#!/usr/bin/env bash

# Auto-add current account on session start
# 이미 등록된 계정이면 조용히 스킵

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>"$LOG_DIR/token-refresh.log"

# 터미널 alias 자동 설정 (마커 기반 블록 관리)
PLUGIN_DIR="$SCRIPT_DIR"
SHELL_RC=""
if [ "$SHELL" = "/bin/zsh" ] || [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ "$SHELL" = "/bin/bash" ] || [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

MARKER_BEGIN="# >>> account-manager >>>"
MARKER_END="# <<< account-manager <<<"

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    EXPECTED_PATH="$PLUGIN_DIR/account_manager.py"

    if grep -q "$MARKER_BEGIN" "$SHELL_RC" 2>/dev/null; then
        # 마커 블록 존재 → 경로가 다를 때만 교체
        if ! grep -q "$EXPECTED_PATH" "$SHELL_RC" 2>/dev/null; then
            sed -i '' "/$MARKER_BEGIN/,/$MARKER_END/d" "$SHELL_RC"
            {
                echo ""
                echo "$MARKER_BEGIN"
                echo "alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"
                echo "alias account-switch='python3 \"$PLUGIN_DIR/account_manager.py\" switch'"
                echo "alias account-list='python3 \"$PLUGIN_DIR/account_manager.py\" list'"
                echo "$MARKER_END"
            } >> "$SHELL_RC"
        fi
    else
        # 레거시 블록 정리 (마커 없는 이전 버전)
        if grep -q "# Claude Account Manager" "$SHELL_RC" 2>/dev/null; then
            sed -i '' '/# Claude Account Manager.*터미널에서 계정 관리/d' "$SHELL_RC"
        fi
        if grep -q "^alias account=" "$SHELL_RC" 2>/dev/null; then
            sed -i '' '/^alias account=/d' "$SHELL_RC"
            sed -i '' '/^alias account-switch=/d' "$SHELL_RC"
            sed -i '' '/^alias account-list=/d' "$SHELL_RC"
        fi
        # 새 마커 블록 추가
        {
            echo ""
            echo "$MARKER_BEGIN"
            echo "alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"
            echo "alias account-switch='python3 \"$PLUGIN_DIR/account_manager.py\" switch'"
            echo "alias account-list='python3 \"$PLUGIN_DIR/account_manager.py\" list'"
            echo "$MARKER_END"
        } >> "$SHELL_RC"
    fi
fi

exit 0
