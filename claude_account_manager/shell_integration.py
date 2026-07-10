import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal, Mapping, Optional, Sequence


SOURCE_BEGIN = "# >>> claude-account-manager source >>>"
SOURCE_BLOCK = "\n".join((
    SOURCE_BEGIN,
    'if [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/claude-account-manager/shell.sh" ]; then',
    '    . "${XDG_CONFIG_HOME:-$HOME/.config}/claude-account-manager/shell.sh"',
    "fi",
    "# <<< claude-account-manager source <<<",
)) + "\n"
SOURCE_END = "# <<< claude-account-manager source <<<"


_FRAGMENT = "\n".join((
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

_LEGACY_BLOCK = re.compile(
    rb"^# >>> account-manager >>>(?:\r?\n|$).*?^# <<< account-manager <<<(?:\r?\n|$)",
    re.MULTILINE | re.DOTALL,
)
_LEGACY_ALIAS = re.compile(
    rb"^[ \t]*alias[ \t]+(?:account|account-switch|account-list)=(?:"
    rb"'_account_mgr_run(?: (?:switch|list))?'|"
    rb'"_account_mgr_run(?: (?:switch|list))?"|'
    rb"'python3 [^'\r\n]*/\.claude/plugins/cache/(?:local|lee-ji-hoon)/account/"
    rb"[0-9]+\.[0-9]+\.[0-9]+/account_manager\.py[^'\r\n]*'|"
    rb'"python3 [^"\r\n]*/\.claude/plugins/cache/(?:local|lee-ji-hoon)/account/'
    rb'[0-9]+\.[0-9]+\.[0-9]+/account_manager\.py[^"\r\n]*"'
    rb")[ \t]*(?:\r?\n|$)",
    re.MULTILINE,
)


def fragment_path(environ: Optional[Mapping[str, str]] = None) -> Path:
    env = os.environ if environ is None else environ
    config_home = env.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path(env["HOME"]) / ".config"
    return base / "claude-account-manager" / "shell.sh"


def render_fragment() -> str:
    return _FRAGMENT


def _atomic_replace(path: Path, content: bytes, mode: int) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as temp_file:
            fd = -1
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, str(path))
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def ensure_fragment(path: Optional[Path] = None) -> bool:
    destination = fragment_path() if path is None else Path(path)
    desired = render_fragment().encode("utf-8")
    try:
        if destination.read_bytes() == desired:
            return False
    except FileNotFoundError:
        pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace(destination, desired, 0o600)
    return True


def is_git_tracked(path: Path) -> bool:
    actual_path = Path(path).resolve()
    ambiguous_git_variables = {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_GLOB_PATHSPECS",
        "GIT_GRAFT_FILE",
        "GIT_ICASE_PATHSPECS",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_LITERAL_PATHSPECS",
        "GIT_NAMESPACE",
        "GIT_NOGLOB_PATHSPECS",
        "GIT_NO_REPLACE_OBJECTS",
        "GIT_OBJECT_DIRECTORY",
        "GIT_PREFIX",
        "GIT_QUARANTINE_PATH",
        "GIT_REPLACE_REF_BASE",
        "GIT_SHALLOW_FILE",
    }
    if any(
        variable in ambiguous_git_variables or variable.startswith("GIT_CONFIG_")
        for variable in os.environ
    ):
        return True

    repository_context_present = "GIT_DIR" in os.environ or "GIT_WORK_TREE" in os.environ
    for directory in (actual_path.parent,) + tuple(actual_path.parent.parents):
        try:
            (directory / ".git").lstat()
        except FileNotFoundError:
            continue
        except OSError:
            repository_context_present = True
            break
        repository_context_present = True
        break

    git_env = {
        variable: os.environ[variable]
        for variable in ("HOME", "PATH", "TMPDIR", "GIT_DIR", "GIT_WORK_TREE")
        if variable in os.environ
    }
    git_env.update({
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "LC_ALL": "C",
    })

    try:
        worktree = subprocess.run(
            ["git", "-C", str(actual_path.parent), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=git_env,
        )
    except OSError:
        return True
    if worktree.returncode != 0:
        error = (worktree.stderr or "").strip()
        outside_worktree = (
            worktree.returncode == 128
            and error == "fatal: not a git repository (or any of the parent directories): .git"
            and not repository_context_present
        )
        return not outside_worktree

    root_text = worktree.stdout.strip()
    if not root_text:
        return True
    root = Path(root_text).resolve()
    try:
        relative_path = actual_path.relative_to(root)
    except ValueError:
        return True

    try:
        tracked = subprocess.run(
            [
                "git",
                "--literal-pathspecs",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                str(relative_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=git_env,
        )
    except OSError:
        return True
    if tracked.returncode == 0:
        return True
    return tracked.returncode != 1


def install_source_block(rc_path: Path) -> Literal["installed", "already", "unsafe"]:
    path = Path(rc_path)
    try:
        original = path.read_bytes()
    except OSError:
        original = None

    source_block = SOURCE_BLOCK.encode("utf-8")
    if original is not None and source_block in original:
        return "already"
    if path.is_symlink():
        return "unsafe"
    if original is None or not path.is_file():
        return "unsafe"
    if is_git_tracked(path.resolve()):
        return "unsafe"

    cleaned = _LEGACY_BLOCK.sub(b"", original)
    cleaned = _LEGACY_ALIAS.sub(b"", cleaned)
    if cleaned and not cleaned.endswith(b"\n"):
        cleaned += b"\n"
    replacement = cleaned + source_block
    mode = stat.S_IMODE(path.stat().st_mode)
    _atomic_replace(path, replacement, mode)
    return "installed"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["ensure-fragment"]:
        ensure_fragment()
        return 0
    if len(args) == 2 and args[0] == "install-rc":
        result = install_source_block(Path(args[1]))
        return 3 if result == "unsafe" else 0

    print(
        "usage: shell_integration.py ensure-fragment\n"
        "       shell_integration.py install-rc <path>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
