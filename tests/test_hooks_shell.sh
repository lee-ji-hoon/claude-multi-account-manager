#!/usr/bin/env bash
# hooks-handlers 셸 스크립트 회귀 테스트 (bash 전용, python unittest 밖)
#
# 검증: 2026-07-08 lean/full 프로필 사고 — CLAUDE_CONFIG_DIR이 설정된 세션에서 hook이
# 돌면 공유 계정 저장소(~/.claude/accounts)가 엉뚱한 Keychain 네임스페이스의 토큰을
# 참조하게 되던 문제. hook은 항상 CLAUDE_CONFIG_DIR을 지우고 호출해야 하고, 셸 alias
# 생성 로직(v1/v2 → v3)도 구버전 블록을 감지해 자동 교체해야 한다.
#
# 실행: bash tests/test_hooks_shell.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

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

# ── 1. session-start.sh가 account_manager.py 호출 전 CLAUDE_CONFIG_DIR을 지우는지 ──
echo "[1] session-start.sh: CLAUDE_CONFIG_DIR unset 후 account_manager.py auto-add 호출"
WORK=$(_tmp)
mkdir -p "$WORK/hooks-handlers"
cp "$REPO_ROOT/hooks-handlers/session-start.sh" "$WORK/hooks-handlers/session-start.sh"
cat > "$WORK/account_manager.py" <<'EOF'
import os, sys
print("ARGS=" + " ".join(sys.argv[1:]))
print("CLAUDE_CONFIG_DIR=" + os.environ.get("CLAUDE_CONFIG_DIR", "<unset>"))
EOF
HOME_FAKE=$(_tmp)
OUT=$(HOME="$HOME_FAKE" SHELL=/bin/zsh CLAUDE_CONFIG_DIR="$HOME_FAKE/.claude-lean" bash "$WORK/hooks-handlers/session-start.sh" 2>&1)
assert_contains "$OUT" "ARGS=auto-add" "auto-add 호출됨"
assert_contains "$OUT" "CLAUDE_CONFIG_DIR=<unset>" "hook 내부에서 CLAUDE_CONFIG_DIR이 지워짐"

# ── 2. prompt-submit.sh도 동일 ──
echo "[2] prompt-submit.sh: CLAUDE_CONFIG_DIR unset 후 refresh-expiring 호출"
WORK2=$(_tmp)
mkdir -p "$WORK2/hooks-handlers"
cp "$REPO_ROOT/hooks-handlers/prompt-submit.sh" "$WORK2/hooks-handlers/prompt-submit.sh"
cp "$WORK/account_manager.py" "$WORK2/account_manager.py"
OUT2=$(CLAUDE_CONFIG_DIR="/tmp/some-lean-dir" bash "$WORK2/hooks-handlers/prompt-submit.sh" 2>&1)
assert_contains "$OUT2" "ARGS=refresh-expiring 1" "refresh-expiring 호출됨"
assert_contains "$OUT2" "CLAUDE_CONFIG_DIR=<unset>" "hook 내부에서 CLAUDE_CONFIG_DIR이 지워짐"

# ── 3. 구버전(v2) 마커 블록이 v3로 자동 교체되는지 ──
echo "[3] session-start.sh: v2 alias 블록 자동 교체(v3, unset 포함)"
HOME3=$(_tmp)
cat > "$HOME3/.zshrc" <<'EOF'
# 기존 사용자 설정
export FOO=bar

# >>> account-manager >>>
# account-manager-block: v2
_account_mgr_run() {
    local base="$HOME/.claude/plugins/cache/lee-ji-hoon/account"
    local latest
    latest=$(ls -1 "$base" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
    python3 "$base/$latest/account_manager.py" "$@"
}
alias account='_account_mgr_run'
alias account-switch='_account_mgr_run switch'
alias account-list='_account_mgr_run list'
# <<< account-manager <<<

# 기존 사용자 설정 끝
export BAZ=qux
EOF
HOME="$HOME3" SHELL=/bin/zsh bash "$WORK/hooks-handlers/session-start.sh" >/dev/null 2>&1
RC_CONTENT=$(cat "$HOME3/.zshrc")
assert_contains "$RC_CONTENT" "account-manager-block: v3" "v3 마커로 교체됨"
assert_not_contains "$RC_CONTENT" "account-manager-block: v2" "v2 마커 잔존 안 함"
assert_contains "$RC_CONTENT" "unset CLAUDE_CONFIG_DIR" "새 _account_mgr_run이 CLAUDE_CONFIG_DIR을 지움"
assert_contains "$RC_CONTENT" "export FOO=bar" "기존 사용자 설정(앞) 보존"
assert_contains "$RC_CONTENT" "export BAZ=qux" "기존 사용자 설정(뒤) 보존"
BLOCK_COUNT=$(grep -c "MARKER_BEGIN\|>>> account-manager >>>" "$HOME3/.zshrc")
if [ "$BLOCK_COUNT" -le 1 ]; then
    echo "  ok: 블록 중복 없음 (count=$BLOCK_COUNT)"
else
    echo "  FAIL: 블록이 중복 생성됨 (count=$BLOCK_COUNT)"
    FAIL=1
fi

# ── 4. 이미 v3인 경우 재실행해도 변화 없음(idempotent) ──
echo "[4] session-start.sh: 이미 v3면 재실행해도 그대로"
BEFORE_HASH=$(shasum "$HOME3/.zshrc")
HOME="$HOME3" SHELL=/bin/zsh bash "$WORK/hooks-handlers/session-start.sh" >/dev/null 2>&1
AFTER_HASH=$(shasum "$HOME3/.zshrc")
if [ "$BEFORE_HASH" = "$AFTER_HASH" ]; then
    echo "  ok: 재실행해도 .zshrc 변화 없음"
else
    echo "  FAIL: 이미 v3인데 .zshrc가 다시 바뀜"
    FAIL=1
fi

rm -rf "$WORK" "$WORK2" "$HOME_FAKE" "$HOME3"

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "ALL PASS"
    exit 0
else
    echo ""
    echo "FAILURES DETECTED"
    exit 1
fi
