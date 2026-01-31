#!/bin/bash
#
# Claude Code Multi-Account Manager Uninstaller
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ACCOUNTS_DIR="$HOME/.claude/accounts"

echo ""
echo -e "${BOLD}  Claude Code Multi-Account Manager Uninstaller${NC}"
echo -e "${DIM}  ─────────────────────────────────────────────${NC}"
echo ""

# alias 제거
echo -e "  ${YELLOW}[1/1]${NC} alias 제거..."

for RC_FILE in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$RC_FILE" ]; then
        if grep -q "alias account=" "$RC_FILE" 2>/dev/null; then
            grep -v "alias account=" "$RC_FILE" > "$RC_FILE.tmp"
            mv "$RC_FILE.tmp" "$RC_FILE"
            echo -e "  ${DIM}  → $RC_FILE 에서 제거됨${NC}"
        fi
    fi
done

echo ""
echo -e "${DIM}  ─────────────────────────────────────────────${NC}"
echo -e "  ${GREEN}제거 완료!${NC}"
echo ""
echo -e "  ${DIM}참고: 계정 데이터는 보존됩니다.${NC}"
echo -e "  ${DIM}완전 삭제: rm -rf $ACCOUNTS_DIR${NC}"
echo ""
