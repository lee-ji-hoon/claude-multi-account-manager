#!/usr/bin/env bash

# Check and refresh expiring tokens on user prompt
# 사용자 메시지 입력 시 만료 임박(1시간 이내) 토큰 자동 갱신

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"

# session-start.sh와 동일한 이유로 고정: 계정 저장소는 CLAUDE_CONFIG_DIR 무관 고정 경로.
unset CLAUDE_CONFIG_DIR
python3 "$SCRIPT_DIR/account_manager.py" refresh-expiring 1 2>>"$LOG_DIR/token-refresh.log"

exit 0
