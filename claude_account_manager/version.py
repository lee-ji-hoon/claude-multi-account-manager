"""
Version checking and update notifications
"""
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta

from .config import __version__, PACKAGE_NAME, VERSION_CACHE
from .storage import ensure_accounts_dir
from .ui import c, Colors


def check_for_updates(silent=True):
    """PyPI에서 최신 버전 확인 (24시간 캐시)"""
    # 캐시 확인
    if VERSION_CACHE.exists():
        try:
            cache = json.loads(VERSION_CACHE.read_text())
            cache_time = datetime.fromisoformat(cache.get("checked_at", "1970-01-01"))
            if datetime.now() - cache_time < timedelta(hours=24):
                # 캐시가 유효하면 사용
                latest = cache.get("latest_version")
                if latest and latest != __version__:
                    return latest
                return None
        except (json.JSONDecodeError, ValueError):
            pass

    # PyPI API 호출
    try:
        req = urllib.request.Request(
            f"https://pypi.org/pypi/{PACKAGE_NAME}/json",
            headers={"User-Agent": f"claude-account-manager/{__version__}"},
        )

        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                latest = data.get("info", {}).get("version")

                # 캐시 저장
                ensure_accounts_dir()
                VERSION_CACHE.write_text(json.dumps({
                    "latest_version": latest,
                    "checked_at": datetime.now().isoformat(),
                }, indent=2))

                if latest and latest != __version__:
                    return latest

    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass

    return None


def notify_update_available(latest_version):
    """업데이트 알림 표시"""
    print()
    print(c(Colors.YELLOW, "  ─────────────────────────────────────"))
    print(f"  {c(Colors.YELLOW, '⬆')} 새 버전 사용 가능: {c(Colors.GREEN, latest_version)} (현재: {__version__})")
    print(f"  {c(Colors.DIM, '업데이트:')} pip install --upgrade {PACKAGE_NAME}")
    print(c(Colors.YELLOW, "  ─────────────────────────────────────"))
