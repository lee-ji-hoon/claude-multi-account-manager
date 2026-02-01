"""
cmd_remove: Remove registered accounts
"""
import json

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index, get_current_account


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
