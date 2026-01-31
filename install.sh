#!/bin/bash
#
# Claude Code Multi-Account Manager Installer
# 다중 계정 관리 설치 스크립트
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
CLAUDE_DIR="$HOME/.claude"
ACCOUNTS_DIR="$CLAUDE_DIR/accounts"
ALIAS_CMD="alias account=\"python3 $SCRIPT_DIR/account_manager.py\""

echo ""
echo -e "${BOLD}  Claude Code Multi-Account Manager${NC}"
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo ""

# 디렉토리 생성
echo -e "  ${CYAN}[1/3]${NC} 디렉토리 생성..."
mkdir -p "$ACCOUNTS_DIR"

# accounts 디렉토리 권한 설정
echo -e "  ${CYAN}[2/3]${NC} 보안 설정..."
chmod 700 "$ACCOUNTS_DIR"

# index.json 초기화 (없는 경우에만)
if [ ! -f "$ACCOUNTS_DIR/index.json" ]; then
    echo '{"version": 1, "accounts": [], "activeAccountId": null}' > "$ACCOUNTS_DIR/index.json"
fi

# alias 추가
echo -e "  ${CYAN}[3/3]${NC} alias 등록..."

# 사용 중인 쉘 확인
SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ "$SHELL" = "/bin/zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ "$SHELL" = "/bin/bash" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    # 기존 alias 제거 후 새로 추가
    grep -v "alias account=" "$SHELL_RC" > "$SHELL_RC.tmp" 2>/dev/null || true
    mv "$SHELL_RC.tmp" "$SHELL_RC"
    echo "$ALIAS_CMD" >> "$SHELL_RC"
    echo -e "  ${DIM}  → $SHELL_RC 에 추가됨${NC}"
fi

echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}설치 완료!${NC}"
echo ""
echo -e "  ${BOLD}즉시 사용하기:${NC}"
echo -e "  ${DIM}다음 중 하나를 실행하세요:${NC}"
echo ""
echo -e "    ${CYAN}source $SHELL_RC${NC}"
echo ""
echo -e "  ${DIM}또는 아래 명령 복사 후 붙여넣기:${NC}"
echo ""
echo -e "    ${CYAN}$ALIAS_CMD${NC}"
echo ""
echo -e "${DIM}  ─────────────────────────────────────${NC}"
echo -e "  ${BOLD}사용법:${NC}"
echo -e "  ${CYAN}account${NC}              계정 목록 + 사용량"
echo -e "  ${CYAN}account add 이름${NC}    현재 계정 저장"
echo -e "  ${CYAN}account switch${NC}      계정 전환 (대화형)"
echo -e "  ${CYAN}account check${NC}       토큰 상태 확인"
echo -e "  ${CYAN}account help${NC}        전체 도움말"
echo ""
