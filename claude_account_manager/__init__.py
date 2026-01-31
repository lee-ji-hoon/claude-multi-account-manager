"""
Claude Code Multi-Account Manager

다중 계정을 관리하는 CLI 도구입니다.
macOS Keychain을 사용하여 OAuth 토큰을 안전하게 저장합니다.
"""

__author__ = "ezhoon"

# account_manager.py의 main 함수를 패키지 수준에서 노출
import sys
import os

# 패키지 경로를 sys.path에 추가 (개발 환경에서 필요)
_package_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.dirname(_package_dir)

# account_manager.py에서 main 함수 가져오기
# 두 가지 경로 지원: 패키지 내부 또는 프로젝트 루트
try:
    from .account_manager import main, __version__
except ImportError:
    # 프로젝트 루트의 account_manager.py 사용 (하위 호환)
    if _project_dir not in sys.path:
        sys.path.insert(0, _project_dir)
    from account_manager import main, __version__

__all__ = ["main", "__version__"]
