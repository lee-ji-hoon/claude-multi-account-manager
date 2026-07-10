import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
        release = (ROOT / "skills/release/SKILL.md").read_text(encoding="utf-8")
        required_in_order = [
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
            "git checkout develop",
            "git commit",
            "git push origin develop",
            "git checkout main",
            "git merge develop",
            "main HEAD",
            "git tag -a",
            "git push origin main",
            "git push origin v{version}",
            "marketplace clone",
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


if __name__ == "__main__":
    unittest.main()
