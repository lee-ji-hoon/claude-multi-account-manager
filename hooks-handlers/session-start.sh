#!/usr/bin/env bash

# Auto-add current account on session start
# 이미 등록된 계정이면 조용히 스킵

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>"$LOG_DIR/token-refresh.log"

# 터미널 alias 자동 설정 (경로 변경 시 자동 갱신)
PLUGIN_DIR="$SCRIPT_DIR"
SHELL_RC=""
if [ "$SHELL" = "/bin/zsh" ] || [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ "$SHELL" = "/bin/bash" ] || [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    ALIAS_LINE="alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"

    if grep -q "alias account=" "$SHELL_RC" 2>/dev/null; then
        # 기존 alias 존재 → 경로가 다르면 갱신
        CURRENT_ALIAS=$(grep "^alias account=" "$SHELL_RC" 2>/dev/null | head -1)
        if [ "$CURRENT_ALIAS" != "$ALIAS_LINE" ]; then
            # 기존 alias 블록 제거 후 재작성
            sed -i '' '/# Claude Account Manager/d' "$SHELL_RC"
            sed -i '' '/^alias account=/d' "$SHELL_RC"
            sed -i '' '/^alias account-switch=/d' "$SHELL_RC"
            sed -i '' '/^alias account-list=/d' "$SHELL_RC"
            {
                echo ""
                echo "# Claude Account Manager - 터미널에서 계정 관리"
                echo "alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"
                echo "alias account-switch='python3 \"$PLUGIN_DIR/account_manager.py\" switch'"
                echo "alias account-list='python3 \"$PLUGIN_DIR/account_manager.py\" list'"
            } >> "$SHELL_RC"
        fi
    else
        # alias 없음 → 새로 추가
        {
            echo ""
            echo "# Claude Account Manager - 터미널에서 계정 관리"
            echo "alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"
            echo "alias account-switch='python3 \"$PLUGIN_DIR/account_manager.py\" switch'"
            echo "alias account-list='python3 \"$PLUGIN_DIR/account_manager.py\" list'"
        } >> "$SHELL_RC"
    fi
fi

exit 0
