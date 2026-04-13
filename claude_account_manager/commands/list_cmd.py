"""
cmd_list: Display registered accounts with usage visualization
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors, make_progress_bar
from ..storage import load_index, get_current_account
from ..keychain import get_keychain_credential
from ..token import TokenStatus
from ..api import _fetch_usage_from_api
from ..account import estimate_plan, is_same_account, _is_real_org


def _get_token_expires_at(credential):
    """credential에서 토큰 만료 시간(datetime) 반환"""
    if not credential:
        return None
    oauth = credential.get("claudeAiOauth", {})
    expires_at = oauth.get("expiresAt")
    if not expires_at:
        return None
    # expiresAt은 밀리초 타임스탬프
    return datetime.fromtimestamp(expires_at / 1000)


def cmd_list():
    """등록된 계정 목록 표시 (사용량 시각화 포함)"""
    index = load_index()
    current = get_current_account()
    current_email = current.get("emailAddress", "")
    current_plan = estimate_plan(current)

    def _is_current(acc):
        return is_same_account(acc, current)

    # 헤더
    print()
    print(c(Colors.BOLD, "  Claude 계정 목록"))
    print(c(Colors.DIM, "  " + "─" * 55))

    if not index["accounts"]:
        print(c(Colors.DIM, "  (등록된 계정 없음)"))
        print(c(Colors.DIM, "  /account add [이름] 으로 현재 계정을 저장하세요"))
    else:
        # 병렬로 모든 계정의 사용량 가져오기
        def fetch_account_usage(acc):
            """계정별 사용량 및 토큰 상태 가져오기 (401 시 자동 갱신 포함)"""
            is_current = _is_current(acc)
            if is_current:
                # 현재 계정: Keychain 사용, credential_file=None
                usage, token_status = _fetch_usage_from_api(include_token_status=True)
                # 현재 계정의 credential에서 만료 시간 가져오기
                current_cred = get_keychain_credential()
                expires_at = _get_token_expires_at(current_cred)
                return (acc["id"], usage, token_status, expires_at)
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
                            # 갱신 후 다시 읽어서 최신 만료 시간 가져오기
                            try:
                                updated_cred = json.loads(credential_path.read_text())
                                expires_at = _get_token_expires_at(updated_cred)
                            except Exception:
                                expires_at = _get_token_expires_at(credential)
                            return (acc["id"], usage, token_status, expires_at)
                        except Exception:
                            pass
                return (acc["id"], None, TokenStatus.NO_TOKEN, None)

        # 계정별 사용량 병렬 조회 (각 계정은 서로 다른 토큰 사용 → rate limit 독립)
        usage_map = {}
        token_status_map = {}
        expires_at_map = {}

        max_workers = min(len(index["accounts"]), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(fetch_account_usage, index["accounts"]):
                try:
                    acc_id, usage, token_status, expires_at = result
                    usage_map[acc_id] = usage
                    token_status_map[acc_id] = token_status
                    expires_at_map[acc_id] = expires_at
                except Exception:
                    pass

        # 결과 출력
        for i, acc in enumerate(index["accounts"], 1):
            is_active = acc["id"] == index.get("activeAccountId")
            is_current = _is_current(acc)

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
                    except Exception:
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

            # 출력: [번호] ● name (org) [Plan] - 상태
            status_text = f" - {status}" if status else ""
            acc_org_name = acc.get("organizationName", "")
            org_badge = f" {c(Colors.MAGENTA, f'@{acc_org_name}')}" if _is_real_org(acc_org_name) else ""
            print(f"  [{i}] {marker} {acc['name']}{org_badge} {plan_badge}{status_text}")
            print(f"      {c(Colors.DIM, acc['email'])}")

            # 사용량 표시 (미리 가져온 데이터 사용)
            real_usage = usage_map.get(acc["id"])
            token_status = token_status_map.get(acc["id"], TokenStatus.NO_TOKEN)
            expires_at = expires_at_map.get(acc["id"])

            # 토큰 상태에 따른 경고 표시
            if token_status == TokenStatus.EXPIRED:
                print(f"      {c(Colors.RED, '⚠ 토큰 만료')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif token_status == TokenStatus.INVALID:
                print(f"      {c(Colors.RED, '⚠ 토큰 무효')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif token_status == TokenStatus.NO_TOKEN:
                print(f"      {c(Colors.DIM, '(credential 없음)')}")
            elif token_status == TokenStatus.ERROR:
                print(f"      {c(Colors.YELLOW, '⚠ 연결 오류')} - {c(Colors.DIM, '네트워크 확인 필요')}")
            elif token_status == TokenStatus.VALID and not real_usage:
                # 토큰은 유효하지만 사용량 조회 실패 (429 rate limit 등)
                if expires_at:
                    now_local = datetime.now()
                    remaining = expires_at - now_local
                    if remaining.total_seconds() > 0:
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        expire_str = f"{hours}h {minutes}m" if hours >= 1 else f"{minutes}m"
                        print(f"      {c(Colors.DIM, '토큰')} {c(Colors.DIM, f'🔑 {expire_str} 후 만료')}")
                else:
                    print(f"      {c(Colors.DIM, '(사용량 조회 일시 실패)')}")
            elif real_usage:
                # 실제 API 데이터 사용
                # API가 반환하는 resetAt은 timezone-aware(UTC)이므로 now도 aware로 생성
                now = datetime.now(timezone.utc)

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

                # 토큰 만료 시간 표시
                if expires_at:
                    now_local = datetime.now()
                    remaining = expires_at - now_local
                    if remaining.total_seconds() > 0:
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        # 1시간 이내면 경고 색상
                        if hours < 1:
                            expire_color = Colors.YELLOW
                            expire_str = f"{minutes}m"
                        else:
                            expire_color = Colors.DIM
                            expire_str = f"{hours}h {minutes}m"
                        print(f"      {c(Colors.DIM, '토큰')} {c(expire_color, f'🔑 {expire_str} 후 만료')}")

    print(c(Colors.DIM, "  " + "─" * 55))

    if not current_email:
        print()
        print(c(Colors.YELLOW, "  현재 로그인된 계정이 없습니다."))

    print()
