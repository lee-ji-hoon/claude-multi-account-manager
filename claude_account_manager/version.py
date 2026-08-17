"""
Version checking and update notifications
"""
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta

from .config import __version__, VERSION_CACHE
from .storage import ensure_accounts_dir
from .ui import c, Colors


RELEASE_API = "https://api.github.com/repos/lee-ji-hoon/ai-account-switcher/releases/latest"
UPDATE_COMMAND = "/plugin update account@lee-ji-hoon"
CACHE_SOURCE = "github-releases"


def _version_key(version):
    """Return a comparable numeric release tuple, or None for unknown tags."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(version or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _is_newer_version(candidate, current):
    candidate_key = _version_key(candidate)
    current_key = _version_key(current)
    return bool(candidate_key and current_key and candidate_key > current_key)


def check_for_updates(silent=True):
    """GitHub Releases에서 최신 버전 확인 (24시간 캐시)."""
    # 캐시 확인
    if VERSION_CACHE.exists():
        try:
            cache = json.loads(VERSION_CACHE.read_text())
            cache_time = datetime.fromisoformat(cache.get("checked_at", "1970-01-01"))
            if (
                cache.get("source") == CACHE_SOURCE
                and datetime.now() - cache_time < timedelta(hours=24)
            ):
                # 캐시가 유효하면 사용
                latest = cache.get("latest_version")
                if _is_newer_version(latest, __version__):
                    return latest
                return None
        except (json.JSONDecodeError, ValueError):
            pass

    # 이 저장소의 GitHub Release만 조회한다. 같은 이름의 제3자 패키지를
    # 설치하도록 안내하지 않기 위한 명시적인 신뢰 경계다.
    try:
        req = urllib.request.Request(
            RELEASE_API,
            headers={"User-Agent": f"switchboard/{__version__}"},
        )

        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                release_tag = str(data.get("tag_name", ""))
                latest = release_tag[1:] if release_tag.startswith("v") else release_tag

                # 캐시 저장
                ensure_accounts_dir()
                VERSION_CACHE.write_text(json.dumps({
                    "latest_version": latest,
                    "checked_at": datetime.now().isoformat(),
                    "source": CACHE_SOURCE,
                }, indent=2))

                if _is_newer_version(latest, __version__):
                    return latest

    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass

    return None


def notify_update_available(latest_version):
    """업데이트 알림 표시"""
    print()
    print(c(Colors.YELLOW, "  ─────────────────────────────────────"))
    print(f"  {c(Colors.YELLOW, '⬆')} 새 버전 사용 가능: {c(Colors.GREEN, latest_version)} (현재: {__version__})")
    print(f"  {c(Colors.DIM, '업데이트:')} {UPDATE_COMMAND}")
    print(c(Colors.YELLOW, "  ─────────────────────────────────────"))
