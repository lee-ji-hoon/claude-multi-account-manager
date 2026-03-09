"""
Anthropic API calls for usage fetching
"""
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta

from .config import STATS_CACHE, CLAUDE_DIR
from .storage import load_claude_json
from .keychain import get_keychain_credential
from .token import TokenStatus, refresh_access_token


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
        except Exception:
            pass
    if data.get("sevenDayResetAt"):
        try:
            result["sevenDayResetAt"] = datetime.fromisoformat(
                str(data["sevenDayResetAt"]).replace("Z", "+00:00")
            )
        except Exception:
            pass

    return result


def _parse_retry_response(api_data, plan_name):
    """429 재시도 후 API 응답 파싱"""
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
            except Exception:
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
            except Exception:
                pass
    return result


def _fetch_usage_from_api(credential=None, include_token_status=False, credential_file=None):
    """
    Anthropic API에서 직접 사용량 가져오기

    Args:
        credential: credential 딕셔너리 (None이면 Keychain에서 읽음)
        include_token_status: 토큰 상태도 함께 반환할지 여부
        credential_file: credential 파일 경로 (저장된 계정용, 토큰 갱신 시 저장에 사용)
    """
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
                "User-Agent": "claude-account-manager/2.1.4",
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
                except Exception:
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
                except Exception:
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
        elif e.code == 429:
            # Rate limited - 점진적 재시도 (2초, 4초)
            import time
            for delay in (2, 4):
                time.sleep(delay)
                try:
                    retry_req = urllib.request.Request(
                        "https://api.anthropic.com/api/oauth/usage",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "anthropic-beta": "oauth-2025-04-20",
                            "User-Agent": "claude-account-manager/2.2.1",
                        },
                    )
                    with urllib.request.urlopen(retry_req, timeout=5) as response:
                        if response.status == 200:
                            api_data = json.loads(response.read().decode())
                            result = _parse_retry_response(api_data, plan_name)
                            if include_token_status:
                                return result, TokenStatus.VALID
                            return result
                except Exception:
                    continue
            if include_token_status:
                return None, TokenStatus.VALID  # 토큰은 유효하지만 사용량을 못 가져옴
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
