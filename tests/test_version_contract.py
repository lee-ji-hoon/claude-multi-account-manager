import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEVELOP_REFSPEC = "+refs/heads/develop:refs/remotes/origin/develop"
MAIN_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"


def run_git(*args, check=True):
    return subprocess.run(
        ["git"] + list(args),
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def read_project_version():
    section = None
    versions = []
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        section_match = re.match(r"^\s*\[([^]]+)]\s*$", line)
        if section_match:
            section = section_match.group(1)
            continue
        if section == "project":
            version_match = re.match(r'^\s*version\s*=\s*["\']([^"\']+)["\']\s*$', line)
            if version_match:
                versions.append(version_match.group(1))

    if len(versions) != 1:
        raise AssertionError(
            "pyproject.toml [project] must contain exactly one literal version entry"
        )
    return versions[0]


def read_release_skill():
    return (ROOT / "skills/release/SKILL.md").read_text(encoding="utf-8")


def release_bash_blocks(release):
    return re.findall(r"```bash\n(.*?)\n```", release, flags=re.DOTALL)


def block_containing(release, marker):
    matches = [block for block in release_bash_blocks(release) if marker in block]
    if len(matches) != 1:
        raise AssertionError(
            "expected exactly one release bash block containing {!r}, found {}".format(
                marker, len(matches)
            )
        )
    return matches[0]


def assert_markers_in_order(test_case, text, markers):
    position = -1
    for marker in markers:
        next_position = text.find(marker, position + 1)
        test_case.assertNotEqual(
            -1,
            next_position,
            "missing or misordered marker {!r}".format(marker),
        )
        position = next_position


class VersionContractTests(unittest.TestCase):
    def test_ci_runs_supported_python_matrix_and_full_gate(self):
        workflow_path = ROOT / ".github/workflows/test.yml"
        self.assertTrue(workflow_path.is_file(), "CI workflow must exist")
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertRegex(
            workflow,
            r"(?ms)^on:\s*\n\s+pull_request:\s*\n\s+push:\s*\n"
            r"\s+branches:\s*\[\s*main\s*,\s*develop\s*]",
        )
        self.assertRegex(
            workflow,
            r'python-version:\s*\[\s*["\']3\.8["\']\s*,\s*["\']3\.12["\']\s*]',
        )
        self.assertIn("python-version: ${{ matrix.python-version }}", workflow)

        run_commands = re.findall(r"(?m)^\s*-?\s*run:\s*(\S.*)$", workflow)
        self.assertEqual(
            [
                "python3 -m unittest discover -s tests -p 'test_*.py'",
                "bash tests/test_hooks_shell.sh",
                "bash tests/test_install_shell.sh",
                "bash -n install.sh hooks-handlers/session-start.sh hooks-handlers/prompt-submit.sh",
            ],
            run_commands,
        )

    def test_plugin_marketplace_and_project_versions_match(self):
        plugin = json.loads(
            (ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        account_entries = [
            entry for entry in marketplace["plugins"] if entry.get("name") == "account"
        ]
        self.assertEqual(1, len(account_entries), "marketplace must contain one account entry")

        versions = {
            "plugin.json": plugin["version"],
            "marketplace.json": account_entries[0]["version"],
            "pyproject.toml": read_project_version(),
        }
        self.assertEqual(
            1,
            len(set(versions.values())),
            "release metadata versions differ: "
            + ", ".join("{}={}".format(name, value) for name, value in versions.items()),
        )

    def test_install_reads_plugin_version_without_literal(self):
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        literal_assignment = re.compile(
            r"(?m)^\s*PLUGIN_VERSION\s*=\s*[\"']?\d+\.\d+\.\d+[\"']?\s*(?:#.*)?$"
        )
        self.assertIsNone(
            literal_assignment.search(install),
            "install.sh must not hard-code PLUGIN_VERSION",
        )
        assignment = next(
            (
                line
                for line in install.splitlines()
                if line.strip().startswith("PLUGIN_VERSION=")
            ),
            "",
        )
        self.assertIn(".claude-plugin/plugin.json", assignment)
        self.assertRegex(assignment, r"json\.(?:load|loads)")
        self.assertIn('["version"]', assignment)

    def test_release_skill_orders_version_gate_and_publication(self):
        release = read_release_skill()
        required_in_order = [
            "git fetch origin '{}'".format(DEVELOP_REFSPEC),
            "git checkout develop",
            "git checkout -b develop --track origin/develop",
            "git merge --ff-only origin/develop",
            'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/develop)"',
            'test -z "$(git status --porcelain)"',
            "remote tag",
            "local cache",
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "pyproject.toml",
            "CHANGELOG.md",
            "python3 -m unittest discover -s tests -p 'test_*.py'",
            "bash tests/test_hooks_shell.sh",
            "bash tests/test_install_shell.sh",
            "bash -n install.sh hooks-handlers/session-start.sh hooks-handlers/prompt-submit.sh",
            "git add .claude-plugin/plugin.json .claude-plugin/marketplace.json pyproject.toml CHANGELOG.md",
            "git commit",
            "git push origin develop",
            "git fetch origin '{}'".format(DEVELOP_REFSPEC),
            'test "$(git rev-parse origin/develop)" = "$RELEASE_SHA"',
            "git fetch origin '{}'".format(MAIN_REFSPEC),
            "git checkout main",
            "git merge --ff-only origin/main",
            'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"',
            'git merge --no-ff "$RELEASE_SHA" -m "Merge develop: v{version}"',
            "main HEAD",
            "git tag -a",
            "git push origin main",
            "git fetch origin '{}'".format(MAIN_REFSPEC),
            'test "$(git rev-parse origin/main)" = "$MAIN_SHA"',
            "git push origin v{version}",
            "marketplace clone",
            "git -C \"$HOME/.claude/plugins/marketplaces/lee-ji-hoon\" fetch origin '{}'".format(
                MAIN_REFSPEC
            ),
            "$HOME/.claude/plugins/cache/lee-ji-hoon/account/{version}",
        ]

        position = -1
        for marker in required_in_order:
            next_position = release.find(marker, position + 1)
            self.assertNotEqual(
                -1,
                next_position,
                "release skill is missing or misorders {!r}".format(marker),
            )
            position = next_position

    def test_release_skill_wraps_every_bash_gate_in_fail_fast_execution(self):
        blocks = release_bash_blocks(read_release_skill())
        self.assertGreaterEqual(len(blocks), 6, "release skill must expose every gate")

        for index, block in enumerate(blocks, start=1):
            lines = block.splitlines()
            self.assertEqual(
                "bash -euo pipefail <<'SH'",
                lines[0],
                "release bash block {} must enter fail-fast bash".format(index),
            )
            self.assertEqual(
                "SH",
                lines[-1],
                "release bash block {} must close the fail-fast unit".format(index),
            )

    def test_release_skill_rejects_local_ahead_develop_and_main(self):
        release = read_release_skill()
        develop_block = block_containing(release, "git checkout develop")
        main_block = block_containing(release, "git checkout main")

        assert_markers_in_order(
            self,
            develop_block,
            [
                "git fetch origin '{}'".format(DEVELOP_REFSPEC),
                "git checkout develop",
                "git checkout -b develop --track origin/develop",
                "git merge --ff-only origin/develop",
                'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/develop)"',
                'test -z "$(git status --porcelain)"',
            ],
        )
        assert_markers_in_order(
            self,
            main_block,
            [
                "git fetch origin '{}'".format(MAIN_REFSPEC),
                "git checkout main",
                "git merge --ff-only origin/main",
                'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"',
                'git merge --no-ff "$RELEASE_SHA" -m "Merge develop: v{version}"',
            ],
        )

    def test_release_skill_supports_single_branch_fetch_configuration(self):
        release = read_release_skill()
        develop_block = block_containing(release, "git checkout develop")
        publication = block_containing(release, 'git commit -m "release: v{version}"')
        marketplace = block_containing(
            release,
            'git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" checkout main',
        )

        self.assertNotIn("git pull", develop_block)
        self.assertNotIn("git pull", publication)
        self.assertNotIn("git pull", marketplace)
        self.assertNotIn("\ngit fetch origin develop\n", release)
        self.assertNotIn("\ngit fetch origin main\n", release)
        assert_markers_in_order(
            self,
            develop_block,
            [
                "git fetch origin '{}'".format(DEVELOP_REFSPEC),
                "if git show-ref --verify --quiet refs/heads/develop; then",
                "git checkout develop",
                "git checkout -b develop --track origin/develop",
                "git merge --ff-only origin/develop",
                'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/develop)"',
                'test -z "$(git status --porcelain)"',
            ],
        )
        assert_markers_in_order(
            self,
            publication,
            [
                "git push origin develop",
                "git fetch origin '{}'".format(DEVELOP_REFSPEC),
                'test "$(git rev-parse origin/develop)" = "$RELEASE_SHA"',
                "git fetch origin '{}'".format(MAIN_REFSPEC),
                "git checkout main",
                "git merge --ff-only origin/main",
                'test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"',
                'git merge --no-ff "$RELEASE_SHA" -m "Merge develop: v{version}"',
                'test "$(git rev-parse "$MAIN_SHA^2")" = "$RELEASE_SHA"',
            ],
        )
        assert_markers_in_order(
            self,
            marketplace,
            [
                "git -C \"$HOME/.claude/plugins/marketplaces/lee-ji-hoon\" fetch origin '{}'".format(
                    MAIN_REFSPEC
                ),
                'git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" checkout main',
                'git -C "$HOME/.claude/plugins/marketplaces/lee-ji-hoon" merge --ff-only origin/main',
            ],
        )

    def test_skill_develop_refspec_materializes_tracking_ref_in_single_branch_clone(self):
        release = read_release_skill()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin.git"
            seed = root / "seed"
            clone = root / "clone"

            run_git("init", "--bare", "-q", str(origin))
            run_git("init", "-q", "-b", "main", str(seed))
            run_git("-C", str(seed), "config", "user.name", "test")
            run_git("-C", str(seed), "config", "user.email", "test@example.invalid")
            run_git("-C", str(seed), "commit", "-q", "--allow-empty", "-m", "initial")
            run_git("-C", str(seed), "branch", "develop")
            run_git("-C", str(seed), "remote", "add", "origin", str(origin))
            run_git("-C", str(seed), "push", "-q", "origin", "main", "develop")
            run_git(
                "clone",
                "-q",
                "--single-branch",
                "--branch",
                "main",
                str(origin),
                str(clone),
            )

            fetch_config = run_git(
                "-C", str(clone), "config", "--get-all", "remote.origin.fetch"
            ).stdout.splitlines()
            self.assertEqual([MAIN_REFSPEC], fetch_config)

            run_git("-C", str(clone), "fetch", "-q", "origin", "develop")
            plain_ref = run_git(
                "-C",
                str(clone),
                "show-ref",
                "--verify",
                "--quiet",
                "refs/remotes/origin/develop",
                check=False,
            )
            self.assertNotEqual(
                0,
                plain_ref.returncode,
                "source-only fetch must reproduce the missing tracking ref",
            )

            refspec_match = re.search(re.escape(DEVELOP_REFSPEC), release)
            self.assertIsNotNone(
                refspec_match,
                "release skill must carry the destination refspec used by this fixture",
            )
            skill_refspec = refspec_match.group(0)
            run_git("-C", str(clone), "fetch", "-q", "origin", skill_refspec)
            tracked = run_git(
                "-C",
                str(clone),
                "show-ref",
                "--verify",
                "--quiet",
                "refs/remotes/origin/develop",
                check=False,
            )
            self.assertEqual(0, tracked.returncode)
            self.assertEqual(
                run_git("-C", str(seed), "rev-parse", "develop").stdout.strip(),
                run_git(
                    "-C", str(clone), "rev-parse", "refs/remotes/origin/develop"
                ).stdout.strip(),
            )

    def test_release_skill_verifies_exact_release_sha_before_each_publication(self):
        publication = block_containing(read_release_skill(), 'git commit -m "release: v{version}"')
        self.assertNotIn(
            "git merge develop",
            publication,
            "main must merge the recorded release commit, not a moving branch name",
        )
        self.assertNotIn(
            '\ngit merge "$RELEASE_SHA"\n',
            publication,
            "main must not fast-forward across the release boundary",
        )

        assert_markers_in_order(
            self,
            publication,
            [
                'git commit -m "release: v{version}"',
                'RELEASE_SHA="$(git rev-parse HEAD)"',
                "git push origin develop",
                "git fetch origin '{}'".format(DEVELOP_REFSPEC),
                'test "$(git rev-parse origin/develop)" = "$RELEASE_SHA"',
                "git fetch origin '{}'".format(MAIN_REFSPEC),
                "git checkout main",
                "git merge --ff-only origin/main",
                'git merge --no-ff "$RELEASE_SHA" -m "Merge develop: v{version}"',
                'MAIN_SHA="$(git rev-parse HEAD)"',
                'test "$MAIN_SHA" != "$RELEASE_SHA"',
                'test "$(git rev-parse "$MAIN_SHA^2")" = "$RELEASE_SHA"',
                'git merge-base --is-ancestor "$RELEASE_SHA" "$MAIN_SHA"',
                'git tag -a v{version} -m "v{version}" "$MAIN_SHA"',
                'TAG_SHA="$(git rev-list -n 1 v{version})"',
                'test "$TAG_SHA" = "$MAIN_SHA"',
                'git merge-base --is-ancestor "$RELEASE_SHA" "$TAG_SHA"',
                "git push origin main",
                "git fetch origin '{}'".format(MAIN_REFSPEC),
                'test "$(git rev-parse origin/main)" = "$MAIN_SHA"',
                "git push origin v{version}",
                'REMOTE_TAG_SHA="$(git ls-remote --tags origin "refs/tags/v{version}^{}"',
                'test "$REMOTE_TAG_SHA" = "$MAIN_SHA"',
                'git merge-base --is-ancestor "$RELEASE_SHA" "$REMOTE_TAG_SHA"',
            ],
        )

    def test_release_skill_commits_the_same_clean_develop_tree_that_passed_gates(self):
        release = read_release_skill()
        gate_end_marker = (
            "bash -n install.sh hooks-handlers/session-start.sh "
            "hooks-handlers/prompt-submit.sh"
        )
        stage_command = (
            "git add .claude-plugin/plugin.json .claude-plugin/marketplace.json "
            "pyproject.toml CHANGELOG.md"
        )
        clean_command = (
            'test -z "$(git status --porcelain)" || { echo '
            '"ERROR: develop worktree is not clean" >&2; exit 1; }'
        )

        self.assertIn(clean_command, release, "release must assert a clean develop tree")

        checkout_position = release.index("git checkout develop")
        merge_position = release.find(
            "git merge --ff-only origin/develop", checkout_position
        )
        self.assertNotEqual(
            -1,
            merge_position,
            "develop must be fast-forwarded from the fetched tracking ref",
        )
        clean_position = release.index(clean_command, merge_position)
        metadata_position = release.index(".claude-plugin/plugin.json", clean_position)
        gate_end = release.index(gate_end_marker, metadata_position) + len(
            gate_end_marker
        )
        commit_position = release.index('git commit -m "release: v{version}"', gate_end)

        git_commands_after_gate = re.findall(
            r"(?m)^git \S.*$", release[gate_end:commit_position]
        )
        self.assertEqual(
            [stage_command],
            git_commands_after_gate,
            "only the four-file staging command may occur between gates and commit",
        )

    def test_release_skill_fails_closed_when_remote_tag_fetch_fails(self):
        release = (ROOT / "skills/release/SKILL.md").read_text(encoding="utf-8")
        fetch_commands = re.findall(
            r"(?m)^git fetch --tags origin.*$",
            release,
        )
        self.assertEqual(
            [
                'git fetch --tags origin || { echo "ERROR: failed to fetch remote tags" '
                ">&2; exit 1; }"
            ],
            fetch_commands,
        )
        self.assertLess(
            release.index(fetch_commands[0]),
            release.index('python3 - "{version}"'),
        )


if __name__ == "__main__":
    unittest.main()
