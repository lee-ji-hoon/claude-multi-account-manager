"""
cmd_push: Push account data to Telegram for cross-machine sync.

Flow:
1. Bundle all accounts (index + credentials + profiles)
2. Send as document to Telegram
3. Pin the message for easy pull on other machines
"""
import json
import platform
from datetime import datetime

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index
from ..telegram import load_telegram_config, send_document, pin_message


def cmd_push():
    """계정 데이터를 텔레그램으로 전송 (다른 맥에서 pull 가능)"""
    # 1. 텔레그램 설정 확인
    tg_config = load_telegram_config()
    if not tg_config:
        print(c(Colors.RED, "  텔레그램 설정이 없습니다."))
        print(c(Colors.DIM, "  ~/.claude/hooks/telegram-config.json 확인"))
        return False

    bot_token = tg_config.get("bot_token")
    chat_id = tg_config.get("chat_id")
    if not bot_token or not chat_id:
        print(c(Colors.RED, "  bot_token 또는 chat_id가 없습니다."))
        return False

    # 2. 계정 데이터 번들 생성
    index = load_index()
    if not index["accounts"]:
        print(c(Colors.YELLOW, "  등록된 계정이 없습니다."))
        return False

    hostname = platform.node().split('.')[0]
    bundle = {
        "type": "claude_account_sync",
        "version": 1,
        "hostname": hostname,
        "timestamp": datetime.now().isoformat(),
        "accounts": [],
    }

    for acc in index["accounts"]:
        entry = {
            "id": acc.get("id"),
            "name": acc.get("name"),
            "email": acc.get("email"),
            "plan": acc.get("plan"),
        }
        # org 정보
        if acc.get("organizationName"):
            entry["organizationName"] = acc["organizationName"]
        if acc.get("organizationUuid"):
            entry["organizationUuid"] = acc["organizationUuid"]

        # credential 파일 읽기
        cred_file = acc.get("credentialFile")
        if cred_file:
            cred_path = ACCOUNTS_DIR / cred_file
            if cred_path.exists():
                try:
                    entry["credential"] = json.loads(cred_path.read_text())
                except Exception:
                    pass

        # profile 파일 읽기
        profile_file = acc.get("profileFile")
        if profile_file:
            profile_path = ACCOUNTS_DIR / profile_file
            if profile_path.exists():
                try:
                    entry["profile"] = json.loads(profile_path.read_text())
                except Exception:
                    pass

        bundle["accounts"].append(entry)

    # 3. 텔레그램으로 전송
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"claude_accounts_{hostname}_{timestamp}.json"
    filedata = json.dumps(bundle, indent=2, ensure_ascii=False).encode()

    caption = (
        f"\U0001f504 Claude Account Sync\n"
        f"\U0001f4cd {hostname}\n"
        f"\U0001f464 {len(bundle['accounts'])}개 계정\n"
        f"\u23f0 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    print()
    print(c(Colors.BOLD, "  계정 데이터를 텔레그램으로 전송 중..."))

    try:
        result = send_document(bot_token, chat_id, filename, filedata, caption)
        if not result.get("ok"):
            print(c(Colors.RED, f"  전송 실패: {result.get('description', 'unknown')}"))
            return False

        message_id = result["result"]["message_id"]

        # 메시지 고정 (silent)
        try:
            pin_message(bot_token, chat_id, message_id)
        except Exception:
            pass  # 고정 실패해도 전송은 성공

        print(c(Colors.GREEN, f"  \u2713 {len(bundle['accounts'])}개 계정 전송 완료"))
        print(c(Colors.DIM, f"  다른 맥에서: /account:pull"))
        print()
        return True

    except Exception as e:
        print(c(Colors.RED, f"  전송 오류: {e}"))
        return False
