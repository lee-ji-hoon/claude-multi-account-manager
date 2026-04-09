#!/bin/bash
#
# Claude Code Multi-Account Manager - Plugin Installer
# Claude Code 다중 계정 관리 플러그인 설치 스크립트
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_VERSION="2.1.4"
PLUGIN_NAME="account"
PLUGIN_DIR="$HOME/.claude/plugins/cache/local/$PLUGIN_NAME/$PLUGIN_VERSION"
ACCOUNTS_DIR="$HOME/.claude/accounts"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"

echo ""
echo -e "${BOLD}  Claude Code Multi-Account Manager${NC}"
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo ""

# 1. 계정 디렉토리 생성
echo -e "  ${CYAN}[1/4]${NC} 계정 디렉토리 생성..."
mkdir -p "$ACCOUNTS_DIR"
chmod 700 "$ACCOUNTS_DIR"

if [ ! -f "$ACCOUNTS_DIR/index.json" ]; then
    echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$ACCOUNTS_DIR/index.json"
fi

# 2. 플러그인 디렉토리 생성 및 복사
echo -e "  ${CYAN}[2/4]${NC} 플러그인 파일 복사..."
mkdir -p "$PLUGIN_DIR"

# 필요한 파일들 복사
cp -r "$SCRIPT_DIR/.claude-plugin" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/commands" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/hooks" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/hooks-handlers" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/claude_account_manager" "$PLUGIN_DIR/"
cp "$SCRIPT_DIR/account_manager.py" "$PLUGIN_DIR/"

# __pycache__ 제외하고 정리
find "$PLUGIN_DIR/claude_account_manager" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 실행 권한 설정
chmod +x "$PLUGIN_DIR/hooks-handlers/session-start.sh"

# 3. installed_plugins.json에 등록
echo -e "  ${CYAN}[3/4]${NC} 플러그인 등록..."

# installed_plugins.json이 없으면 생성
if [ ! -f "$INSTALLED_PLUGINS" ]; then
    mkdir -p "$(dirname "$INSTALLED_PLUGINS")"
    echo '{"version": 2, "plugins": {}}' > "$INSTALLED_PLUGINS"
fi

# Python으로 JSON 업데이트
python3 << EOF
import json
import os
from datetime import datetime, timezone

path = "$INSTALLED_PLUGINS"
plugin_path = "$PLUGIN_DIR"

with open(path, 'r') as f:
    data = json.load(f)

if 'plugins' not in data:
    data['plugins'] = {}

data['plugins']['$PLUGIN_NAME@local'] = [{
    'scope': 'user',
    'installPath': plugin_path,
    'version': '$PLUGIN_VERSION',
    'installedAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'lastUpdated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
}]

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
EOF

# 4. 터미널 alias 설정 (마커 기반 블록 관리)
echo -e "  ${CYAN}[4/5]${NC} 터미널 alias 설정..."

# 사용자 shell 확인
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

MARKER_BEGIN="# >>> account-manager >>>"
MARKER_END="# <<< account-manager <<<"

ALIAS_ADDED=false
if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
    # 기존 마커 블록 또는 레거시 블록 제거
    if grep -q "$MARKER_BEGIN" "$SHELL_RC" 2>/dev/null; then
        sed -i '' "/$MARKER_BEGIN/,/$MARKER_END/d" "$SHELL_RC"
    fi
    if grep -q "# Claude Account Manager" "$SHELL_RC" 2>/dev/null; then
        sed -i '' '/# Claude Account Manager.*터미널에서 계정 관리/d' "$SHELL_RC"
    fi
    if grep -q "^alias account=" "$SHELL_RC" 2>/dev/null; then
        sed -i '' '/^alias account=/d' "$SHELL_RC"
        sed -i '' '/^alias account-switch=/d' "$SHELL_RC"
        sed -i '' '/^alias account-list=/d' "$SHELL_RC"
        sed -i '' '/^alias cl=/d' "$SHELL_RC"
    fi

    # 새 마커 블록 추가
    {
        echo ""
        echo "$MARKER_BEGIN"
        echo "alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'"
        echo "alias account-switch='python3 \"$PLUGIN_DIR/account_manager.py\" switch'"
        echo "alias account-list='python3 \"$PLUGIN_DIR/account_manager.py\" list'"
        echo "alias cl='python3 \"$PLUGIN_DIR/bin/claude-launch\"'"
        echo "$MARKER_END"
    } >> "$SHELL_RC"
    ALIAS_ADDED=true
    echo -e "    ${GREEN}✓${NC} $SHELL_RC에 alias 설정됨"
else
    echo -e "    ${YELLOW}!${NC} shell 설정 파일을 찾을 수 없습니다"
    echo -e "    ${DIM}수동으로 추가하세요: alias account='python3 \"$PLUGIN_DIR/account_manager.py\"'${NC}"
fi

# 5. 완료
echo -e "  ${CYAN}[5/5]${NC} 설치 확인..."

echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}✓ 설치 완료!${NC}"

if [ "$ALIAS_ADDED" = true ]; then
    echo ""
    echo -e "  ${YELLOW}⚠ 터미널을 재시작하거나 'source $SHELL_RC' 실행${NC}"
fi

echo ""
echo -e "  ${BOLD}다음 단계:${NC}"
echo -e "  ${YELLOW}Claude Code를 재시작하세요${NC}"
echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${BOLD}사용법 (Claude Code 대화창에서):${NC}"
echo -e "  ${CYAN}/account:list${NC}         계정 목록 + 사용량"
echo -e "  ${CYAN}/account:add 이름${NC}     현재 계정 저장"
echo -e "  ${CYAN}/account:switch${NC}       계정 전환"
echo -e "  ${CYAN}/account:check${NC}        토큰 상태 확인"
echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${BOLD}🚀 빠른 시작:${NC}"
echo -e "  ${CYAN}cl${NC}                   런처 (계정 선택 + 세션 관리)"
echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${BOLD}🚨 토큰 소진 시 (Claude가 응답 안 할 때):${NC}"
echo -e "  ${CYAN}account-switch${NC}       터미널에서 계정 전환"
echo -e "  ${CYAN}account-list${NC}         터미널에서 계정 목록"
echo ""
echo -e "  ${DIM}세션 시작 시 자동으로 현재 계정이 등록됩니다.${NC}"
echo ""
