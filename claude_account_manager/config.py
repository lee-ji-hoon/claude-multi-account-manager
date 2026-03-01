"""
Configuration constants and paths for Claude Account Manager
"""
import json
from pathlib import Path


def _get_version():
    """plugin.json에서 버전 읽기"""
    try:
        plugin_json = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        if plugin_json.exists():
            data = json.loads(plugin_json.read_text())
            return data.get("version", "0.0.0")
    except Exception:
        pass
    return "0.0.0"


__version__ = _get_version()
PACKAGE_NAME = "claude-account-manager"

# Path constants
CLAUDE_JSON = Path.home() / ".claude.json"
CLAUDE_DIR = Path.home() / ".claude"
ACCOUNTS_DIR = CLAUDE_DIR / "accounts"
INDEX_FILE = ACCOUNTS_DIR / "index.json"
STATS_CACHE = CLAUDE_DIR / "stats-cache.json"
USAGE_CACHE = CLAUDE_DIR / "plugins" / "claude-hud" / ".usage-cache.json"
VERSION_CACHE = ACCOUNTS_DIR / ".version-cache.json"

# Plan별 대략적인 일일 토큰 한도 (참고용)
PLAN_LIMITS_DAILY = {
    "Free": 100_000,
    "Pro": 500_000,
    "Team": 1_000_000,
    "Max5": 2_000_000,    # Max 5 프로젝트
    "Max20": 5_000_000,   # Max 20 프로젝트
    "Max": 2_000_000,     # 하위 호환 (Max5와 동일)
    "Unknown": 100_000,
}

# Plan별 대략적인 주간 토큰 한도 (참고용)
PLAN_LIMITS_WEEKLY = {
    "Free": 500_000,
    "Pro": 2_500_000,
    "Team": 5_000_000,
    "Max5": 10_000_000,   # Max 5 프로젝트
    "Max20": 25_000_000,  # Max 20 프로젝트
    "Max": 10_000_000,    # 하위 호환 (Max5와 동일)
    "Unknown": 500_000,
}

# 리셋 주기 (시간)
RESET_HOURS = {
    "Free": 4,
    "Pro": 5,
    "Team": 5,
    "Max5": 5,
    "Max20": 5,
    "Max": 5,  # 하위 호환
    "Unknown": 5,
}

# OAuth 토큰 설정
TOKEN_VALIDITY_HOURS = 8       # 토큰 유효기간 (시간)
TOKEN_FRESH_THRESHOLD_HOURS = 7  # 토큰 신선도 기준 (시간)
