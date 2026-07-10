#!/usr/bin/env bash

# Auto-add current account on session start
# 이미 등록된 계정이면 조용히 스킵

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"

# 이 플러그인의 계정 저장소(~/.claude/accounts)는 CLAUDE_CONFIG_DIR과 무관하게 항상 고정 경로다
# (config.py). 그런데 keychain.py의 Keychain 조회는 CLAUDE_CONFIG_DIR을 반영해 서비스명이
# 갈린다 — CLAUDE_CONFIG_DIR이 설정된 세션(예: 커스텀 프로필로 실행된 Claude Code)에서 이 hook이
# 돌면 공유 저장소에는 엉뚱한(그 프로필 전용) Keychain의 토큰이 쓰인다. hook은 항상 기본
# Keychain 네임스페이스를 봐야 저장소 가정과 일치한다.
unset CLAUDE_CONFIG_DIR
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>"$LOG_DIR/token-refresh.log"

if ! python3 "$SCRIPT_DIR/claude_account_manager/shell_integration.py" ensure-fragment 2>>"$LOG_DIR/token-refresh.log"; then
    echo "account-manager: shell fragment 갱신 실패; shell rc는 변경하지 않았습니다" >&2
fi

exit 0
