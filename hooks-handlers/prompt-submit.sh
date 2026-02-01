#!/usr/bin/env bash

# Check and refresh expiring tokens on user prompt
# 사용자 메시지 입력 시 만료 임박(1시간 이내) 토큰 자동 갱신

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
python3 "$SCRIPT_DIR/account_manager.py" refresh-expiring 1 2>/dev/null

exit 0
