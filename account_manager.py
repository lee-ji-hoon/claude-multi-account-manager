#!/usr/bin/env python3
"""
Claude Code Multi-Account Manager
다중 계정을 관리하는 스크립트

Usage:
    python3 account_manager.py [action] [args]

Actions:
    list           - 등록된 계정 목록 (사용량 시각화 포함)
    add [name]     - 현재 계정 저장
    switch [id]    - 계정 전환 (인자 없으면 대화형 선택)
    remove [id]    - 계정 삭제
    rename [id] [name] - 계정 이름 변경
    current        - 현재 계정 표시
"""
import json
import os
import sys
import select
from pathlib import Path
from datetime import datetime, date, timedelta


# 버전 정보
__version__ = "1.0.0"
PACKAGE_NAME = "claude-account-manager"

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

# ANSI 색상 코드
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def supports_color():
    """터미널이 색상을 지원하는지 확인"""
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


USE_COLOR = supports_color()


def c(color, text):
    """색상 적용 (지원 시에만)"""
    if USE_COLOR:
        return f"{color}{text}{Colors.RESET}"
    return text


def get_keychain_service():
    """Claude Code가 사용하는 실제 keychain service name 결정"""
    import hashlib
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if config_dir:
        hash_suffix = hashlib.sha256(config_dir.encode()).hexdigest()[:8]
        return f"Claude Code-credentials-{hash_suffix}"
    return "Claude Code-credentials"


KEYCHAIN_SERVICE = get_keychain_service()
KEYCHAIN_ACCOUNT = os.environ.get("USER", "unknown")


import subprocess


def get_keychain_credential():
    """Keychain에서 Claude Code credential 읽기"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
        return None
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        print(f"  Keychain 읽기 실패: {e}")
        return None


def set_keychain_credential(credential_data):
    """Keychain에 Claude Code credential 저장"""
    try:
        credential_json = json.dumps(credential_data, ensure_ascii=False)

        # 기존 항목 삭제 (있는 경우)
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
            capture_output=True
        )

        # 새 항목 추가
        result = subprocess.run(
            ["security", "add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w", credential_json],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"  Keychain 저장 실패: {result.stderr}")
            return False
        return True
    except subprocess.SubprocessError as e:
        print(f"  Keychain 저장 실패: {e}")
        return False


def ensure_accounts_dir():
    """accounts 디렉토리와 index.json 초기화"""
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(json.dumps({
            "version": 1,
            "accounts": [],
            "activeAccountId": None
        }, indent=2, ensure_ascii=False))


def load_index():
    """index.json 로드"""
    ensure_accounts_dir()
    try:
        return json.loads(INDEX_FILE.read_text())
    except json.JSONDecodeError:
        # 손상된 index.json 복구
        default_index = {
            "version": 1,
            "accounts": [],
            "activeAccountId": None
        }
        save_index(default_index)
        return default_index


def save_index(data):
    """index.json 저장"""
    INDEX_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_claude_json():
    """~/.claude.json 로드"""
    if not CLAUDE_JSON.exists():
        return {}
    try:
        return json.loads(CLAUDE_JSON.read_text())
    except json.JSONDecodeError as e:
        print(f"~/.claude.json 파싱 오류: {e}")
        return {}


def save_claude_json(data):
    """~/.claude.json 저장"""
    CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_current_account():
    """현재 oauthAccount 반환"""
    data = load_claude_json()
    return data.get("oauthAccount", {})


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


def get_today_usage():
    """오늘 사용량 정보 반환"""
    if not STATS_CACHE.exists():
        return None

    try:
        stats = json.loads(STATS_CACHE.read_text())
        today = date.today().isoformat()

        # 오늘 토큰 사용량 찾기
        daily_tokens = stats.get("dailyModelTokens", [])
        today_tokens = None
        for entry in daily_tokens:
            if entry.get("date") == today:
                today_tokens = entry.get("tokensByModel", {})
                break

        # 오늘 활동 찾기
        daily_activity = stats.get("dailyActivity", [])
        today_activity = None
        for entry in daily_activity:
            if entry.get("date") == today:
                today_activity = entry
                break

        if not today_tokens and not today_activity:
            return None

        total_tokens = sum(today_tokens.values()) if today_tokens else 0
        messages = today_activity.get("messageCount", 0) if today_activity else 0

        return {
            "tokens": total_tokens,
            "messages": messages,
            "models": today_tokens or {}
        }
    except (json.JSONDecodeError, KeyError):
        return None


def get_weekly_usage():
    """최근 7일 사용량 정보 반환 (로컬 stats 기반)"""
    if not STATS_CACHE.exists():
        return None

    try:
        stats = json.loads(STATS_CACHE.read_text())
        today = date.today()
        week_ago = today - timedelta(days=7)

        daily_tokens = stats.get("dailyModelTokens", [])
        daily_activity = stats.get("dailyActivity", [])

        total_tokens = 0
        total_messages = 0

        for entry in daily_tokens:
            entry_date = date.fromisoformat(entry.get("date", "1970-01-01"))
            if week_ago <= entry_date <= today:
                tokens_by_model = entry.get("tokensByModel", {})
                total_tokens += sum(tokens_by_model.values())

        for entry in daily_activity:
            entry_date = date.fromisoformat(entry.get("date", "1970-01-01"))
            if week_ago <= entry_date <= today:
                total_messages += entry.get("messageCount", 0)

        if total_tokens == 0 and total_messages == 0:
            return None

        return {
            "tokens": total_tokens,
            "messages": total_messages,
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def get_real_usage():
    """실제 API 사용량 정보 반환 (항상 직접 API 호출)"""
    return _fetch_usage_from_api()


def _parse_usage_data(data):
    """사용량 데이터 파싱"""
    result = {
        "planName": data.get("planName"),
        "fiveHour": data.get("fiveHour"),
        "sevenDay": data.get("sevenDay"),
        "fiveHourResetAt": None,
        "sevenDayResetAt": None,
    }

    if data.get("fiveHourResetAt"):
        try:
            result["fiveHourResetAt"] = datetime.fromisoformat(
                str(data["fiveHourResetAt"]).replace("Z", "+00:00")
            )
        except:
            pass
    if data.get("sevenDayResetAt"):
        try:
            result["sevenDayResetAt"] = datetime.fromisoformat(
                str(data["sevenDayResetAt"]).replace("Z", "+00:00")
            )
        except:
            pass

    return result


def check_for_updates(silent=True):
    """PyPI에서 최신 버전 확인 (24시간 캐시)"""
    import urllib.request
    import urllib.error

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


def detect_plan_from_credential(credential):
    """credential에서 Plan 자동 감지

    우선순위:
    1. rateLimitTier에서 max_5x/max_20x 감지 → Max5/Max20
    2. subscriptionType에서 team/pro/max 감지 → Team/Pro/Max5
    3. 기본값 → Free
    """
    import re
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


# 토큰 상태 상수
class TokenStatus:
    VALID = "valid"
    EXPIRED = "expired"      # 401 - 토큰 만료
    INVALID = "invalid"      # 403 - 토큰 무효
    NO_TOKEN = "no_token"    # 토큰 없음
    REFRESHED = "refreshed"  # 토큰 갱신됨
    ERROR = "error"          # 기타 오류


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


def refresh_access_token(credential=None, credential_file=None):
    """
    Refresh token으로 access token 갱신

    Args:
        credential: credential 딕셔너리 (None이면 Keychain에서 읽음)
        credential_file: credential 파일 경로 (저장된 계정용)
                        - None: Keychain에 저장 (현재 로그인 계정)
                        - Path: 해당 파일에 저장 (저장된 계정)
    """
    import urllib.request
    import urllib.error

    from_keychain = credential is None
    if credential is None:
        credential = get_keychain_credential()
    if not credential:
        return None, "credential 없음"

    oauth = credential.get("claudeAiOauth", {})
    refresh_token = oauth.get("refreshToken")

    if not refresh_token:
        return None, "refresh token 없음"

    try:
        # OAuth 토큰 갱신 요청
        # Claude Code 공식 OAuth 엔드포인트 및 client_id 사용
        import urllib.parse
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
        except:
            pass
        return None, f"토큰 갱신 실패 (HTTP {e.code}): {error_body}"
    except urllib.error.URLError as e:
        return None, f"연결 오류: {e.reason}"
    except Exception as e:
        return None, str(e)

    return None, "알 수 없는 오류"


def check_token_status(credential=None, auto_refresh=True):
    """OAuth 토큰 상태 확인 (자동 갱신 지원)"""
    import urllib.request
    import urllib.error

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


def _fetch_usage_from_api(credential=None, include_token_status=False, credential_file=None):
    """
    Anthropic API에서 직접 사용량 가져오기

    Args:
        credential: credential 딕셔너리 (None이면 Keychain에서 읽음)
        include_token_status: 토큰 상태도 함께 반환할지 여부
        credential_file: credential 파일 경로 (저장된 계정용, 토큰 갱신 시 저장에 사용)
    """
    import urllib.request
    import urllib.error

    # credential이 없으면 Keychain에서 읽기
    if credential is None:
        credential = get_keychain_credential()
    if not credential:
        if include_token_status:
            return None, TokenStatus.NO_TOKEN
        return None

    access_token = credential.get("claudeAiOauth", {}).get("accessToken")
    subscription_type = credential.get("claudeAiOauth", {}).get("subscriptionType", "")

    if not access_token:
        if include_token_status:
            return None, TokenStatus.NO_TOKEN
        return None

    # Plan 이름 결정
    sub_lower = subscription_type.lower()
    if "max" in sub_lower:
        # Max5/Max20 구분: subscription_type에서 숫자 추출
        import re
        match = re.search(r'max[_\s-]?(\d+)', sub_lower)
        if match:
            num = int(match.group(1))
            if num >= 20:
                plan_name = "Max20"
            else:
                plan_name = "Max5"
        else:
            plan_name = "Max5"  # 기본값
    elif "pro" in sub_lower:
        plan_name = "Pro"
    elif "team" in sub_lower:
        plan_name = "Team"
    elif not subscription_type or "api" in sub_lower:
        if include_token_status:
            return None, TokenStatus.VALID  # API 사용자는 토큰은 유효하지만 사용량 없음
        return None
    else:
        plan_name = subscription_type.capitalize()

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
            if response.status != 200:
                if include_token_status:
                    return None, TokenStatus.ERROR
                return None
            api_data = json.loads(response.read().decode())

        # API 응답 파싱
        result = {
            "planName": plan_name,
            "fiveHour": None,
            "sevenDay": None,
            "fiveHourResetAt": None,
            "sevenDayResetAt": None,
            "tokenStatus": TokenStatus.VALID,
        }

        if api_data.get("five_hour"):
            util = api_data["five_hour"].get("utilization")
            if util is not None:
                result["fiveHour"] = max(0, min(100, round(util)))
            if api_data["five_hour"].get("resets_at"):
                try:
                    result["fiveHourResetAt"] = datetime.fromisoformat(
                        api_data["five_hour"]["resets_at"].replace("Z", "+00:00")
                    )
                except:
                    pass

        if api_data.get("seven_day"):
            util = api_data["seven_day"].get("utilization")
            if util is not None:
                result["sevenDay"] = max(0, min(100, round(util)))
            if api_data["seven_day"].get("resets_at"):
                try:
                    result["sevenDayResetAt"] = datetime.fromisoformat(
                        api_data["seven_day"]["resets_at"].replace("Z", "+00:00")
                    )
                except:
                    pass

        if include_token_status:
            return result, TokenStatus.VALID
        return result

    except urllib.error.HTTPError as e:
        if e.code == 401:
            # 토큰 만료 - 자동 갱신 시도 (credential_file 전달하여 올바른 위치에 저장)
            new_credential, refresh_error = refresh_access_token(credential, credential_file=credential_file)
            if new_credential:
                # 갱신 성공 - 재시도 (credential_file=None으로 재귀 방지)
                return _fetch_usage_from_api(new_credential, include_token_status, credential_file=None)
            if include_token_status:
                return None, TokenStatus.EXPIRED
            return None
        elif e.code == 403:
            if include_token_status:
                return None, TokenStatus.INVALID
            return None
        else:
            if include_token_status:
                return None, TokenStatus.ERROR
            return None

    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        if include_token_status:
            return None, TokenStatus.ERROR
        return None


def get_last_activity_time():
    """마지막 활동 시간 가져오기"""
    try:
        claude_data = load_claude_json()
        projects = claude_data.get("projects", {})

        last_time = None
        for project in projects.values():
            session_id = project.get("lastSessionId")
            if session_id:
                # sessions 디렉토리에서 마지막 수정 시간 확인
                sessions_dir = CLAUDE_DIR / "projects"
                for p in sessions_dir.glob(f"**/{session_id}*"):
                    mtime = datetime.fromtimestamp(p.stat().st_mtime)
                    if last_time is None or mtime > last_time:
                        last_time = mtime

        if last_time is None:
            # 대안: stats-cache.json 수정 시간 사용
            if STATS_CACHE.exists():
                last_time = datetime.fromtimestamp(STATS_CACHE.stat().st_mtime)

        return last_time
    except Exception:
        return None


def format_tokens(n):
    """토큰 수를 읽기 쉽게 포맷"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def make_progress_bar(percentage, width=20, filled_char="█", empty_char="░"):
    """아스키 진행 막대 생성"""
    percentage = max(0, min(100, percentage))
    filled = int(width * percentage / 100)
    empty = width - filled

    bar = filled_char * filled + empty_char * empty

    # 색상 적용 (사용량에 따라)
    if percentage >= 90:
        return c(Colors.RED, bar)
    elif percentage >= 70:
        return c(Colors.YELLOW, bar)
    elif percentage >= 50:
        return c(Colors.CYAN, bar)
    else:
        return c(Colors.GREEN, bar)


def format_time_remaining(hours, minutes):
    """남은 시간 포맷"""
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def cmd_list():
    """등록된 계정 목록 표시 (사용량 시각화 포함)"""
    index = load_index()
    current = get_current_account()
    current_email = current.get("emailAddress", "")
    current_plan = estimate_plan(current)
    today_usage = get_today_usage()
    last_activity = get_last_activity_time()

    # 헤더
    print()
    print(c(Colors.BOLD, "  Claude 계정 목록"))
    print(c(Colors.DIM, "  " + "─" * 55))

    if not index["accounts"]:
        print(c(Colors.DIM, "  (등록된 계정 없음)"))
        print(c(Colors.DIM, "  /account add [이름] 으로 현재 계정을 저장하세요"))
    else:
        # 병렬로 모든 계정의 사용량 가져오기
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_account_usage(acc):
            """계정별 사용량 및 토큰 상태 가져오기 (401 시 자동 갱신 포함)"""
            is_current = acc["email"] == current_email
            if is_current:
                # 현재 계정: Keychain 사용, credential_file=None
                usage, token_status = _fetch_usage_from_api(include_token_status=True)
                return (acc["id"], usage, token_status)
            else:
                # 저장된 계정: credential 파일 사용
                cred_filename = acc.get("credentialFile")
                if cred_filename:
                    credential_path = ACCOUNTS_DIR / cred_filename
                    if credential_path.exists():
                        try:
                            credential = json.loads(credential_path.read_text())
                            # credential_file 전달하여 401 갱신 시 파일에 저장
                            usage, token_status = _fetch_usage_from_api(
                                credential,
                                include_token_status=True,
                                credential_file=credential_path
                            )
                            return (acc["id"], usage, token_status)
                        except:
                            pass
                return (acc["id"], None, TokenStatus.NO_TOKEN)

        # 병렬 요청
        usage_map = {}
        token_status_map = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_account_usage, acc): acc for acc in index["accounts"]}
            for future in as_completed(futures):
                try:
                    acc_id, usage, token_status = future.result()
                    usage_map[acc_id] = usage
                    token_status_map[acc_id] = token_status
                except:
                    pass

        # 결과 출력
        for i, acc in enumerate(index["accounts"], 1):
            is_active = acc["id"] == index.get("activeAccountId")
            is_current = acc["email"] == current_email

            if is_active and is_current:
                marker = c(Colors.GREEN, "●")
                status = c(Colors.GREEN, "활성")
            elif is_current:
                marker = c(Colors.CYAN, "→")
                status = c(Colors.CYAN, "현재")
            elif is_active:
                marker = c(Colors.DIM, "○")
                status = c(Colors.DIM, "저장됨")
            else:
                marker = " "
                status = ""

            # Plan 정보 가져오기
            if "plan" in acc:
                plan = acc["plan"]
            elif is_current:
                plan = current_plan
            else:
                profile_path = ACCOUNTS_DIR / acc.get("profileFile", "")
                if profile_path.exists():
                    try:
                        profile = json.loads(profile_path.read_text())
                        plan = estimate_plan(profile)
                    except:
                        plan = "?"
                else:
                    plan = "?"

            # Plan 색상
            plan_colors = {
                "Free": Colors.DIM,
                "Pro": Colors.CYAN,
                "Team": Colors.MAGENTA,
                "Max": Colors.YELLOW,
                "Max5": Colors.YELLOW,
                "Max20": Colors.GREEN,
            }
            plan_badge = c(plan_colors.get(plan, Colors.DIM), f"[{plan}]")

            # 출력: [번호] ● name [Plan] - 상태
            status_text = f" - {status}" if status else ""
            print(f"  [{i}] {marker} {acc['name']} {plan_badge}{status_text}")
            print(f"      {c(Colors.DIM, acc['email'])}")

            # 사용량 표시 (미리 가져온 데이터 사용)
            real_usage = usage_map.get(acc["id"])
            token_status = token_status_map.get(acc["id"], TokenStatus.NO_TOKEN)

            # 토큰 상태에 따른 경고 표시
            if token_status == TokenStatus.EXPIRED:
                print(f"      {c(Colors.RED, '⚠ 토큰 만료')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif token_status == TokenStatus.INVALID:
                print(f"      {c(Colors.RED, '⚠ 토큰 무효')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif token_status == TokenStatus.NO_TOKEN:
                print(f"      {c(Colors.DIM, '(credential 없음)')}")
            elif token_status == TokenStatus.ERROR:
                print(f"      {c(Colors.YELLOW, '⚠ 연결 오류')} - {c(Colors.DIM, '네트워크 확인 필요')}")
            elif real_usage:
                # 실제 API 데이터 사용
                now = datetime.now(real_usage["sevenDayResetAt"].tzinfo) if real_usage["sevenDayResetAt"] else datetime.now()

                # 현재 세션 사용량 (5시간)
                if real_usage["fiveHour"] is not None:
                    percentage = real_usage["fiveHour"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage["fiveHourResetAt"]:
                        remaining = real_usage["fiveHourResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {hours}h {minutes}m"
                    print(f"      {c(Colors.DIM, '현재')} {bar} {percentage}%{reset_str}")

                # 주간 사용량
                if real_usage["sevenDay"] is not None:
                    percentage = real_usage["sevenDay"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage["sevenDayResetAt"]:
                        remaining = real_usage["sevenDayResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {hours}h {minutes}m"
                    print(f"      {c(Colors.DIM, '주간')} {bar} {percentage}%{reset_str}")

    print(c(Colors.DIM, "  " + "─" * 55))

    if not current_email:
        print()
        print(c(Colors.YELLOW, "  현재 로그인된 계정이 없습니다."))

    print()


def cmd_add(name=None):
    """현재 계정을 프로필로 저장"""
    current = get_current_account()
    if not current:
        print("현재 로그인된 계정이 없습니다. 먼저 /login 하세요.")
        return False

    email = current.get("emailAddress", "")
    if not email:
        print("계정 이메일을 찾을 수 없습니다.")
        return False

    # Generate ID from email
    account_id = email.split("@")[0].replace(".", "_").replace("+", "_").lower()

    if not name:
        name = current.get("displayName", account_id)

    index = load_index()

    # Check if already exists
    for acc in index["accounts"]:
        if acc["email"] == email:
            print(f"이미 등록된 계정입니다: {acc['id']} ({acc['name']})")
            print()
            print(c(Colors.DIM, "  " + "─" * 40))
            print(f"  [1] 토큰만 갱신 (재로그인 없이)")
            print(f"  [2] 새로 로그인 후 갱신")
            print(f"  [3] 취소")
            print(c(Colors.DIM, "  " + "─" * 40))
            print(f"  {c(Colors.DIM, '번호를 입력하세요 (기본: 1)')}: ", end="", flush=True)

            try:
                choice = input().strip()
            except (EOFError, KeyboardInterrupt):
                print()
                print("취소됨")
                return False

            if choice == "1" or choice == "":
                # 기존 계정 토큰만 갱신
                credential = get_keychain_credential()
                if credential:
                    credential_path = ACCOUNTS_DIR / acc.get("credentialFile", f"credential_{acc['id']}.json")
                    credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
                    os.chmod(credential_path, 0o600)

                    # Plan도 자동 감지해서 갱신
                    detected_plan = detect_plan_from_credential(credential)
                    for i, a in enumerate(index["accounts"]):
                        if a["id"] == acc["id"]:
                            index["accounts"][i]["plan"] = detected_plan
                            break
                    save_index(index)

                    print()
                    print(c(Colors.GREEN, f"  토큰 갱신 완료: {acc['id']}"))
                    print(f"  Plan: {detected_plan} (자동 감지)")
                else:
                    print(c(Colors.RED, "  토큰을 가져올 수 없습니다."))
                return False
            elif choice == "2":
                # 새로 로그인 요청
                print()
                print(c(Colors.YELLOW, "  새로 로그인해주세요: /login"))
                print(c(Colors.DIM, "  로그인 후 다시 /account-add 를 실행하세요."))
                return "need_login"
            else:
                print("취소됨")
                return False

    # credential에서 Plan 자동 감지
    credential = get_keychain_credential()
    detected_plan = None
    if credential:
        detected_plan = detect_plan_from_credential(credential)

    # Plan 확인 (자동 감지 결과 표시)
    print()
    if detected_plan and detected_plan != "Free":
        print(c(Colors.GREEN, f"  Plan 자동 감지: {detected_plan}"))
        plan = detected_plan
    else:
        # 자동 감지 실패 시 수동 선택
        print(c(Colors.BOLD, "  Plan 선택"))
        print(c(Colors.DIM, "  " + "─" * 40))
        plans = ["Free", "Pro", "Team", "Max5", "Max20"]
        for i, p in enumerate(plans, 1):
            desc = ""
            if p == "Max5":
                desc = c(Colors.DIM, " (5 프로젝트)")
            elif p == "Max20":
                desc = c(Colors.DIM, " (20 프로젝트)")
            print(f"  [{i}] {p}{desc}")
        print(c(Colors.DIM, "  " + "─" * 40))
        print(f"  {c(Colors.DIM, '번호를 입력하세요 (기본: 1)')}: ", end="", flush=True)

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False

        if choice == "":
            plan = "Free"
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(plans):
                    plan = plans[idx]
                else:
                    plan = "Free"
            except ValueError:
                plan = "Free"

    # Save profile
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # Save credential from Keychain
    credential_file = f"credential_{account_id}.json"
    credential_path = ACCOUNTS_DIR / credential_file
    credential = get_keychain_credential()
    has_credential = False
    if credential:
        credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
        os.chmod(credential_path, 0o600)
        has_credential = True

    # Update index
    index["accounts"].append({
        "id": account_id,
        "name": name,
        "email": email,
        "plan": plan,
        "profileFile": profile_file,
        "credentialFile": credential_file if has_credential else None,
        "createdAt": datetime.now().isoformat()
    })
    index["activeAccountId"] = account_id
    save_index(index)

    print()
    print(c(Colors.GREEN, "  계정 저장 완료"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  ID: {account_id}")
    print(f"  이름: {name}")
    print(f"  이메일: {email}")
    print(f"  Plan: {plan}")
    if has_credential:
        print(f"  OAuth: {c(Colors.GREEN, '저장됨')}")
    else:
        print(f"  OAuth: {c(Colors.YELLOW, '저장 실패 (수동 로그인 필요)')}")
    print()
    return True


def cmd_switch(account_id=None):
    """다른 계정으로 전환 (대화형 선택 지원)"""
    index = load_index()

    if not index["accounts"]:
        print("등록된 계정이 없습니다.")
        print("/account add [이름] 으로 먼저 계정을 등록하세요.")
        return False

    # 인자가 없으면 대화형 선택
    if account_id is None:
        print()
        print(c(Colors.BOLD, "  계정 선택"))
        print(c(Colors.DIM, "  " + "─" * 55))

        current = get_current_account()
        current_email = current.get("emailAddress", "")
        current_plan = estimate_plan(current)
        today_usage = get_today_usage()
        last_activity = get_last_activity_time()

        for i, acc in enumerate(index["accounts"], 1):
            is_current = acc["email"] == current_email
            marker = c(Colors.GREEN, "●") if is_current else " "

            # Plan 정보
            if "plan" in acc:
                plan = acc["plan"]
            elif is_current:
                plan = current_plan
            else:
                profile_path = ACCOUNTS_DIR / acc.get("profileFile", "")
                if profile_path.exists():
                    try:
                        profile = json.loads(profile_path.read_text())
                        plan = estimate_plan(profile)
                    except:
                        plan = "?"
                else:
                    plan = "?"

            plan_colors = {"Free": Colors.DIM, "Pro": Colors.CYAN, "Team": Colors.MAGENTA, "Max": Colors.YELLOW, "Max5": Colors.YELLOW, "Max20": Colors.GREEN}
            plan_badge = c(plan_colors.get(plan, Colors.DIM), f"[{plan}]")

            print(f"  [{i}] {marker} {acc['name']} {plan_badge}")
            print(f"      {c(Colors.DIM, acc['email'])}")

            # 현재 계정이면 사용량 표시
            if is_current:
                if today_usage:
                    tokens = today_usage["tokens"]
                    limit = PLAN_LIMITS_DAILY.get(plan, PLAN_LIMITS_DAILY["Unknown"])
                    percentage = min(100, (tokens / limit) * 100)
                    bar = make_progress_bar(percentage, width=12)
                    print(f"      {c(Colors.DIM, '오늘')} {bar} {format_tokens(tokens)} ({percentage:.0f}%)")

                weekly_usage = get_weekly_usage()
                if weekly_usage:
                    tokens = weekly_usage["tokens"]
                    limit = PLAN_LIMITS_WEEKLY.get(plan, PLAN_LIMITS_WEEKLY["Unknown"])
                    percentage = min(100, (tokens / limit) * 100)
                    bar = make_progress_bar(percentage, width=12)
                    print(f"      {c(Colors.DIM, '주간')} {bar} {format_tokens(tokens)} ({percentage:.0f}%)")

        print(c(Colors.DIM, "  " + "─" * 55))

        # 리셋 시간 표시
        if last_activity:
            reset_hours = RESET_HOURS.get(current_plan, 5)
            reset_time = last_activity + timedelta(hours=reset_hours)
            now = datetime.now()
            if reset_time > now:
                remaining = reset_time - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                time_str = format_time_remaining(hours, minutes)
                print(f"  {c(Colors.CYAN, '⏱')} 리셋까지: {time_str}")
                print(c(Colors.DIM, "  " + "─" * 55))

        print(f"  {c(Colors.DIM, '번호를 입력하세요 (취소: q)')}: ", end="", flush=True)

        # 입력 대기 (타임아웃 없이)
        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False

        if choice.lower() in ('q', 'quit', 'exit', ''):
            print("취소됨")
            return False

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(index["accounts"]):
                account_id = index["accounts"][idx]["id"]
            else:
                print(f"잘못된 번호입니다: {choice}")
                return False
        except ValueError:
            # 숫자가 아니면 account_id로 시도
            account_id = choice

    # Find account
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        print("\n등록된 계정:")
        for acc in index["accounts"]:
            print(f"   - {acc['id']}: {acc['name']}")
        return False

    # Load profile
    profile_path = ACCOUNTS_DIR / account["profileFile"]
    if not profile_path.exists():
        print(f"프로필 파일이 없습니다: {account['profileFile']}")
        return False

    new_oauth = json.loads(profile_path.read_text())

    # Check if already active
    current = get_current_account()
    if current.get("emailAddress") == account["email"]:
        print(f"이미 해당 계정으로 로그인되어 있습니다: {account['name']}")
        return True

    # Backup current state
    backup_dir = ACCOUNTS_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Backup claude.json
    backup_file = backup_dir / f"claude_{timestamp}.json"
    claude_data = load_claude_json()
    backup_file.write_text(json.dumps(claude_data, indent=2, ensure_ascii=False))

    # Backup current credential
    current_credential = get_keychain_credential()
    if current_credential:
        backup_cred_file = backup_dir / f"credential_{timestamp}.json"
        backup_cred_file.write_text(json.dumps(current_credential, indent=2, ensure_ascii=False))
        os.chmod(backup_cred_file, 0o600)

    # Replace oauthAccount
    claude_data["oauthAccount"] = new_oauth
    save_claude_json(claude_data)

    # Replace Keychain credential
    credential_switched = False
    credential_file = account.get("credentialFile")
    if credential_file:
        credential_path = ACCOUNTS_DIR / credential_file
        if credential_path.exists():
            try:
                new_credential = json.loads(credential_path.read_text())
                if set_keychain_credential(new_credential):
                    credential_switched = True
            except json.JSONDecodeError:
                pass

    # Update active account
    index["activeAccountId"] = account_id
    save_index(index)

    print()
    print(c(Colors.GREEN, "  계정 전환 완료"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  {account['name']} ({account['email']})")

    if credential_switched:
        print(f"  OAuth: {c(Colors.GREEN, '토큰 교체 완료')}")
    else:
        print(f"  OAuth: {c(Colors.YELLOW, '토큰 없음 (재로그인 필요)')}")

    print()
    print(c(Colors.YELLOW, "  Claude Code를 재시작해야 변경사항이 적용됩니다."))
    print(c(Colors.DIM, "  터미널에서 'exit' 후 다시 'claude' 실행"))
    print()
    return True


def cmd_remove(account_id=None):
    """계정 삭제 (대화형 선택 지원)"""
    index = load_index()

    if not index["accounts"]:
        print("등록된 계정이 없습니다.")
        return False

    # 인자가 없으면 대화형 선택
    if account_id is None:
        print()
        print(c(Colors.BOLD, "  삭제할 계정 선택"))
        print(c(Colors.DIM, "  " + "─" * 55))

        current = get_current_account()
        current_email = current.get("emailAddress", "") if current else ""

        for i, acc in enumerate(index["accounts"], 1):
            is_current = acc["email"] == current_email
            marker = c(Colors.GREEN, "●") if is_current else " "
            plan_badge = c(Colors.DIM, f"[{acc.get('plan', '?')}]")
            print(f"  [{i}] {marker} {acc['name']} {plan_badge}")
            print(f"      {c(Colors.DIM, acc['email'])}")

        print(c(Colors.DIM, "  " + "─" * 55))
        print(f"  {c(Colors.DIM, '번호를 입력하세요 (취소: q)')}: ", end="", flush=True)

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False

        if choice.lower() in ('q', 'quit', 'exit', ''):
            print("취소됨")
            return False

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(index["accounts"]):
                account_id = index["accounts"][idx]["id"]
            else:
                print(f"잘못된 번호입니다: {choice}")
                return False
        except ValueError:
            account_id = choice

    # Find account
    account = None
    account_index = -1
    for i, acc in enumerate(index["accounts"]):
        if acc["id"] == account_id:
            account = acc
            account_index = i
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        return False

    # 삭제 확인
    print()
    print(c(Colors.YELLOW, f"  정말 삭제하시겠습니까?"))
    print(f"  계정: {account['name']} ({account['email']})")
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  {c(Colors.DIM, 'y/n (기본: n)')}: ", end="", flush=True)

    try:
        confirm = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    if confirm not in ('y', 'yes'):
        print("취소됨")
        return False

    # Remove profile file
    profile_path = ACCOUNTS_DIR / account["profileFile"]
    if profile_path.exists():
        profile_path.unlink()

    # Remove credential file
    if account.get("credentialFile"):
        credential_path = ACCOUNTS_DIR / account["credentialFile"]
        if credential_path.exists():
            credential_path.unlink()

    # Remove from index
    index["accounts"].pop(account_index)
    if index["activeAccountId"] == account_id:
        index["activeAccountId"] = index["accounts"][0]["id"] if index["accounts"] else None
    save_index(index)

    print(f"계정 삭제 완료: {account_id} ({account['name']})")
    return True


def cmd_current():
    """현재 계정 상세 정보 표시"""
    current = get_current_account()
    if not current:
        print("현재 로그인된 계정이 없습니다.")
        return

    print()
    print(c(Colors.BOLD, "  현재 계정"))
    print(c(Colors.DIM, "  " + "─" * 40))

    fields = [
        ("이름", current.get("displayName", "Unknown")),
        ("이메일", current.get("emailAddress", "Unknown")),
        ("조직", current.get("organizationName", "N/A")),
        ("역할", current.get("organizationRole", "N/A")),
        ("UUID", current.get("accountUuid", "N/A")[:20] + "..."),
    ]

    for label, value in fields:
        print(f"  {c(Colors.DIM, label)}: {value}")

    print()


def cmd_rename(account_id, new_name):
    """계정 이름 변경"""
    index = load_index()

    # Find account
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        print("\n등록된 계정:")
        for acc in index["accounts"]:
            print(f"   - {acc['id']}: {acc['name']}")
        return False

    old_name = account["name"]
    account["name"] = new_name
    save_index(index)

    print(f"이름 변경 완료: {old_name} → {new_name}")
    return True


def cmd_set_plan(account_id, plan):
    """계정 Plan 수동 설정"""
    valid_plans = ["Free", "Pro", "Team", "Max5", "Max20"]

    # "Max" 입력 시 "Max5"로 자동 변환 (하위 호환)
    if plan == "Max":
        plan = "Max5"
        print(c(Colors.DIM, "  (Max → Max5로 변환됨)"))

    if plan not in valid_plans:
        print(f"유효하지 않은 Plan: {plan}")
        print(f"사용 가능: {', '.join(valid_plans)}")
        return False

    index = load_index()

    # Find account
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}")
        return False

    account["plan"] = plan
    save_index(index)

    print(f"Plan 설정 완료: {account['name']} → {plan}")
    return True


def cmd_auto_add():
    """Hook용 자동 계정 등록 (비대화형)

    - 중복 시 조용히 스킵 (exit 0)
    - Plan 자동 감지 (credential에서)
    - 이름 자동 생성 (displayName > email)

    Returns:
        bool: True=등록됨, False=스킵/실패
    """
    # 1. 현재 계정 정보 확인
    current = get_current_account()
    if not current:
        return False  # 로그인 안 됨

    email = current.get("emailAddress", "")
    if not email:
        return False  # 이메일 없음

    # 2. 중복 확인 (조용히 스킵)
    if is_account_duplicate(email):
        return False  # 이미 등록됨

    # 3. credential에서 Plan 감지
    credential = get_keychain_credential()
    if not credential:
        print("[auto-add] credential을 읽을 수 없습니다.", file=sys.stderr)
        return False

    plan = detect_plan_from_credential(credential)

    # 4. 이름 자동 생성
    name = generate_account_name(current, email)

    # 5. ID 생성
    account_id = email.split("@")[0].replace(".", "_").replace("+", "_").lower()

    # 6. 프로필 저장
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # 7. credential 저장
    credential_file = f"credential_{account_id}.json"
    credential_path = ACCOUNTS_DIR / credential_file
    credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
    os.chmod(credential_path, 0o600)

    # 8. index 업데이트
    index = load_index()
    index["accounts"].append({
        "id": account_id,
        "name": name,
        "email": email,
        "plan": plan,
        "profileFile": profile_file,
        "credentialFile": credential_file,
        "createdAt": datetime.now().isoformat()
    })
    index["activeAccountId"] = account_id
    save_index(index)

    # 9. 성공 메시지
    print(f"[auto-add] 계정 등록됨: {name} ({email}) [{plan}]")
    return True


def cmd_refresh_all():
    """모든 등록된 계정의 토큰 갱신 (Hook용, 비대화형)

    세션 시작 시 모든 계정을 무조건 갱신하여:
    - 장기간 미사용 계정의 토큰 만료 방지
    - 세션 중간에 토큰 만료되는 상황 방지
    - 모든 계정이 항상 최신 토큰 유지

    Returns:
        int: 갱신 성공한 계정 수
    """
    index = load_index()
    if not index["accounts"]:
        return 0

    refreshed_count = 0
    current = get_current_account()
    current_email = current.get("emailAddress", "") if current else ""

    for acc in index["accounts"]:
        credential_file = acc.get("credentialFile")
        if not credential_file:
            continue

        credential_path = ACCOUNTS_DIR / credential_file

        # 현재 로그인된 계정 처리
        if acc["email"] == current_email:
            # Keychain에서 최신 토큰 가져와서 저장
            current_credential = get_keychain_credential()
            if current_credential:
                credential_path.write_text(json.dumps(current_credential, indent=2, ensure_ascii=False))
                os.chmod(credential_path, 0o600)

                # Plan도 갱신
                detected_plan = detect_plan_from_credential(current_credential)
                acc["plan"] = detected_plan

                refreshed_count += 1
                print(f"[refresh] {acc['id']}: 현재 계정 토큰 저장됨 [{detected_plan}]")
            continue

        # 다른 계정은 refreshToken으로 무조건 갱신 (만료 여부 무관)
        if not credential_path.exists():
            continue

        try:
            credential = json.loads(credential_path.read_text())
        except (json.JSONDecodeError, IOError):
            continue

        # refreshToken으로 갱신 시도 (만료 체크 없이 무조건 갱신)
        new_credential, error = refresh_access_token(credential)
        if new_credential:
            credential_path.write_text(json.dumps(new_credential, indent=2, ensure_ascii=False))
            os.chmod(credential_path, 0o600)

            # Plan도 갱신
            detected_plan = detect_plan_from_credential(new_credential)
            acc["plan"] = detected_plan

            refreshed_count += 1
            print(f"[refresh] {acc['id']}: 토큰 갱신됨 [{detected_plan}]")
        else:
            print(f"[refresh] {acc['id']}: 갱신 실패 - {error}", file=sys.stderr)

    # index 저장 (Plan 정보 갱신)
    save_index(index)

    return refreshed_count


def cmd_setup_hook():
    """Claude Code Hook 설정

    ~/.claude/settings.json에 SessionStart hook 추가
    - 기존 Hook 있으면 배열에 추가
    - 백업 생성
    """
    import shutil

    settings_path = Path.home() / ".claude" / "settings.json"

    print()
    print(c(Colors.BOLD, "  Claude Code Hook 설정"))
    print(c(Colors.DIM, "  " + "─" * 50))

    # 1. account_manager.py 경로 결정
    script_path = Path(__file__).resolve()

    # 2. 백업 생성
    if settings_path.exists():
        backup_path = settings_path.with_suffix(".json.bak")
        shutil.copy(settings_path, backup_path)
        print(f"  백업 생성: {c(Colors.DIM, str(backup_path))}")

    # 3. 기존 설정 로드
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            print(f"  {c(Colors.YELLOW, '경고')}: 기존 settings.json 파싱 실패, 새로 생성합니다.")

    # 4. hooks 구조 확인/생성
    if "hooks" not in settings:
        settings["hooks"] = {}

    # 5. SessionStart 배열 확인/생성
    if "SessionStart" not in settings["hooks"]:
        settings["hooks"]["SessionStart"] = []

    session_start = settings["hooks"]["SessionStart"]

    # 6. 이미 auto-add hook 있는지 확인
    for existing in session_start:
        if "auto-add" in existing.get("command", ""):
            print(f"  {c(Colors.GREEN, '✓')} 이미 auto-add Hook이 설정되어 있습니다.")
            print()
            return True

    # 7. 새 Hook 추가
    new_hook = {
        "matcher": "",
        "command": f"python3 {script_path} auto-add"
    }
    session_start.append(new_hook)

    # 8. 저장
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False))

    print(f"  {c(Colors.GREEN, '✓')} Hook 설정 완료")
    print()
    print(f"  {c(Colors.CYAN, '설정 파일')}: {settings_path}")
    print(f"  {c(Colors.CYAN, '실행 명령')}: python3 {script_path} auto-add")
    print()
    print(c(Colors.DIM, "  " + "─" * 50))
    print(f"  {c(Colors.YELLOW, 'Claude Code를 재시작하면 로그인 시 자동으로 계정이 등록됩니다.')}")
    print()
    return True


def cmd_check():
    """현재 OAuth 토큰 상태 확인"""
    print()
    print(c(Colors.BOLD, "  OAuth 토큰 상태 확인"))
    print(c(Colors.DIM, "  " + "─" * 50))

    current = get_current_account()
    current_email = current.get("emailAddress", "")

    if not current_email:
        print(f"  {c(Colors.YELLOW, '현재 로그인된 계정이 없습니다.')}")
        print()
        return

    print(f"  계정: {current_email}")
    print()

    # 현재 토큰 상태 확인
    token_status, message = check_token_status()

    if token_status == TokenStatus.VALID:
        print(f"  {c(Colors.GREEN, '✓')} 토큰 상태: {c(Colors.GREEN, '유효')}")
        # 추가로 사용량 정보도 표시
        usage = _fetch_usage_from_api()
        if usage:
            print()
            if usage["fiveHour"] is not None:
                print(f"  현재 세션 사용량: {usage['fiveHour']}%")
            if usage["sevenDay"] is not None:
                print(f"  주간 사용량: {usage['sevenDay']}%")
    elif token_status == TokenStatus.REFRESHED:
        print(f"  {c(Colors.GREEN, '✓')} 토큰 상태: {c(Colors.GREEN, '자동 갱신됨')}")
        print(f"  {c(Colors.CYAN, '→')} {message}")
        # 갱신 후 사용량 정보 표시
        usage = _fetch_usage_from_api()
        if usage:
            print()
            if usage["fiveHour"] is not None:
                print(f"  현재 세션 사용량: {usage['fiveHour']}%")
            if usage["sevenDay"] is not None:
                print(f"  주간 사용량: {usage['sevenDay']}%")
    elif token_status == TokenStatus.EXPIRED:
        print(f"  {c(Colors.RED, '✗')} 토큰 상태: {c(Colors.RED, '만료됨')}")
        print()
        print(f"  {c(Colors.YELLOW, '해결 방법:')}")
        print(f"    1. Claude Code에서 {c(Colors.CYAN, '/logout')} 실행")
        print(f"    2. {c(Colors.CYAN, '/login')} 으로 재로그인")
        print(f"    3. {c(Colors.CYAN, 'account add')} 로 토큰 다시 저장")
    elif token_status == TokenStatus.INVALID:
        print(f"  {c(Colors.RED, '✗')} 토큰 상태: {c(Colors.RED, '무효')}")
        print()
        print(f"  {c(Colors.YELLOW, '해결 방법:')}")
        print(f"    1. Claude Code에서 {c(Colors.CYAN, '/logout')} 실행")
        print(f"    2. {c(Colors.CYAN, '/login')} 으로 재로그인")
        print(f"    3. {c(Colors.CYAN, 'account add')} 로 토큰 다시 저장")
    elif token_status == TokenStatus.NO_TOKEN:
        print(f"  {c(Colors.YELLOW, '!')} 토큰 상태: {c(Colors.YELLOW, '토큰 없음')}")
        print()
        print(f"  {c(Colors.DIM, 'Keychain에 저장된 토큰이 없습니다.')}")
    else:
        print(f"  {c(Colors.YELLOW, '?')} 토큰 상태: {c(Colors.YELLOW, '확인 불가')}")
        if message:
            print(f"  {c(Colors.DIM, message)}")

    print(c(Colors.DIM, "  " + "─" * 50))
    print()


def cmd_update():
    """최신 버전으로 업데이트"""
    print()
    print(c(Colors.BOLD, "  버전 확인 중..."))

    latest = check_for_updates(silent=False)

    if latest:
        print(f"  새 버전 발견: {c(Colors.GREEN, latest)} (현재: {__version__})")
        print()
        print(f"  {c(Colors.CYAN, '업데이트 명령:')}")
        print(f"    pip install --upgrade {PACKAGE_NAME}")
        print()
    else:
        print(f"  {c(Colors.GREEN, '✓')} 최신 버전입니다: {__version__}")
        print()


def cmd_version():
    """버전 정보 표시"""
    print(f"Claude Account Manager v{__version__}")

    # 업데이트 확인 (백그라운드 캐시 사용)
    latest = check_for_updates(silent=True)
    if latest:
        print(f"  {c(Colors.YELLOW, '⬆')} 새 버전: {latest}")
        print(f"  pip install --upgrade {PACKAGE_NAME}")


def cmd_help():
    """도움말 표시"""
    print(f"""
{c(Colors.BOLD, '  Claude Account Manager')} v{__version__} - 다중 계정 관리
{c(Colors.DIM, '  ' + '─' * 50)}

  {c(Colors.CYAN, '사용법')}: /account [action] [args]

  {c(Colors.CYAN, 'Actions')}:
    list                등록된 계정 목록 + 사용량 (기본값)
    add [name]          현재 로그인된 계정 저장
    switch [id]         계정 전환 (인자 없으면 대화형 선택)
    remove [id]         저장된 계정 삭제
    rename [id] [name]  계정 이름 변경
    set-plan [id] [plan] Plan 수동 설정 (Free/Pro/Team/Max5/Max20)
    auto-add            자동 계정 등록 + 토큰 갱신 (Hook용)
    refresh-all         모든 계정 토큰 갱신
    setup-hook          Claude Code Hook 설정
    check               현재 OAuth 토큰 상태 확인
    update              새 버전 확인
    current             현재 계정 상세 정보
    help                이 도움말 표시

  {c(Colors.CYAN, '예시')}:
    /account add 업무용
    /account switch          {c(Colors.DIM, '# 대화형 선택')}
    /account switch personal
    /account setup-hook      {c(Colors.DIM, '# 로그인 시 자동 등록 Hook 설정')}
    /account check           {c(Colors.DIM, '# 토큰 만료 확인')}
    /account rename joel 조엘
    /account set-plan joel Pro
""")


def main():
    args = sys.argv[1:]

    # 버전 옵션 처리
    if args and args[0] in ("--version", "-v", "-V", "version"):
        cmd_version()
        return

    if not args or args[0] in ("list", "ls"):
        cmd_list()
    elif args[0] == "add":
        name = " ".join(args[1:]) if len(args) > 1 else None
        cmd_add(name)
    elif args[0] == "switch":
        account_id = args[1] if len(args) > 1 else None
        cmd_switch(account_id)
    elif args[0] in ("remove", "rm", "delete"):
        account_id = args[1] if len(args) > 1 else None
        cmd_remove(account_id)
    elif args[0] == "rename":
        if len(args) < 3:
            print("사용법: /account rename [계정ID] [새이름]")
            print("예: /account rename joel 조엘")
            return
        cmd_rename(args[1], " ".join(args[2:]))
    elif args[0] == "set-plan":
        if len(args) < 3:
            print("사용법: /account set-plan [계정ID] [Plan]")
            print("Plan: Free, Pro, Team, Max5, Max20")
            print("예: /account set-plan joel Pro")
            return
        cmd_set_plan(args[1], args[2])
    elif args[0] == "auto-add":
        cmd_auto_add()
        cmd_refresh_all()  # 모든 계정 토큰 갱신
        sys.exit(0)  # Hook은 항상 0으로 종료
    elif args[0] == "refresh-all":
        count = cmd_refresh_all()
        print(f"갱신된 계정: {count}개")
        sys.exit(0)
    elif args[0] == "setup-hook":
        cmd_setup_hook()
    elif args[0] == "check":
        cmd_check()
    elif args[0] == "update":
        cmd_update()
    elif args[0] == "current":
        cmd_current()
    elif args[0] in ("help", "-h", "--help"):
        cmd_help()
    else:
        print(f"알 수 없는 명령: {args[0]}")
        print("/account help 로 사용법을 확인하세요.")


if __name__ == "__main__":
    main()
