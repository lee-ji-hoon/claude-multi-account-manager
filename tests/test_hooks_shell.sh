#!/usr/bin/env bash
# hooks-handlers 셸 스크립트 회귀 테스트 (bash 전용, python unittest 밖)
#
# 검증: SessionStart는 CLAUDE_CONFIG_DIR을 지운 뒤 auto-add를 호출하고, 사용자 소유의
# shell rc는 바꾸지 않은 채 별도 runtime fragment만 멱등적으로 보장해야 한다.
#
# 실행: bash tests/test_hooks_shell.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
PYTHON_BIN="$(command -v python3)"
SAFE_PATH="$(dirname "$PYTHON_BIN"):/usr/bin:/bin:/usr/sbin:/sbin"

_tmp() {
    mktemp -d "${TMPDIR:-/tmp}/account-mgr-hooktest.XXXXXX"
}

assert_contains() {
    local haystack="$1" needle="$2" msg="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "  ok: $msg"
    else
        echo "  FAIL: $msg (원했던 문자열 없음: $needle)"
        FAIL=1
    fi
}

assert_not_contains() {
    local haystack="$1" needle="$2" msg="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "  ok: $msg"
    else
        echo "  FAIL: $msg (있으면 안 되는 문자열 발견: $needle)"
        FAIL=1
    fi
}

assert_equal() {
    local actual="$1" expected="$2" msg="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  ok: $msg"
    else
        echo "  FAIL: $msg (actual=$actual, expected=$expected)"
        FAIL=1
    fi
}

assert_file_exists() {
    local path="$1" msg="$2"
    if [ -f "$path" ]; then
        echo "  ok: $msg"
    else
        echo "  FAIL: $msg (파일 없음: $path)"
        FAIL=1
    fi
}

file_mtime_ns() {
    "$PYTHON_BIN" -c 'import os,sys; print(os.stat(sys.argv[1]).st_mtime_ns)' "$1"
}

# ── 1. session-start.sh가 account_manager.py 호출 전 CLAUDE_CONFIG_DIR을 지우는지 ──
echo "[1] session-start.sh: CLAUDE_CONFIG_DIR unset 후 account_manager.py auto-add 호출"
WORK=$(_tmp)
mkdir -p "$WORK/hooks-handlers" "$WORK/claude_account_manager"
cp "$REPO_ROOT/hooks-handlers/session-start.sh" "$WORK/hooks-handlers/session-start.sh"
cp "$REPO_ROOT/claude_account_manager/shell_integration.py" "$WORK/claude_account_manager/shell_integration.py"
cat > "$WORK/account_manager.py" <<'EOF'
import os, sys
print("ARGS=" + " ".join(sys.argv[1:]))
print("CLAUDE_CONFIG_DIR=" + os.environ.get("CLAUDE_CONFIG_DIR", "<unset>"))
if os.environ.get("SENTINEL_AUTO_ADD_FAIL") == "1":
    raise SystemExit(23)
EOF
HOME_FAKE=$(_tmp)
XDG_FAKE="$HOME_FAKE/xdg"
OUT=$(env -i HOME="$HOME_FAKE" XDG_CONFIG_HOME="$XDG_FAKE" PATH="$SAFE_PATH" SHELL=/bin/zsh CLAUDE_CONFIG_DIR="$HOME_FAKE/.claude-lean" bash "$WORK/hooks-handlers/session-start.sh" 2>&1)
assert_contains "$OUT" "ARGS=auto-add" "auto-add 호출됨"
assert_contains "$OUT" "CLAUDE_CONFIG_DIR=<unset>" "hook 내부에서 CLAUDE_CONFIG_DIR이 지워짐"

# ── 2. prompt-submit.sh도 동일 ──
echo "[2] prompt-submit.sh: CLAUDE_CONFIG_DIR unset 후 refresh-expiring 호출"
WORK2=$(_tmp)
mkdir -p "$WORK2/hooks-handlers"
cp "$REPO_ROOT/hooks-handlers/prompt-submit.sh" "$WORK2/hooks-handlers/prompt-submit.sh"
cp "$WORK/account_manager.py" "$WORK2/account_manager.py"
HOME2=$(_tmp)
OUT2=$(env -i HOME="$HOME2" PATH="$SAFE_PATH" CLAUDE_CONFIG_DIR="$HOME2/sentinel-lean-dir" bash "$WORK2/hooks-handlers/prompt-submit.sh" 2>&1)
assert_contains "$OUT2" "ARGS=refresh-expiring 1" "refresh-expiring 호출됨"
assert_contains "$OUT2" "CLAUDE_CONFIG_DIR=<unset>" "hook 내부에서 CLAUDE_CONFIG_DIR이 지워짐"

# ── 3. tracked fixture를 가리키는 rc symlink는 불변, runtime fragment는 멱등 생성 ──
echo "[3] session-start.sh: shell rc 불변 + runtime fragment 멱등 생성"
HOME3=$(_tmp)
RC_REPO=$(_tmp)
git init -q "$RC_REPO"
cat > "$RC_REPO/tracked-zshrc" <<'EOF'
export SENTINEL_RC_OWNERSHIP=preserve-byte-for-byte
EOF
git -C "$RC_REPO" add tracked-zshrc
ln -s "$RC_REPO/tracked-zshrc" "$HOME3/.zshrc"
XDG3="$HOME3/xdg"
FRAGMENT3="$XDG3/claude-account-manager/shell.sh"
RC_HASH_BEFORE=$(shasum -a 256 "$HOME3/.zshrc" | awk '{print $1}')
RC_MTIME_BEFORE=$(file_mtime_ns "$HOME3/.zshrc")
env -i HOME="$HOME3" XDG_CONFIG_HOME="$XDG3" PATH="$SAFE_PATH" SHELL=/bin/zsh CLAUDE_CONFIG_DIR="$HOME3/sentinel-profile" bash "$WORK/hooks-handlers/session-start.sh" >/dev/null 2>&1
RC_HASH_AFTER=$(shasum -a 256 "$HOME3/.zshrc" | awk '{print $1}')
RC_MTIME_AFTER=$(file_mtime_ns "$HOME3/.zshrc")
assert_equal "$RC_HASH_AFTER" "$RC_HASH_BEFORE" "tracked rc symlink 대상의 SHA-256 불변"
assert_equal "$RC_MTIME_AFTER" "$RC_MTIME_BEFORE" "tracked rc symlink 대상의 st_mtime_ns 불변"
assert_file_exists "$FRAGMENT3" "XDG runtime fragment 생성됨"

if [ -f "$FRAGMENT3" ]; then
    FRAGMENT_CONTENT=$(cat "$FRAGMENT3")
    assert_contains "$FRAGMENT_CONTENT" "_account_mgr_run()" "fragment에 account wrapper 존재"
    assert_contains "$FRAGMENT_CONTENT" "sort -V | tail -1" "fragment가 latest version을 동적 선택"
    assert_contains "$FRAGMENT_CONTENT" "unset CLAUDE_CONFIG_DIR" "fragment 실행 시 CLAUDE_CONFIG_DIR unset"

    "$PYTHON_BIN" -c 'import os,sys; t=946684800000000000; os.utime(sys.argv[1], ns=(t,t))' "$FRAGMENT3"
    FRAGMENT_MTIME_BEFORE=$(file_mtime_ns "$FRAGMENT3")
    env -i HOME="$HOME3" XDG_CONFIG_HOME="$XDG3" PATH="$SAFE_PATH" SHELL=/bin/zsh bash "$WORK/hooks-handlers/session-start.sh" >/dev/null 2>&1
    FRAGMENT_MTIME_AFTER=$(file_mtime_ns "$FRAGMENT3")
    assert_equal "$FRAGMENT_MTIME_AFTER" "$FRAGMENT_MTIME_BEFORE" "두 번째 SessionStart에서 fragment mtime 유지"
fi

# ── 4. auto-add 실패와 fragment ensure는 독립, hook 종료 코드는 0 ──
echo "[4] session-start.sh: auto-add 실패에도 fragment ensure 실행"
HOME4=$(_tmp)
XDG4="$HOME4/xdg"
env -i HOME="$HOME4" XDG_CONFIG_HOME="$XDG4" PATH="$SAFE_PATH" SHELL=/bin/zsh SENTINEL_AUTO_ADD_FAIL=1 bash "$WORK/hooks-handlers/session-start.sh" >/dev/null 2>/dev/null
STATUS4=$?
assert_equal "$STATUS4" "0" "auto-add 실패에도 SessionStart exit 0"
assert_file_exists "$XDG4/claude-account-manager/shell.sh" "auto-add 실패와 무관하게 fragment 생성"

# ── 5. fragment atomic replace 실패는 고정 경고만 stderr로 노출 ──
echo "[5] session-start.sh: fragment replace 실패 격리"
HOME5=$(_tmp)
XDG5="$HOME5/xdg"
INJECT5=$(_tmp)
cat > "$INJECT5/sitecustomize.py" <<'EOF'
import os
import sys

if sys.argv and sys.argv[0].endswith("shell_integration.py"):
    def fail_replace(source, destination):
        raise OSError(os.environ["SENTINEL_FRAGMENT_SECRET"])
    os.replace = fail_replace
EOF
SENTINEL_SECRET="sentinel-fragment-secret-do-not-expose"
STDOUT5="$HOME5/stdout"
STDERR5="$HOME5/stderr"
env -i HOME="$HOME5" XDG_CONFIG_HOME="$XDG5" PATH="$SAFE_PATH" SHELL=/bin/zsh PYTHONPATH="$INJECT5" SENTINEL_FRAGMENT_SECRET="$SENTINEL_SECRET" bash "$WORK/hooks-handlers/session-start.sh" >"$STDOUT5" 2>"$STDERR5"
STATUS5=$?
ERROR5=$(cat "$STDERR5")
EXPECTED_WARNING="account-manager: shell fragment 갱신 실패; shell rc는 변경하지 않았습니다"
assert_equal "$STATUS5" "0" "fragment replace 실패에도 SessionStart exit 0"
assert_equal "$ERROR5" "$EXPECTED_WARNING" "stderr에 고정 경고만 출력"
assert_not_contains "$ERROR5" "$SENTINEL_SECRET" "stderr에 sentinel secret 미노출"

rm -rf "$WORK" "$WORK2" "$HOME_FAKE" "$HOME2" "$HOME3" "$RC_REPO" "$HOME4" "$HOME5" "$INJECT5"

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "ALL PASS"
    exit 0
else
    echo ""
    echo "FAILURES DETECTED"
    exit 1
fi
