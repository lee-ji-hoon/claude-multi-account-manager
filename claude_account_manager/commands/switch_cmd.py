"""
cmd_switch: Switch between accounts
"""
import json
import os
import time
from datetime import datetime, timedelta

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors, make_progress_bar, format_time_remaining
from ..storage import load_index, save_index, load_claude_json, save_claude_json, get_current_account
from ..keychain import get_keychain_credential, set_keychain_credential
from ..token import RefreshError, TokenStatus, classify_refresh_error, is_credential_valid
from .token_cmd import _safe_refresh_credential
from ..logger import log
from ..account import estimate_plan, is_same_account, _is_real_org
from ..api import _fetch_usage_from_api


def _cleanup_old_backups(backup_dir, prefix, keep=5):
    """오래된 백업 파일 정리 (최근 keep개만 유지)"""
    files = sorted(backup_dir.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    for old_file in files[:-keep]:
        try:
            old_file.unlink()
        except Exception:
            pass


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
        current_plan = estimate_plan(current)

        def _is_current(acc):
            return is_same_account(acc, current)

        # 전체 계정 사용량 가져오기 (list와 동일)
        usage_map = {}
        token_status_map = {}

        def _fetch_for_account(acc):
            if _is_current(acc):
                usage, ts = _fetch_usage_from_api(include_token_status=True)
                return (acc["id"], usage, ts)
            else:
                cred_filename = acc.get("credentialFile")
                if cred_filename:
                    credential_path = ACCOUNTS_DIR / cred_filename
                    if credential_path.exists():
                        try:
                            credential = json.loads(credential_path.read_text())
                            usage, ts = _fetch_usage_from_api(
                                credential, include_token_status=True,
                                credential_file=credential_path
                            )
                            return (acc["id"], usage, ts)
                        except Exception:
                            pass
                return (acc["id"], None, TokenStatus.NO_TOKEN)

        # 현재 계정 먼저, 나머지 순차 (429 방지)
        current_acc = None
        other_accs = []
        for acc in index["accounts"]:
            if _is_current(acc):
                current_acc = acc
            else:
                other_accs.append(acc)

        if current_acc:
            try:
                acc_id, usage, ts = _fetch_for_account(current_acc)
                usage_map[acc_id] = usage
                token_status_map[acc_id] = ts
            except Exception:
                pass

        if other_accs:
            time.sleep(1)
            for acc in other_accs:
                try:
                    acc_id, usage, ts = _fetch_for_account(acc)
                    usage_map[acc_id] = usage
                    token_status_map[acc_id] = ts
                except Exception:
                    pass
                time.sleep(1)

        # 계정 목록 출력
        for i, acc in enumerate(index["accounts"], 1):
            is_current = _is_current(acc)
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
                    except Exception:
                        plan = "?"
                else:
                    plan = "?"

            plan_colors = {"Free": Colors.DIM, "Pro": Colors.CYAN, "Team": Colors.MAGENTA, "Max": Colors.YELLOW, "Max5": Colors.YELLOW, "Max20": Colors.GREEN}
            plan_badge = c(plan_colors.get(plan, Colors.DIM), f"[{plan}]")

            acc_org_name = acc.get("organizationName", "")
            org_badge = f" {c(Colors.MAGENTA, f'@{acc_org_name}')}" if _is_real_org(acc_org_name) else ""
            print(f"  [{i}] {marker} {acc['name']}{org_badge} {plan_badge}")
            print(f"      {c(Colors.DIM, acc['email'])}")

            # 사용량 표시 (전체 계정)
            real_usage = usage_map.get(acc["id"])
            ts = token_status_map.get(acc["id"], TokenStatus.NO_TOKEN)

            if ts == TokenStatus.EXPIRED:
                print(f"      {c(Colors.RED, '⚠ 토큰 만료')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif ts == TokenStatus.INVALID:
                print(f"      {c(Colors.RED, '⚠ 토큰 무효')} - {c(Colors.YELLOW, '재로그인 필요')}")
            elif ts == TokenStatus.NO_TOKEN:
                print(f"      {c(Colors.DIM, '(credential 없음)')}")
            elif ts == TokenStatus.ERROR:
                print(f"      {c(Colors.YELLOW, '⚠ 연결 오류')}")
            elif real_usage:
                now = datetime.now(real_usage["sevenDayResetAt"].tzinfo) if real_usage.get("sevenDayResetAt") else datetime.now()
                if real_usage.get("fiveHour") is not None:
                    percentage = real_usage["fiveHour"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage.get("fiveHourResetAt"):
                        remaining = real_usage["fiveHourResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {hours}h {minutes}m"
                    print(f"      {c(Colors.DIM, '현재')} {bar} {percentage}%{reset_str}")
                if real_usage.get("sevenDay") is not None:
                    percentage = real_usage["sevenDay"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage.get("sevenDayResetAt"):
                        remaining = real_usage["sevenDayResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {hours}h {minutes}m"
                    print(f"      {c(Colors.DIM, '주간')} {bar} {percentage}%{reset_str}")

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
    if is_same_account(account, current):
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

    # 오래된 백업 정리
    _cleanup_old_backups(backup_dir, "claude", keep=5)
    _cleanup_old_backups(backup_dir, "credential", keep=5)

    # Replace oauthAccount
    claude_data["oauthAccount"] = new_oauth
    save_claude_json(claude_data)

    # Replace Keychain credential (토큰 갱신 포함)
    credential_switched = False
    token_status = "no_credential"  # no_credential | fresh | refreshed | permanent_fail | transient_fail
    credential_file = account.get("credentialFile")

    # credentialFile이 null인 경우: 예상 파일명으로 디스크 확인 후 index 복구
    if not credential_file:
        expected_file = f"credential_{account['id']}.json"
        expected_path = ACCOUNTS_DIR / expected_file
        if expected_path.exists():
            # 파일은 있지만 index에 기록 안 됨 → index 복구
            credential_file = expected_file
            for i, acc in enumerate(index["accounts"]):
                if acc["id"] == account_id:
                    index["accounts"][i]["credentialFile"] = credential_file
                    break
            save_index(index)
            log("INFO", f"switch: credentialFile index 복구됨 ({account['name']})")

    if credential_file:
        credential_path = ACCOUNTS_DIR / credential_file
        if credential_path.exists():
            new_credential, error = _safe_refresh_credential(credential_path, account['id'], skip_fresh_check=True)
            if new_credential is not None and not error:
                token_status = "refreshed"
                log("INFO", f"switch: 토큰 갱신 성공 ({account['name']})")
            elif error and error.startswith("skip:"):
                # 락 충돌: 파일에서 직접 읽어서 사용
                if new_credential is None:
                    try:
                        new_credential = json.loads(credential_path.read_text())
                    except (json.JSONDecodeError, IOError):
                        new_credential = None
                token_status = "fresh"
            else:
                error_type = classify_refresh_error(error)
                token_status = "permanent_fail" if error_type == RefreshError.PERMANENT else "transient_fail"
                log("WARN", f"switch: 토큰 갱신 실패 ({account['name']}, {error_type}): {error}")
                # 실패해도 기존 credential 파일에서 읽어서 적용 시도
                try:
                    new_credential = json.loads(credential_path.read_text())
                except (json.JSONDecodeError, IOError):
                    new_credential = None

            if new_credential and set_keychain_credential(new_credential):
                credential_switched = True

    # Update active account
    index["activeAccountId"] = account_id
    save_index(index)

    # Plan 정보
    plan = account.get("plan", "?")
    plan_colors = {"Free": Colors.DIM, "Pro": Colors.CYAN, "Team": Colors.MAGENTA, "Max": Colors.YELLOW, "Max5": Colors.YELLOW, "Max20": Colors.GREEN}
    plan_badge = c(plan_colors.get(plan, Colors.DIM), f"[{plan}]")

    print()
    print(c(Colors.GREEN, f"  계정 전환 완료: {account['name']} {plan_badge}"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  {account['email']}")

    if credential_switched:
        if token_status == "refreshed":
            print(f"  OAuth: {c(Colors.GREEN, '토큰 갱신 후 교체 완료')}")
        elif token_status == "permanent_fail":
            print(f"  OAuth: {c(Colors.RED, '토큰 만료 (재로그인 필요)')}")
            print(f"  {c(Colors.DIM, '→ /login 으로 재인증하세요')}")
        elif token_status == "transient_fail":
            print(f"  OAuth: {c(Colors.YELLOW, '토큰 갱신 실패 (네트워크 문제 가능)')}")
            print(f"  {c(Colors.DIM, '→ 네트워크 확인 후 /account check 로 상태를 확인하세요')}")
        else:
            print(f"  OAuth: {c(Colors.GREEN, '토큰 교체 완료')}")

        # 전환된 계정의 사용량 표시
        try:
            real_usage = _fetch_usage_from_api()
            if real_usage:
                now = datetime.now(real_usage["sevenDayResetAt"].tzinfo) if real_usage.get("sevenDayResetAt") else datetime.now()
                if real_usage.get("fiveHour") is not None:
                    percentage = real_usage["fiveHour"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage.get("fiveHourResetAt"):
                        remaining = real_usage["fiveHourResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {format_time_remaining(hours, minutes)}"
                    print(f"  {c(Colors.DIM, '현재')} {bar} {percentage}%{reset_str}")
                if real_usage.get("sevenDay") is not None:
                    percentage = real_usage["sevenDay"]
                    bar = make_progress_bar(percentage, width=12)
                    reset_str = ""
                    if real_usage.get("sevenDayResetAt"):
                        remaining = real_usage["sevenDayResetAt"] - now
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            minutes = int((remaining.total_seconds() % 3600) // 60)
                            reset_str = f" | {c(Colors.CYAN, '⏱')} {format_time_remaining(hours, minutes)}"
                    print(f"  {c(Colors.DIM, '주간')} {bar} {percentage}%{reset_str}")
        except Exception:
            pass  # 사용량 조회 실패 시 무시 (전환 자체는 성공)
    else:
        print(f"  OAuth: {c(Colors.YELLOW, '토큰 없음 (재로그인 필요)')}")
        print(f"  {c(Colors.DIM, '→ /login 후 /account:add 로 credential을 저장하세요')}")

    print()
    print(c(Colors.YELLOW, "  Claude Code를 재시작해야 변경사항이 적용됩니다."))
    print(c(Colors.DIM, "  터미널에서 'exit' 후 다시 'claude' 실행"))
    print()
    return True
