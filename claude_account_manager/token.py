"""
OAuth token management: expiration, refresh, status checking
"""
import json
import os
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from .config import TOKEN_VALIDITY_HOURS, TOKEN_FRESH_THRESHOLD_HOURS
from .keychain import get_keychain_credential, set_keychain_credential
from .logger import log, log_token_info


class TokenStatus:
    """토큰 상태 상수"""
    VALID = "valid"
    EXPIRED = "expired"      # 401 - 토큰 만료
    INVALID = "invalid"      # 403 - 토큰 무효
    NO_TOKEN = "no_token"    # 토큰 없음
    REFRESHED = "refreshed"  # 토큰 갱신됨
    ERROR = "error"          # 기타 오류


class RefreshError:
    """토큰 갱신 실패 분류"""
    PERMANENT = "permanent"  # invalid_grant, HTTP 400/401 → 재로그인 필요
    TRANSIENT = "transient"  # 네트워크 오류, 타임아웃 → 일시적, 재시도 가능


def classify_refresh_error(error_message):
    """갱신 실패 에러 메시지를 영구적/일시적으로 분류"""
    if not error_message:
        return RefreshError.TRANSIENT

    msg = error_message.lower()

    # 영구적 실패: refresh token 자체가 무효
    if "invalid_grant" in msg:
        return RefreshError.PERMANENT
    if "http 400" in msg or "http 401" in msg:
        return RefreshError.PERMANENT

    # 그 외는 일시적 (네트워크, 타임아웃 등)
    return RefreshError.TRANSIENT


def is_token_expired(credential):
    """토큰 만료 여부 확인 (expiresAt 기준)"""
    oauth = credential.get("claudeAiOauth", {})
    expires_at = oauth.get("expiresAt")
    if not expires_at:
        return False  # 만료 시간 없으면 일단 유효하다고 가정

    # expiresAt은 밀리초 타임스탬프
    expires_datetime = datetime.fromtimestamp(expires_at / 1000)
    # 5분 여유를 두고 만료 판단
    return datetime.now() > expires_datetime - timedelta(minutes=5)


def is_token_expiring_soon(credential, hours=1):
    """토큰이 곧 만료되는지 확인 (기본 1시간 이내)"""
    oauth = credential.get("claudeAiOauth", {})
    expires_at = oauth.get("expiresAt")
    if not expires_at:
        return False

    expires_datetime = datetime.fromtimestamp(expires_at / 1000)
    return datetime.now() > expires_datetime - timedelta(hours=hours)


def is_token_fresh(credential, threshold_hours=TOKEN_FRESH_THRESHOLD_HOURS):
    """토큰이 최근에 갱신되었는지 확인 (잔여 시간이 threshold 이상)

    8시간 유효기간 중 잔여 시간이 threshold_hours 이상이면 '신선'하다고 판단.
    다른 프로세스가 이미 갱신한 경우를 감지하는 데 사용.

    Args:
        credential: credential 딕셔너리
        threshold_hours: 신선도 기준 시간 (기본 7시간)

    Returns:
        bool: 잔여 시간이 threshold 이상이면 True
    """
    oauth = credential.get("claudeAiOauth", {})
    expires_at = oauth.get("expiresAt")
    if not expires_at:
        return False

    expires_datetime = datetime.fromtimestamp(expires_at / 1000)
    remaining = expires_datetime - datetime.now()
    return remaining >= timedelta(hours=threshold_hours)


def refresh_access_token(credential=None, credential_file=None):
    """
    Refresh token으로 access token 갱신

    Args:
        credential: credential 딕셔너리 (None이면 Keychain에서 읽음)
        credential_file: credential 파일 경로 (저장된 계정용)
                        - None: Keychain에 저장 (현재 로그인 계정)
                        - Path: 해당 파일에 저장 (저장된 계정)
    """
    from_keychain = credential is None
    source = "keychain" if credential is None else ("file" if credential_file else "passed")

    if credential is None:
        credential = get_keychain_credential()
    if not credential:
        log("WARN", f"refresh: credential 없음 (source={source})")
        return None, "credential 없음"

    oauth = credential.get("claudeAiOauth", {})
    refresh_token = oauth.get("refreshToken")

    if not refresh_token:
        log("WARN", f"refresh: refresh token 없음 (source={source})")
        return None, "refresh token 없음"

    log("INFO", f"refresh: 갱신 시작 (source={source})")

    try:
        # OAuth 토큰 갱신 요청
        # Claude Code 공식 OAuth 엔드포인트 및 client_id 사용
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://platform.claude.com/v1/oauth/token",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "claude-account-manager/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                token_data = json.loads(response.read().decode())

                # credential 업데이트
                new_credential = credential.copy()
                new_oauth = oauth.copy()

                if "access_token" in token_data:
                    new_oauth["accessToken"] = token_data["access_token"]
                if "refresh_token" in token_data:
                    new_oauth["refreshToken"] = token_data["refresh_token"]
                if "expires_in" in token_data:
                    # expires_in은 초 단위, expiresAt은 밀리초 타임스탬프
                    new_oauth["expiresAt"] = int((datetime.now().timestamp() + token_data["expires_in"]) * 1000)

                new_credential["claudeAiOauth"] = new_oauth

                # 갱신 성공 로깅
                new_expires = new_oauth.get("expiresAt")
                if new_expires:
                    new_exp_str = datetime.fromtimestamp(new_expires / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    log("INFO", f"refresh: 갱신 성공 (새 만료: {new_exp_str}, source={source})")

                # 저장 위치 결정
                if credential_file:
                    # 파일에 저장 (저장된 계정)
                    try:
                        credential_file.write_text(json.dumps(new_credential, indent=2, ensure_ascii=False))
                        os.chmod(credential_file, 0o600)
                        return new_credential, None
                    except Exception as e:
                        return new_credential, f"파일 저장 실패: {e}"
                elif from_keychain:
                    # Keychain에 저장 (현재 로그인 계정)
                    if set_keychain_credential(new_credential):
                        return new_credential, None
                    else:
                        return new_credential, "Keychain 저장 실패"
                else:
                    # credential이 직접 전달됨 - 저장하지 않고 반환만
                    return new_credential, None

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            pass
        log("ERROR", f"refresh: HTTP {e.code}")
        return None, f"토큰 갱신 실패 (HTTP {e.code})"
    except urllib.error.URLError as e:
        log("ERROR", f"refresh: 연결 오류 - {e.reason}")
        return None, f"연결 오류: {e.reason}"
    except Exception as e:
        log("ERROR", f"refresh: 예외 - {e}")
        return None, str(e)

    return None, "알 수 없는 오류"


def check_token_status(credential=None, auto_refresh=True):
    """OAuth 토큰 상태 확인 (자동 갱신 지원)"""
    if credential is None:
        credential = get_keychain_credential()
    if not credential:
        return TokenStatus.NO_TOKEN, None

    access_token = credential.get("claudeAiOauth", {}).get("accessToken")
    if not access_token:
        return TokenStatus.NO_TOKEN, None

    # 만료 시간 미리 체크 (API 호출 전)
    if auto_refresh and is_token_expired(credential):
        new_credential, error = refresh_access_token(credential)
        if new_credential:
            return TokenStatus.REFRESHED, "토큰이 자동으로 갱신되었습니다."
        # 갱신 실패하면 계속 진행하여 API로 확인

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {access_token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-account-manager/1.0",
            },
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            return TokenStatus.VALID, None

    except urllib.error.HTTPError as e:
        if e.code == 401:
            # 토큰 만료 - 자동 갱신 시도
            if auto_refresh:
                new_credential, error = refresh_access_token(credential)
                if new_credential:
                    return TokenStatus.REFRESHED, "토큰이 자동으로 갱신되었습니다."
                return TokenStatus.EXPIRED, f"토큰 갱신 실패: {error}"
            return TokenStatus.EXPIRED, "토큰이 만료되었습니다. 재로그인이 필요합니다."
        elif e.code == 403:
            return TokenStatus.INVALID, "토큰이 유효하지 않습니다. 재로그인이 필요합니다."
        else:
            return TokenStatus.ERROR, f"HTTP 오류: {e.code}"
    except urllib.error.URLError as e:
        return TokenStatus.ERROR, f"연결 오류: {e.reason}"
    except Exception as e:
        return TokenStatus.ERROR, str(e)
