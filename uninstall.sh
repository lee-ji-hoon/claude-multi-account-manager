#!/bin/bash
#
# Claude Code Multi-Account Manager - Plugin Uninstaller
# Claude Code 다중 계정 관리 플러그인 제거 스크립트
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

PLUGIN_NAME="account-manager"
PLUGIN_DIR="$HOME/.claude/plugins/cache/local/$PLUGIN_NAME"
ACCOUNTS_DIR="$HOME/.claude/accounts"
INSTALLED_PLUGINS="$HOME/.claude/plugins/installed_plugins.json"

echo ""
echo -e "${BOLD}  Claude Code Multi-Account Manager 제거${NC}"
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo ""

# 1. 플러그인 등록 해제
echo -e "  ${CYAN}[1/2]${NC} 플러그인 등록 해제..."

if [ -f "$INSTALLED_PLUGINS" ]; then
    python3 << EOF
import json

path = "$INSTALLED_PLUGINS"

with open(path, 'r') as f:
    data = json.load(f)

if 'plugins' in data and '$PLUGIN_NAME@local' in data['plugins']:
    del data['plugins']['$PLUGIN_NAME@local']
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print("  플러그인 등록 해제됨")
else:
    print("  플러그인이 등록되어 있지 않음")
EOF
fi

# 2. 플러그인 파일 삭제
echo -e "  ${CYAN}[2/2]${NC} 플러그인 파일 삭제..."

if [ -d "$PLUGIN_DIR" ]; then
    rm -rf "$PLUGIN_DIR"
    echo -e "  ${DIM}  → $PLUGIN_DIR 삭제됨${NC}"
else
    echo -e "  ${DIM}  → 플러그인 디렉토리 없음${NC}"
fi

echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}✓ 제거 완료!${NC}"
echo ""
echo -e "  ${BOLD}참고:${NC}"
echo -e "  ${DIM}계정 데이터는 유지됩니다: $ACCOUNTS_DIR${NC}"
echo ""
echo -e "  ${DIM}데이터도 삭제하려면:${NC}"
echo -e "  ${CYAN}rm -rf $ACCOUNTS_DIR${NC}"
echo ""
echo -e "  ${YELLOW}Claude Code를 재시작하세요${NC}"
echo ""
