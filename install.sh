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
PLUGIN_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$SCRIPT_DIR/.claude-plugin/plugin.json")"
PLUGIN_NAME="account"
PLUGIN_DIR="$HOME/.claude/plugins/cache/local/$PLUGIN_NAME/$PLUGIN_VERSION"
ACCOUNTS_DIR="$HOME/.claude/accounts"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
SHELL_INTEGRATION="$PLUGIN_DIR/claude_account_manager/shell_integration.py"

echo ""
echo -e "${BOLD}  Claude Code Multi-Account Manager${NC}"
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo ""

# 1. 계정 디렉토리 생성
echo -e "  ${CYAN}[1/5]${NC} 계정 디렉토리 생성..."
mkdir -p "$ACCOUNTS_DIR"
chmod 700 "$ACCOUNTS_DIR"

if [ ! -f "$ACCOUNTS_DIR/index.json" ]; then
    echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$ACCOUNTS_DIR/index.json"
fi

# 2. 플러그인 디렉토리 생성 및 복사
echo -e "  ${CYAN}[2/5]${NC} 플러그인 파일 복사..."
mkdir -p "$PLUGIN_DIR"

# 필요한 파일들 복사
cp -r "$SCRIPT_DIR/.claude-plugin" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/hooks" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/hooks-handlers" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/claude_account_manager" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/skills" "$PLUGIN_DIR/"
cp -r "$SCRIPT_DIR/bin" "$PLUGIN_DIR/"
cp "$SCRIPT_DIR/account_manager.py" "$PLUGIN_DIR/"

# __pycache__ 제외하고 정리
find "$PLUGIN_DIR/claude_account_manager" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 실행 권한 설정
chmod +x "$PLUGIN_DIR/hooks-handlers/session-start.sh"

# 3. installed_plugins.json에 등록
echo -e "  ${CYAN}[3/5]${NC} 플러그인 등록..."

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

# 4. runtime fragment 생성 및 shell source block 설치
echo -e "  ${CYAN}[4/5]${NC} shell integration 설정..."

python3 "$SHELL_INTEGRATION" ensure-fragment

# 사용자 shell 확인
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

SOURCE_CONFIGURED=false
if [ -n "$SHELL_RC" ] && { [ -f "$SHELL_RC" ] || [ -L "$SHELL_RC" ]; }; then
    if python3 "$SHELL_INTEGRATION" install-rc "$SHELL_RC"; then
        SOURCE_CONFIGURED=true
        echo -e "    ${GREEN}✓${NC} $SHELL_RC source 설정 확인됨"
    else
        SHELL_STATUS=$?
        if [ "$SHELL_STATUS" -eq 3 ]; then
            echo -e "    ${YELLOW}!${NC} 사용자 소유 shell 설정 파일은 자동 수정하지 않습니다"
            echo -e "    ${DIM}아래 block을 직접 추가하세요:${NC}"
            python3 -c 'import runpy,sys; sys.stdout.write(runpy.run_path(sys.argv[1])["SOURCE_BLOCK"])' "$SHELL_INTEGRATION"
        fi
        exit "$SHELL_STATUS"
    fi
else
    echo -e "    ${YELLOW}!${NC} shell 설정 파일을 찾을 수 없습니다"
    echo -e "    ${DIM}runtime fragment는 생성했으며 shell rc는 변경하지 않았습니다${NC}"
fi

# 5. 완료
echo -e "  ${CYAN}[5/5]${NC} 설치 확인..."

echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}✓ 설치 완료!${NC}"

if [ "$SOURCE_CONFIGURED" = true ]; then
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
echo -e "  ${BOLD}🚨 토큰 소진 시 (Claude가 응답 안 할 때):${NC}"
echo -e "  ${CYAN}account-switch${NC}       터미널에서 계정 전환"
echo -e "  ${CYAN}account-list${NC}         터미널에서 계정 목록"
echo ""
echo -e "  ${DIM}세션 시작 시 자동으로 현재 계정이 등록됩니다.${NC}"
echo ""
