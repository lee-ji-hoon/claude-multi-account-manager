import importlib
import os
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "claude_account_manager"
package = types.ModuleType("claude_account_manager")
package.__path__ = [str(PACKAGE_DIR)]
previous_package = sys.modules.get("claude_account_manager")
sys.modules["claude_account_manager"] = package
try:
    shell_integration = importlib.import_module("claude_account_manager.shell_integration")
finally:
    if previous_package is None:
        del sys.modules["claude_account_manager"]
    else:
        sys.modules["claude_account_manager"] = previous_package


EXPECTED_FRAGMENT = "\n".join((
    "_account_mgr_run() {",
    '    local root version candidate best_version="" manager=""',
    "    for root in \\",
    '        "$HOME/.claude/plugins/cache/local/account" \\',
    '        "$HOME/.claude/plugins/cache/lee-ji-hoon/account"; do',
    '        [ -d "$root" ] || continue',
    "        version=$(ls -1 \"$root\" 2>/dev/null | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+$' | sort -V | tail -1)",
    '        candidate="$root/$version/account_manager.py"',
    '        [ -n "$version" ] && [ -f "$candidate" ] || continue',
    '        if [ -z "$best_version" ] || [ "$(printf \'%s\\n%s\\n\' "$best_version" "$version" | sort -V | tail -1)" = "$version" ]; then',
    '            best_version="$version"',
    '            manager="$candidate"',
    "        fi",
    "    done",
    '    if [ -z "$manager" ]; then',
    '        echo "account: installed plugin not found" >&2',
    "        return 1",
    "    fi",
    '    ( unset CLAUDE_CONFIG_DIR; python3 "$manager" "$@" )',
    "}",
    "alias account='_account_mgr_run'",
    "alias account-switch='_account_mgr_run switch'",
    "alias account-list='_account_mgr_run list'",
)) + "\n"


def _write_manager(home, namespace, version, label):
    manager = home / ".claude" / "plugins" / "cache" / namespace / "account" / version / "account_manager.py"
    manager.parent.mkdir(parents=True)
    manager.write_text(
        "import os, sys\n"
        "secret_state = 'secret-present' if 'SHELL_INTEGRATION_TEST_SECRET' in os.environ else 'secret-absent'\n"
        "print(%r + '|' + os.environ.get('CLAUDE_CONFIG_DIR', '<unset>') + '|' + ','.join(sys.argv[1:]) + '|' + secret_state)\n"
        % label
    )


class TestShellIntegration(unittest.TestCase):
    def test_fragment_path_honors_xdg_config_home(self):
        self.assertEqual(
            shell_integration.fragment_path({"XDG_CONFIG_HOME": "/tmp/sentinel-xdg", "HOME": "/tmp/ignored"}),
            Path("/tmp/sentinel-xdg/claude-account-manager/shell.sh"),
        )
        self.assertEqual(
            shell_integration.fragment_path({"HOME": "/tmp/sentinel-home"}),
            Path("/tmp/sentinel-home/.config/claude-account-manager/shell.sh"),
        )

    def test_render_fragment_searches_marketplace_and_local_cache_and_unsets_claude_config_dir(self):
        self.assertEqual(shell_integration.render_fragment(), EXPECTED_FRAGMENT)

    def test_wrapper_selects_highest_version_across_both_cache_namespaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            _write_manager(home, "local", "2.10.0", "local-2.10.0")
            _write_manager(home, "lee-ji-hoon", "2.9.9", "marketplace-2.9.9")
            fragment = home / "shell.sh"
            fragment.write_text(shell_integration.render_fragment())
            with mock.patch.dict(
                os.environ,
                {"PATH": os.environ.get("PATH", ""), "SHELL_INTEGRATION_TEST_SECRET": "sentinel"},
                clear=True,
            ):
                env = {
                    "HOME": str(home),
                    "PATH": os.environ["PATH"],
                    "CLAUDE_CONFIG_DIR": "/tmp/sentinel-profile",
                }

            first = subprocess.run(
                ["bash", "-c", 'source "$1"\n_account_mgr_run probe', "bash", str(fragment)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(first.stdout.strip(), "local-2.10.0|<unset>|probe|secret-absent")

            _write_manager(home, "lee-ji-hoon", "2.10.0", "marketplace-2.10.0")
            tied = subprocess.run(
                ["bash", "-c", 'source "$1"\n_account_mgr_run probe', "bash", str(fragment)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(tied.stdout.strip(), "marketplace-2.10.0|<unset>|probe|secret-absent")

    def test_ensure_fragment_is_idempotent_and_preserves_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "shell.sh"
            self.assertIs(shell_integration.ensure_fragment(path), True)
            self.assertEqual(path.read_text(), EXPECTED_FRAGMENT)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

            stable_mtime = 1_700_000_000_123_456_789
            os.utime(str(path), ns=(stable_mtime, stable_mtime))
            self.assertIs(shell_integration.ensure_fragment(path), False)
            self.assertEqual(path.stat().st_mtime_ns, stable_mtime)

    def test_replace_failure_preserves_previous_complete_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "shell.sh"
            path.write_bytes(b"previous-complete-fragment\n")

            with mock.patch.object(shell_integration, "render_fragment", return_value="replacement\n"), \
                 mock.patch.object(shell_integration.os, "replace", side_effect=OSError("sentinel replace failure")):
                with self.assertRaisesRegex(OSError, "sentinel replace failure"):
                    shell_integration.ensure_fragment(path)

            self.assertEqual(path.read_bytes(), b"previous-complete-fragment\n")
            self.assertEqual(list(directory.iterdir()), [path])

    def test_install_source_block_refuses_symlink_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "owned-zshrc"
            target.write_bytes(b"export SENTINEL=target\n")
            rc_path = directory / ".zshrc"
            rc_path.symlink_to(target)

            self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")
            self.assertTrue(rc_path.is_symlink())
            self.assertEqual(target.read_bytes(), b"export SENTINEL=target\n")

    def test_install_source_block_refuses_git_tracked_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            rc_path = repo / ".zshrc"
            rc_path.write_bytes(b"export SENTINEL=tracked\n")
            subprocess.run(["git", "-C", str(repo), "add", ".zshrc"], check=True)

            self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")
            self.assertEqual(rc_path.read_bytes(), b"export SENTINEL=tracked\n")

    def test_install_source_block_refuses_git_tracked_pathspec_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            rc_path = repo / ":(glob).zshrc"
            original = b"export SENTINEL=tracked-pathspec\n"
            rc_path.write_bytes(original)
            subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)

            self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")
            self.assertEqual(rc_path.read_bytes(), original)

    def test_install_source_block_refuses_when_git_probe_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            rc_path = repo / ".zshrc"
            original = b"export SENTINEL=git-unavailable\n"
            rc_path.write_bytes(original)
            subprocess.run(["git", "-C", str(repo), "add", ".zshrc"], check=True)

            with mock.patch.object(shell_integration.subprocess, "run", side_effect=FileNotFoundError("git")):
                self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")

            self.assertEqual(rc_path.read_bytes(), original)

    def test_install_source_block_refuses_when_worktree_probe_is_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            rc_path = repo / ".zshrc"
            original = b"export SENTINEL=git-probe-error\n"
            rc_path.write_bytes(original)

            failed_probe = subprocess.CompletedProcess(
                ["git", "rev-parse"],
                128,
                stdout="",
                stderr="fatal: not a git repository (or any of the parent directories): .git\n",
            )
            with mock.patch.object(shell_integration.subprocess, "run", return_value=failed_probe):
                self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")

            self.assertEqual(rc_path.read_bytes(), original)

    def test_install_source_block_refuses_ambiguous_nonrepository_probe_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc_path = Path(tmp) / ".zshrc"
            original = b"export SENTINEL=ambiguous-nonrepository-probe\n"
            rc_path.write_bytes(original)
            failed_probe = subprocess.CompletedProcess(
                ["git", "rev-parse"],
                128,
                stdout="",
                stderr=(
                    "fatal: not a git repository (or any of the parent directories): .git\n"
                    "sentinel additional diagnostic\n"
                ),
            )

            with mock.patch.object(shell_integration.subprocess, "run", return_value=failed_probe):
                self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")

            self.assertEqual(rc_path.read_bytes(), original)

    def test_install_source_block_refuses_repository_affecting_git_environment(self):
        for variable, value in (
            ("GIT_INDEX_FILE", "/tmp/sentinel-index"),
            ("GIT_LITERAL_PATHSPECS", "1"),
            ("GIT_CONFIG_COUNT", "0"),
        ):
            with self.subTest(variable=variable), tempfile.TemporaryDirectory() as tmp:
                rc_path = Path(tmp) / ".zshrc"
                original = b"export SENTINEL=ambiguous-git-environment\n"
                rc_path.write_bytes(original)

                with mock.patch.dict(
                    os.environ,
                    {"HOME": tmp, "PATH": os.environ.get("PATH", ""), variable: value},
                    clear=True,
                ), mock.patch.object(shell_integration.subprocess, "run") as git_probe:
                    self.assertEqual(shell_integration.install_source_block(rc_path), "unsafe")

                git_probe.assert_not_called()
                self.assertEqual(rc_path.read_bytes(), original)

    def test_install_source_block_allows_proven_untracked_worktree_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            rc_path = repo / ".zshrc"
            original = b"export SENTINEL=untracked\n"
            rc_path.write_bytes(original)

            self.assertEqual(shell_integration.install_source_block(rc_path), "installed")
            self.assertEqual(rc_path.read_bytes(), original + shell_integration.SOURCE_BLOCK.encode())

    def test_unsafe_rc_with_exact_source_block_is_already_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "owned-zshrc"
            original = b"export SENTINEL=before\n" + shell_integration.SOURCE_BLOCK.encode() + b"export SENTINEL=after\n"
            target.write_bytes(original)
            rc_path = directory / ".zshrc"
            rc_path.symlink_to(target)

            self.assertEqual(shell_integration.install_source_block(rc_path), "already")
            self.assertTrue(rc_path.is_symlink())
            self.assertEqual(target.read_bytes(), original)

    def test_cli_install_rc_returns_3_for_unsafe_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "owned-zshrc"
            target.write_bytes(b"export SENTINEL=target\n")
            rc_path = directory / ".zshrc"
            rc_path.symlink_to(target)

            result = subprocess.run(
                [sys.executable, str(PACKAGE_DIR / "shell_integration.py"), "install-rc", str(rc_path)],
                check=False,
            )

            self.assertEqual(result.returncode, 3)
            self.assertEqual(target.read_bytes(), b"export SENTINEL=target\n")

    def test_regular_rc_gets_exactly_one_source_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc_path = Path(tmp) / ".zshrc"
            original = b"export SENTINEL=regular\n"
            rc_path.write_bytes(original)
            rc_path.chmod(0o640)

            self.assertEqual(shell_integration.install_source_block(rc_path), "installed")
            installed = rc_path.read_bytes()
            self.assertEqual(installed, original + shell_integration.SOURCE_BLOCK.encode())
            self.assertEqual(installed.count(shell_integration.SOURCE_BEGIN.encode()), 1)
            self.assertEqual(stat.S_IMODE(rc_path.stat().st_mode), 0o640)
            self.assertEqual(shell_integration.install_source_block(rc_path), "already")
            self.assertEqual(rc_path.read_bytes(), installed)

    def test_unrelated_same_name_aliases_are_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc_path = Path(tmp) / ".zshrc"
            original = (
                b"export KEEP_BEFORE=sentinel-before\n"
                b"alias account='custom-account --profile personal'\n"
                b"alias account-switch='python3 /tmp/custom/account_manager.py switch'\n"
                b"alias account-list='custom-list-command'\n"
                b"export KEEP_AFTER=sentinel-after\n"
            )
            rc_path.write_bytes(original)

            self.assertEqual(shell_integration.install_source_block(rc_path), "installed")
            self.assertEqual(rc_path.read_bytes(), original + shell_integration.SOURCE_BLOCK.encode())

    def test_regular_rc_legacy_marker_is_removed_without_touching_other_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc_path = Path(tmp) / ".zshrc"
            original = (
                b"export KEEP_BEFORE=sentinel-before\n"
                b"# >>> account-manager >>>\n"
                b"# account-manager-block: v3\n"
                b"alias account='_account_mgr_run'\n"
                b"# <<< account-manager <<<\n"
                b"alias account='python3 /Users/sentinel/.claude/plugins/cache/local/account/2.1.4/account_manager.py'\n"
                b"alias account-switch='python3 /Users/sentinel/.claude/plugins/cache/local/account/2.1.4/account_manager.py switch'\n"
                b"alias account-list='python3 /Users/sentinel/.claude/plugins/cache/local/account/2.1.4/account_manager.py list'\n"
                b"export KEEP_AFTER=sentinel-after\n"
            )
            rc_path.write_bytes(original)

            self.assertEqual(shell_integration.install_source_block(rc_path), "installed")
            installed = rc_path.read_bytes()
            self.assertIn(b"export KEEP_BEFORE=sentinel-before\n", installed)
            self.assertIn(b"export KEEP_AFTER=sentinel-after\n", installed)
            self.assertNotIn(b"# >>> account-manager >>>", installed)
            self.assertNotIn(b"/Users/sentinel/.claude/plugins/cache/local/account", installed)
            self.assertEqual(installed.count(shell_integration.SOURCE_BEGIN.encode()), 1)


if __name__ == "__main__":
    unittest.main()
