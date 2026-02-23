#!/usr/bin/env bash

# Check and refresh expiring tokens on user prompt
# 사용자 메시지 입력 시 만료 임박(1시간 이내) 토큰 자동 갱신

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"
python3 "$SCRIPT_DIR/account_manager.py" refresh-expiring 1 2>>"$LOG_DIR/token-refresh.log"

exit 0
