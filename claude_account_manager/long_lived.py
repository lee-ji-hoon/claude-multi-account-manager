"""
Long-lived OAuth token (claude setup-token) 전용 유틸
"""


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
