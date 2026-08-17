import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_notes", ROOT / "scripts/release_notes.py"
)
release_notes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_notes)


class ReleaseNotesTests(unittest.TestCase):
    def test_renders_release_with_readme_update(self):
        changelog = """# Changelog

## [3.0.0] - 2026-08-17

### Added
- Added the menu bar app.

### Documentation
- Updated `README.md` and `README.ko.md` for the new app.

## [2.5.10] - 2026-07-19
### Changed
- Older entry.
"""

        release_date, body = release_notes.extract_release(changelog, "3.0.0")
        rendered = release_notes.render_notes("3.0.0", release_date, body)

        self.assertIn("# Switchboard v3.0.0", rendered)
        self.assertIn("Released 2026-08-17", rendered)
        self.assertIn("Updated `README.md`", rendered)
        self.assertNotIn("Older entry", rendered)

    def test_accepts_explained_readme_not_required(self):
        changelog = """# Changelog
## [3.0.1] - 2026-08-17
### Fixed
- Fixed an internal retry race.
### Documentation
- README 변경 불필요 — 사용자 동작과 설치 방법이 바뀌지 않음.
"""

        release_notes.extract_release(changelog, "3.0.1")

    def test_rejects_missing_readme_impact(self):
        changelog = """# Changelog
## [3.0.0] - 2026-08-17
### Added
- Added the menu bar app.
### Documentation
- Updated architecture notes.
"""

        with self.assertRaisesRegex(
            release_notes.ReleaseNotesError, "README file or explain"
        ):
            release_notes.extract_release(changelog, "3.0.0")

    def test_rejects_unexplained_readme_not_required(self):
        changelog = """# Changelog
## [3.0.1] - 2026-08-17
### Fixed
- Fixed an internal retry race.
### Documentation
- README 변경 불필요
"""

        with self.assertRaisesRegex(
            release_notes.ReleaseNotesError, "concrete reason"
        ):
            release_notes.extract_release(changelog, "3.0.1")

    def test_rejects_placeholder_release_notes(self):
        changelog = """# Changelog
## [3.0.0] - 2026-08-17
### Added
- TODO
### Documentation
- Updated `README.md`.
"""

        with self.assertRaisesRegex(
            release_notes.ReleaseNotesError, "placeholder"
        ):
            release_notes.extract_release(changelog, "3.0.0")

    def test_rejects_readme_not_required_for_user_facing_diff(self):
        changelog = """# Changelog
## [3.0.1] - 2026-08-17
### Fixed
- Added a menu-bar switching action.
### Documentation
- README 변경 불필요 — 내부 구현만 변경됨.
"""

        with self.assertRaisesRegex(
            release_notes.ReleaseNotesError, "require both README files"
        ):
            release_notes.extract_release(
                changelog,
                "3.0.1",
                changed_files=["prototype/switchboard-menubar/Sources/main.swift"],
            )

    def test_accepts_both_readmes_for_user_facing_diff(self):
        changelog = """# Changelog
## [3.0.1] - 2026-08-17
### Added
- Added verified provider switching.
### Documentation
- Updated `README.md` and `README.ko.md` with installation and provider limits.
"""

        release_notes.extract_release(
            changelog,
            "3.0.1",
            changed_files=[
                "prototype/switchboard-menubar/Sources/main.swift",
                "README.md",
                "README.ko.md",
            ],
        )

    def test_internal_diff_can_explain_readme_not_required(self):
        changelog = """# Changelog
## [3.0.1] - 2026-08-17
### Fixed
- Hardened release validation.
### Documentation
- README 변경 불필요 — 배포 검증기 내부 동작만 변경됨.
"""

        release_notes.extract_release(
            changelog,
            "3.0.1",
            changed_files=["scripts/release_notes.py"],
        )
