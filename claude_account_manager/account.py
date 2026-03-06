"""
Account business logic: plan detection, duplicate checking, name generation
"""
import re
from datetime import datetime

from .storage import load_index


def estimate_plan(oauth_account):
    """oauthAccount 정보로 Plan 추정"""
    if not oauth_account:
        return "Unknown"

    has_extra = oauth_account.get("hasExtraUsageEnabled", False)
    org_role = oauth_account.get("organizationRole", "")
    org_name = oauth_account.get("organizationName", "")

    # Team plan: organization에 속하고 역할이 있는 경우
    if org_role in ("admin", "member", "developer", "membership_admin") and org_name and _is_real_org(org_name):
        return "Team"
    # Pro plan: 추가 사용량 활성화된 경우
    elif has_extra:
        return "Pro"
    # Free plan: 기본
    else:
        return "Free"


def _is_real_org(org_name):
    """개인 조직이 아닌 실제 Team/Organization인지 확인"""
    return bool(org_name) and "'s Organization" not in org_name


def detect_plan_from_credential(credential):
    """credential에서 Plan 자동 감지

    우선순위:
    1. rateLimitTier에서 max_5x/max_20x 감지 → Max5/Max20
    2. subscriptionType에서 team/pro/max 감지 → Team/Pro/Max5
    3. 기본값 → Free
    """
    oauth = credential.get("claudeAiOauth", {})
    subscription_type = oauth.get("subscriptionType", "").lower()
    rate_limit_tier = oauth.get("rateLimitTier", "").lower()

    # rateLimitTier 우선 (Max 플랜 구분에 정확)
    if "max_20" in rate_limit_tier or "max20" in rate_limit_tier:
        return "Max20"
    elif "max_5" in rate_limit_tier or "max5" in rate_limit_tier:
        return "Max5"

    # subscriptionType 기반
    if "team" in subscription_type:
        return "Team"
    elif "pro" in subscription_type:
        return "Pro"
    elif "max" in subscription_type:
        match = re.search(r'max[_\s-]?(\d+)', subscription_type)
        if match:
            num = int(match.group(1))
            return "Max20" if num >= 20 else "Max5"
        return "Max5"

    return "Free"


def generate_account_name(oauth_account, email):
    """계정 이름 자동 생성

    우선순위:
    1. oauthAccount.displayName
    2. email의 username 부분
    3. "Account_{timestamp}" fallback
    """
    # displayName 시도
    display_name = oauth_account.get("displayName", "").strip()
    if display_name:
        return display_name

    # email username 시도
    if email and "@" in email:
        username = email.split("@")[0]
        if username:
            return username

    # timestamp fallback
    return f"Account_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_account_id(email, org_name=None, org_uuid=None):
    """email과 organization으로 고유 account_id 생성

    Team/Organization 계정은 org 이름을 suffix로 추가하여 동일 이메일 구분.
    동일 org 이름(case-insensitive)이지만 UUID가 다른 경우 UUID 앞 8자를 추가하여 충돌 방지.
    개인 계정은 email만 사용 (기존 호환).
    """
    base = email.split("@")[0].replace(".", "_").replace("+", "_").lower()
    if _is_real_org(org_name):
        org_suffix = re.sub(r'[^a-z0-9]', '_', org_name.lower()).strip('_')
        org_suffix = re.sub(r'_+', '_', org_suffix)
        candidate = f"{base}_{org_suffix}"
        if org_uuid and _has_id_conflict(candidate, org_uuid):
            org_suffix += f"_{org_uuid[:8]}"
        return f"{base}_{org_suffix}"
    return base


def _has_id_conflict(candidate_id, org_uuid):
    """동일 account_id가 이미 존재하면서 UUID가 다른 경우 충돌 감지"""
    index = load_index()
    for acc in index.get("accounts", []):
        if acc.get("id") == candidate_id:
            stored_uuid = acc.get("organizationUuid", "")
            if stored_uuid and stored_uuid != org_uuid:
                return True
    return False


def is_account_duplicate(email, org_uuid=None):
    """email + organizationUuid 기준 중복 계정 확인

    동일 이메일이라도 다른 Organization이면 별도 계정으로 취급.
    """
    index = load_index()
    for acc in index.get("accounts", []):
        if acc.get("email") != email:
            continue
        stored_org = acc.get("organizationUuid")
        if stored_org and org_uuid:
            if stored_org == org_uuid:
                return True
            continue
        if not stored_org and not org_uuid:
            return True
    return False


def is_same_account(acc, current_oauth):
    """저장된 계정(index entry)과 현재 oauthAccount가 동일한지 확인

    organizationUuid가 저장된 계정은 email + org로 비교.
    Legacy 계정(org 미저장)은 email만으로 비교.
    """
    if acc.get("email") != current_oauth.get("emailAddress", ""):
        return False
    stored_org = acc.get("organizationUuid")
    if stored_org:
        return stored_org == current_oauth.get("organizationUuid", "")
    return True


def get_org_info(oauth_account):
    """oauthAccount에서 organization 정보 추출

    Returns:
        tuple: (org_name, org_uuid) - 없으면 ("", "")
    """
    if not oauth_account:
        return "", ""
    return (
        oauth_account.get("organizationName", ""),
        oauth_account.get("organizationUuid", ""),
    )
