#!/usr/bin/env bash

# Auto-add current account on session start
# 이미 등록된 계정이면 조용히 스킵

SCRIPT_DIR="$(dirname "$(dirname "$0")")"
LOG_DIR="$HOME/.claude/accounts/logs"
mkdir -p "$LOG_DIR"
python3 "$SCRIPT_DIR/account_manager.py" auto-add 2>>"$LOG_DIR/token-refresh.log"

# 터미널 alias 자동 설정 (마커 기반 블록 관리, version-agnostic)
SHELL_RC=""
if [ "$SHELL" = "/bin/zsh" ] || [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ "$SHELL" = "/bin/bash" ] || [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

# 심볼릭 링크 해석 (sed -i는 심링크에서 실패하므로 실제 파일 경로 사용)
if [ -n "$SHELL_RC" ] && [ -L "$SHELL_RC" ]; then
    SHELL_RC="$(cd "$(dirname "$SHELL_RC")" && cd "$(dirname "$(readlink "$SHELL_RC")")" && pwd)/$(basename "$(readlink "$SHELL_RC")")"
fi

MARKER_BEGIN="# >>> account-manager >>>"
MARKER_END="# <<< account-manager <<<"
BLOCK_VERSION_TAG="# account-manager-block: v2"

write_v2_block() {
    local rc="$1"
    {
        echo ""
        echo "$MARKER_BEGIN"
        echo "$BLOCK_VERSION_TAG"
        echo "# 항상 최신 설치 버전을 자동 선택 (플러그인 업데이트 시 재설정 불필요)"
        echo "_account_mgr_run() {"
        echo "    local base=\"\$HOME/.claude/plugins/cache/lee-ji-hoon/account\""
        echo "    local latest"
        echo "    latest=\$(ls -1 \"\$base\" 2>/dev/null | grep -E '^[0-9]+\\.[0-9]+\\.[0-9]+\$' | sort -V | tail -1)"
        echo "    if [ -z \"\$latest\" ] || [ ! -f \"\$base/\$latest/account_manager.py\" ]; then"
        echo "        echo \"account: plugin not found in \$base\" >&2"
        echo "        return 1"
        echo "    fi"
        echo "    python3 \"\$base/\$latest/account_manager.py\" \"\$@\""
        echo "}"
        echo "alias account='_account_mgr_run'"
        echo "alias account-switch='_account_mgr_run switch'"
        echo "alias account-list='_account_mgr_run list'"
        echo "$MARKER_END"
    } >> "$rc"
}

if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    if grep -q "$MARKER_BEGIN" "$SHELL_RC" 2>/dev/null; then
        # 마커 블록 존재 → v2 여부 확인
        if grep -q "$BLOCK_VERSION_TAG" "$SHELL_RC" 2>/dev/null; then
            : # 이미 v2 → 재설치/업데이트에도 손댈 필요 없음
        else
            # v1 (경로 박힌 alias) → v2로 교체
            sed -i '' "/$MARKER_BEGIN/,/$MARKER_END/d" "$SHELL_RC"
            write_v2_block "$SHELL_RC"
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
        write_v2_block "$SHELL_RC"
    fi
fi

exit 0
