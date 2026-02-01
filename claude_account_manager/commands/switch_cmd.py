"""
cmd_switch: Switch between accounts
"""
import json
import os
from datetime import datetime, timedelta

from ..config import ACCOUNTS_DIR, PLAN_LIMITS_DAILY, PLAN_LIMITS_WEEKLY, RESET_HOURS
from ..ui import c, Colors, format_tokens, make_progress_bar, format_time_remaining
from ..storage import load_index, save_index, load_claude_json, save_claude_json, get_current_account
from ..keychain import get_keychain_credential, set_keychain_credential
from ..account import estimate_plan
from ..api import get_today_usage, get_weekly_usage, get_last_activity_time


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
                    except Exception:
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
