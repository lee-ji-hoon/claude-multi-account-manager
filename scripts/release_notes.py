#!/usr/bin/env python3
"""Validate a release contract and render GitHub release notes from CHANGELOG.md."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
RELEASE_HEADING = re.compile(
    r"^## \[(?P<version>[0-9]+\.[0-9]+\.[0-9]+)] - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$"
)
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO|FIXME)\b|작성\s*예정", re.IGNORECASE)
README_NOT_REQUIRED = re.compile(
    r"README\s+(?:변경|수정|update)\s*(?:이\s*)?(?:불필요|not required)",
    re.IGNORECASE,
)
README_NOT_REQUIRED_REASON = re.compile(
    r"README\s+(?:변경|수정|update)\s*(?:이\s*)?(?:불필요|not required)"
    r"\s*(?:—|–|:|-)\s*\S.{5,}",
    re.IGNORECASE,
)


class ReleaseNotesError(ValueError):
    pass


USER_FACING_PATHS = (
    "account_manager.py",
    "claude_account_manager/",
    "hooks-handlers/",
    "install.sh",
    "prototype/",
    "skills/",
    "uninstall.sh",
)


def changed_files_since(base_ref):
    if not base_ref:
        return []
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", base_ref, "--"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ReleaseNotesError(
            "cannot inspect README impact from base ref {}".format(base_ref)
        ) from error
    return [line.strip() for line in output.splitlines() if line.strip()]


def validate_readme_impact(documentation_text, changed_files):
    if not changed_files:
        return
    user_facing = any(
        path == prefix or path.startswith(prefix)
        for path in changed_files
        for prefix in USER_FACING_PATHS
    )
    if not user_facing:
        return
    missing_mentions = [
        name for name in ("README.md", "README.ko.md")
        if name not in documentation_text
    ]
    missing_changes = [
        name for name in ("README.md", "README.ko.md")
        if name not in changed_files
    ]
    if missing_mentions or missing_changes:
        raise ReleaseNotesError(
            "user-facing changes require both README files to be changed and named"
        )


def read_project_version(path):
    section = None
    versions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        section_match = re.match(r"^\s*\[([^]]+)]\s*$", line)
        if section_match:
            section = section_match.group(1)
            continue
        if section == "project":
            version_match = re.match(
                r'^\s*version\s*=\s*["\']([^"\']+)["\']\s*$', line
            )
            if version_match:
                versions.append(version_match.group(1))
    if len(versions) != 1:
        raise ReleaseNotesError(
            "pyproject.toml [project] must contain exactly one literal version"
        )
    return versions[0]


def metadata_versions(root):
    plugin = json.loads(
        (root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    entries = [entry for entry in marketplace["plugins"] if entry.get("name") == "account"]
    if len(entries) != 1:
        raise ReleaseNotesError("marketplace must contain exactly one account plugin")
    return {
        "plugin.json": plugin["version"],
        "marketplace.json": entries[0]["version"],
        "pyproject.toml": read_project_version(root / "pyproject.toml"),
    }


def extract_release(changelog, version, changed_files=None):
    if not SEMVER.fullmatch(version):
        raise ReleaseNotesError("version must be strict MAJOR.MINOR.PATCH")

    lines = changelog.splitlines()
    start = None
    release_date = None
    for index, line in enumerate(lines):
        match = RELEASE_HEADING.fullmatch(line)
        if match and match.group("version") == version:
            if start is not None:
                raise ReleaseNotesError("CHANGELOG contains duplicate release headings")
            start = index
            release_date = match.group("date")
    if start is None:
        raise ReleaseNotesError("CHANGELOG is missing the exact dated release heading")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if RELEASE_HEADING.fullmatch(lines[index]):
            end = index
            break

    body_lines = lines[start + 1 : end]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    body = "\n".join(body_lines)

    if not body or PLACEHOLDER.search(body):
        raise ReleaseNotesError("release section is empty or contains a placeholder")

    sections = {}
    current = None
    for line in body_lines:
        heading = re.fullmatch(r"###\s+(.+)", line)
        if heading:
            current = heading.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)

    documentation = sections.get("Documentation")
    if documentation is None:
        raise ReleaseNotesError("release requires a ### Documentation section")
    documentation_text = "\n".join(documentation)
    documentation_bullets = [
        line for line in documentation if re.match(r"^\s*[-*]\s+\S", line)
    ]
    if not documentation_bullets:
        raise ReleaseNotesError("Documentation must contain a README impact bullet")

    mentions_readme = "README.md" in documentation_text or "README.ko.md" in documentation_text
    declares_not_required = README_NOT_REQUIRED.search(documentation_text) is not None
    explains_not_required = any(
        README_NOT_REQUIRED_REASON.search(line) for line in documentation_bullets
    )
    if not mentions_readme and not declares_not_required:
        raise ReleaseNotesError(
            "Documentation must name the updated README file or explain that a README update is not required"
        )
    if declares_not_required and not explains_not_required:
        raise ReleaseNotesError(
            "README not-required declaration must include a concrete reason after a separator"
        )
    validate_readme_impact(documentation_text, changed_files or [])

    non_documentation_bullets = [
        line
        for name, section_lines in sections.items()
        if name != "Documentation"
        for line in section_lines
        if re.match(r"^\s*[-*]\s+\S", line)
    ]
    if not non_documentation_bullets:
        raise ReleaseNotesError("release requires at least one user-visible change bullet")

    return release_date, body


def render_notes(version, release_date, body):
    return "# Switchboard v{}\n\nReleased {}\n\n{}\n".format(
        version, release_date, body
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref used to verify README impact from the actual release diff",
    )
    args = parser.parse_args(argv)

    try:
        versions = metadata_versions(ROOT)
        mismatches = {
            name: value for name, value in versions.items() if value != args.version
        }
        if mismatches:
            details = ", ".join(
                "{}={}".format(name, value) for name, value in mismatches.items()
            )
            raise ReleaseNotesError("release metadata differs from {}: {}".format(args.version, details))

        changed_files = changed_files_since(args.base_ref)
        release_date, body = extract_release(
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            args.version,
            changed_files=changed_files,
        )
        rendered = render_notes(args.version, release_date, body)
    except (OSError, KeyError, json.JSONDecodeError, ReleaseNotesError) as error:
        print("release-notes: {}".format(error), file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
