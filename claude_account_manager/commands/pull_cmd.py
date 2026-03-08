"""
cmd_pull: Pull account data from Telegram (sent by another machine's push).

Flow:
1. Read pinned message from Telegram chat
2. Download the sync document
3. Import accounts that don't exist locally
"""
import json
import os
from datetime import datetime
from pathlib import Path

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index
from ..account import is_account_duplicate, _is_real_org
from ..telegram import load_telegram_config, get_chat, get_file_info, download_file


def cmd_pull(source=None):
    """텔레그램에서 계정 데이터 가져오기

    Args:
        source: 파일 경로 또는 None (텔레그램에서 가져오기)
    """
    if source:
        path = Path(source).expanduser()
        if path.exists() and path.is_file():
            return _import_from_file(path)
        # 파일이 아니면 무시하고 텔레그램에서 시도
        print(c(Colors.YELLOW, f"  파일 없음: {source}"))
        print(c(Colors.DIM, "  텔레그램에서 가져오기 시도..."))

    return _pull_from_telegram()


def _pull_from_telegram():
    """텔레그램 pinned message에서 계정 데이터 다운로드"""
    tg_config = load_telegram_config()
    if not tg_config:
        print(c(Colors.RED, "  텔레그램 설정이 없습니다."))
        print(c(Colors.DIM, "  ~/.claude/hooks/telegram-config.json 확인"))
        return False

    bot_token = tg_config.get("bot_token")
    chat_id = tg_config.get("chat_id")

    print()
    print(c(Colors.BOLD, "  텔레그램에서 계정 데이터 가져오는 중..."))

    try:
        # pinned message 조회
        chat_info = get_chat(bot_token, chat_id)
        if not chat_info.get("ok"):
            print(c(Colors.RED, "  채팅 정보를 가져올 수 없습니다."))
            return False

        pinned = chat_info.get("result", {}).get("pinned_message")
        if not pinned:
            print(c(Colors.YELLOW, "  고정된 메시지가 없습니다."))
            print(c(Colors.DIM, "  먼저 다른 맥에서 /account:push 실행"))
            return False

        # 문서 확인
        document = pinned.get("document")
        if not document:
            print(c(Colors.YELLOW, "  고정된 메시지에 파일이 없습니다."))
            return False

        file_name = document.get("file_name", "")
        if not file_name.startswith("claude_accounts_"):
            print(c(Colors.YELLOW, f"  계정 동기화 파일이 아닙니다: {file_name}"))
            return False

        # 캡션 정보 출력
        caption = pinned.get("caption", "")
        if caption:
            print(c(Colors.CYAN, f"  {caption}"))
            print()

        # 파일 다운로드
        file_id = document["file_id"]
        file_result = get_file_info(bot_token, file_id)
        if not file_result.get("ok"):
            print(c(Colors.RED, "  파일 정보를 가져올 수 없습니다."))
            return False

        file_data = download_file(bot_token, file_result["result"]["file_path"])
        bundle = json.loads(file_data.decode())

        return _process_sync_bundle(bundle)

    except Exception as e:
        print(c(Colors.RED, f"  오류: {e}"))
        return False


def _import_from_file(path):
    """로컬 파일에서 계정 데이터 가져오기"""
    print()
    print(c(Colors.BOLD, f"  파일에서 가져오기: {path.name}"))

    try:
        bundle = json.loads(path.read_text())
        return _process_sync_bundle(bundle)
    except json.JSONDecodeError as e:
        print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
        return False


def _process_sync_bundle(bundle):
    """동기화 번들 처리 - 새 계정만 등록"""
    if bundle.get("type") != "claude_account_sync":
        print(c(Colors.RED, "  올바른 동기화 파일이 아닙니다."))
        return False

    accounts = bundle.get("accounts", [])
    if not accounts:
        print(c(Colors.YELLOW, "  가져올 계정이 없습니다."))
        return False

    source_host = bundle.get("hostname", "unknown")
    imported = 0
    skipped = 0
    failed = 0

    for acc_data in accounts:
        email = acc_data.get("email", "")
        org_uuid = acc_data.get("organizationUuid")

        # 중복 확인
        if is_account_duplicate(email, org_uuid):
            skipped += 1
            name = acc_data.get("name", email)
            print(f"  {c(Colors.DIM, '-')} {name} ({email}) - 이미 등록됨")
            continue

        # credential과 profile 필수
        credential = acc_data.get("credential")
        profile = acc_data.get("profile")
        if not credential or not profile:
            failed += 1
            print(f"  {c(Colors.RED, '✗')} {email} - credential/profile 없음")
            continue

        try:
            account_id = acc_data.get("id", email.split("@")[0])
            name = acc_data.get("name", account_id)
            plan = acc_data.get("plan", "Unknown")

            # 프로필 저장
            profile_file = f"profile_{account_id}.json"
            profile_path = ACCOUNTS_DIR / profile_file
            profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
            os.chmod(profile_path, 0o600)

            # Credential 저장
            credential_file = f"credential_{account_id}.json"
            credential_path = ACCOUNTS_DIR / credential_file
            credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
            os.chmod(credential_path, 0o600)

            # Index 업데이트
            index = load_index()
            account_entry = {
                "id": account_id,
                "name": name,
                "email": email,
                "plan": plan,
                "profileFile": profile_file,
                "credentialFile": credential_file,
                "createdAt": datetime.now().isoformat(),
                "syncedFrom": source_host,
            }
            org_name = acc_data.get("organizationName", "")
            if org_name:
                account_entry["organizationName"] = org_name
            if org_uuid:
                account_entry["organizationUuid"] = org_uuid

            index["accounts"].append(account_entry)
            save_index(index)

            imported += 1
            org_suffix = f" @{org_name}" if _is_real_org(org_name) else ""
            print(f"  {c(Colors.GREEN, '✓')} {name} ({email}{org_suffix}) [{plan}]")

        except Exception as e:
            failed += 1
            print(f"  {c(Colors.RED, '✗')} {email}: {e}")

    print()
    print(c(Colors.DIM, "  " + "-" * 40))
    summary = f"  가져옴: {c(Colors.GREEN, str(imported))}  스킵: {c(Colors.DIM, str(skipped))}"
    if failed:
        summary += f"  실패: {c(Colors.RED, str(failed))}"
    print(summary)
    print()

    return imported > 0
