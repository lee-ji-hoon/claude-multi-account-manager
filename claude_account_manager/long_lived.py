"""
Long-lived OAuth token (claude setup-token) 전용 유틸
"""
from datetime import datetime, timedelta


LONG_LIVED_VALIDITY_DAYS = 365
EXPIRY_WARN_DAYS = 30
EXPIRY_DANGER_DAYS = 7


def validate_token_format(token):
    """long-lived 토큰 포맷 검증

    `claude setup-token`이 발급하는 토큰은 sk-ant- prefix를 가진다.
    구체적 sub-prefix(oat01 등)는 시간이 지나며 바뀔 수 있으므로 sk-ant- 만 검증.
    """
    if not token:
        return False
    if not isinstance(token, str):
        return False
    stripped = token.strip()
    if not stripped:
        return False
    return stripped.startswith("sk-ant-")


def plan_to_subscription_type(plan):
    """Plan name → (subscriptionType, rateLimitTier) 매핑

    detect_plan_from_credential의 역방향. 사용자 입력 Plan으로부터
    credential의 subscriptionType과 rateLimitTier를 생성한다.
    """
    plan_map = {
        "Max20": ("max", "default_claude_max_20x"),
        "Max5": ("max", "default_claude_max_5x"),
        "Pro": ("pro", ""),
        "Team": ("team", ""),
        "Free": ("free", ""),
    }
    return plan_map.get(plan, ("free", ""))


def wrap_long_lived_token(token, plan, validity_days=LONG_LIVED_VALIDITY_DAYS):
    """long-lived 토큰을 claudeAiOauth schema로 wrap

    refreshToken은 빈 문자열(없음 의미). expiresAt은 발급 시점 + validity_days.
    Plan에 따라 subscriptionType/rateLimitTier를 채운다.
    """
    sub_type, rate_tier = plan_to_subscription_type(plan)
    expires_at_ms = int((datetime.now() + timedelta(days=validity_days)).timestamp() * 1000)
    return {
        "claudeAiOauth": {
            "accessToken": token.strip(),
            "refreshToken": "",
            "expiresAt": expires_at_ms,
            "subscriptionType": sub_type,
            "rateLimitTier": rate_tier,
        }
    }


def is_long_lived_account(account_entry):
    """account index entry가 long-lived 계정인지 판정

    tokenType 필드가 없으면 oauth (backward compat).
    """
    if not account_entry:
        return False
    return account_entry.get("tokenType", "oauth") == "long-lived"


def format_expiry_dday(expires_at_ms):
    """만료까지 D-day와 severity 레벨 반환

    Returns:
        tuple[str, str]: (라벨, severity)
        severity: "normal" | "warn" | "danger" | "expired"
    """
    if not expires_at_ms:
        return ("?", "normal")
    expires = datetime.fromtimestamp(expires_at_ms / 1000)
    delta = expires - datetime.now()
    days = delta.days
    if delta.total_seconds() < 0 and days < 0:
        return ("만료됨", "expired")
    label = f"D-{days}"
    if days <= EXPIRY_DANGER_DAYS:
        severity = "danger"
    elif days <= EXPIRY_WARN_DAYS:
        severity = "warn"
    else:
        severity = "normal"
    return (label, severity)
