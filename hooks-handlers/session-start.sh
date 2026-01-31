#!/usr/bin/env bash

# Auto-add current account on session start
# 이미 등록된 계정이면 조용히 스킵

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>/dev/null

exit 0
