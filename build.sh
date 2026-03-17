#!/bin/bash
#
# Claude Account Manager - 빌드/배포 스크립트
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo ""
echo -e "${CYAN}Claude Account Manager - Build${NC}"
echo "──────────────────────────────────"

# 1. 심볼릭 링크를 실제 파일로 복사
echo -e "${YELLOW}[1/3]${NC} 패키지 파일 준비..."
if [ -L "claude_account_manager/account_manager.py" ]; then
    rm claude_account_manager/account_manager.py
    cp account_manager.py claude_account_manager/account_manager.py
    echo "  → account_manager.py 복사됨"
fi

# 2. 이전 빌드 정리
echo -e "${YELLOW}[2/3]${NC} 이전 빌드 정리..."
rm -rf dist/ build/ *.egg-info/

# 3. 빌드
echo -e "${YELLOW}[3/3]${NC} 패키지 빌드..."
python3 -m build

echo ""
echo -e "${GREEN}빌드 완료!${NC}"
echo ""
echo "배포 명령:"
echo "  python3 -m twine upload dist/*"
echo ""
echo "테스트 설치:"
echo "  pip install dist/*.whl"
echo ""
