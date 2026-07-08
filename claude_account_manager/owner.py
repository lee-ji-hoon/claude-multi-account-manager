"""
토큰 소유자 검증: credential의 access token이 실제로 어느 계정 소유인지 확인

~/.claude.json(oauthAccount)과 Keychain은 서로 다른 저장소라 switch나 /login 직후
잠깐 서로 어긋날 수 있다. 이 desync 윈도우에 hook이 Keychain 토큰을 "현재 계정"
슬롯에 저장하면 다른 계정의 토큰이 슬롯에 들어가는 교차 오염이 발생한다
(2026-07-08 실사고: switch 직후 gmail 토큰이 soop 슬롯에 저장됨).
슬롯에 credential을 쓰기 전 반드시 이 모듈로 소유자를 검증한다.
"""
import hashlib
import json
import urllib.request

from .config import ACCOUNTS_DIR
from .logger import log

OWNER_CACHE_FILE = ACCOUNTS_DIR / ".token-owner-cache.json"
OWNER_CACHE_MAX = 50


def _load_owner_cache():
    try:
        if OWNER_CACHE_FILE.exists():
            return json.loads(OWNER_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_owner_cache(cache):
    try:
        if len(cache) > OWNER_CACHE_MAX:
            cache = dict(list(cache.items())[-OWNER_CACHE_MAX:])
        OWNER_CACHE_FILE.write_text(json.dumps(cache))
    except Exception:
        pass


def fetch_token_owner(credential):
    """access token의 소유 계정/조직 조회 (profile API)

    토큰→소유자 매핑은 불변이므로 토큰 해시 키로 캐시 (신규 토큰당 API 1회).

    Returns:
        dict: {"uuid", "email", "org_uuid"} 또는 None(조회 실패)
    """
    oauth = (credential or {}).get("claudeAiOauth", {})
    token = oauth.get("accessToken")
    if not token:
        return None

    key = hashlib.sha256(token.encode()).hexdigest()[:16]
    cache = _load_owner_cache()
    if key in cache:
        return cache[key]

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/profile",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            profile = json.loads(response.read().decode())
    except Exception as e:
        log("WARN", f"owner: profile 조회 실패 - {e}")
        return None

    account = profile.get("account") or {}
    organization = profile.get("organization") or {}
    owner = {
        "uuid": account.get("uuid", ""),
        "email": (account.get("email") or "").lower(),
        "org_uuid": organization.get("uuid", ""),
    }
    if not owner["uuid"] and not owner["email"]:
        return None

    cache[key] = owner
    _save_owner_cache(cache)
    return owner


def credential_matches_identity(credential, email, account_uuid="", org_uuid=""):
    """credential 토큰이 기대 계정(email/uuid) + 조직 컨텍스트 소유인지 검증

    Returns:
        True  — 소유자 일치 (저장 안전)
        False — 소유자 불일치 (교차 오염 위험, 저장 금지)
        None  — 판별 불가 (네트워크 오류 등 — 호출부는 저장을 미루고 재시도)
    """
    owner = fetch_token_owner(credential)
    if not owner:
        return None

    # 계정 정체성: uuid 우선, 없으면 email
    if account_uuid and owner["uuid"]:
        if owner["uuid"] != account_uuid:
            return False
    elif email and owner["email"]:
        if owner["email"] != email.lower():
            return False
    else:
        return None

    # 같은 계정이라도 조직 컨텍스트가 다르면 다른 슬롯 (동일 이메일 다중 org)
    if org_uuid and owner["org_uuid"] and owner["org_uuid"] != org_uuid:
        return False

    return True


def credential_matches_slot(credential, acc):
    """index entry(acc) 슬롯 기준 소유자 검증 — profile 파일에서 accountUuid 보강"""
    account_uuid = ""
    profile_file = acc.get("profileFile")
    if profile_file:
        try:
            profile = json.loads((ACCOUNTS_DIR / profile_file).read_text())
            account_uuid = profile.get("accountUuid", "")
        except Exception:
            pass
    return credential_matches_identity(
        credential,
        acc.get("email", ""),
        account_uuid=account_uuid,
        org_uuid=acc.get("organizationUuid", ""),
    )
