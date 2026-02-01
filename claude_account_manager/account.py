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
    if org_role in ("admin", "member", "developer", "membership_admin") and org_name and "'s Organization" not in org_name:
        return "Team"
    # Pro plan: 추가 사용량 활성화된 경우
    elif has_extra:
        return "Pro"
    # Free plan: 기본
    else:
        return "Free"


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


def is_account_duplicate(email):
    """email 기준 중복 계정 확인"""
    index = load_index()
    for acc in index.get("accounts", []):
        if acc.get("email") == email:
            return True
    return False
