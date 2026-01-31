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
PLUGIN_VERSION="1.0.0"
PLUGIN_NAME="account-manager"
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
cp "$SCRIPT_DIR/account_manager.py" "$PLUGIN_DIR/"

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

# 4. 완료
echo -e "  ${CYAN}[4/4]${NC} 설치 확인..."

echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}✓ 설치 완료!${NC}"
echo ""
echo -e "  ${BOLD}다음 단계:${NC}"
echo -e "  ${YELLOW}Claude Code를 재시작하세요${NC}"
echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${BOLD}사용법 (Claude Code 대화창에서):${NC}"
echo -e "  ${CYAN}/account${NC}              계정 목록 + 사용량"
echo -e "  ${CYAN}/account-add 이름${NC}    현재 계정 저장"
echo -e "  ${CYAN}/account-switch${NC}      계정 전환"
echo -e "  ${CYAN}/account-check${NC}       토큰 상태 확인"
echo ""
echo -e "  ${DIM}세션 시작 시 자동으로 현재 계정이 등록됩니다.${NC}"
echo ""
