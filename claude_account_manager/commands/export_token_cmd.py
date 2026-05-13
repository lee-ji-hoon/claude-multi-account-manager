"""
cmd_export_token: 계정의 토큰을 eval 가능한 export 라인으로 stdout 출력

usage:
    eval $(python3 -m claude_account_manager export-token <id>)
또는 shell function wrapper(account:export-token)에서 자동 eval.
"""
import json
import sys

from ..config import ACCOUNTS_DIR
from ..storage import load_index
from ..long_lived import is_long_lived_account, format_expiry_dday


def cmd_export_token(account_id):
    """해당 계정의 access token을 export 라인으로 stdout 출력

    long-lived와 일반 OAuth 둘 다 동작. stderr에 만료/경고 정보 출력.
    """
    if not account_id:
        print("사용법: account export-token <id>", file=sys.stderr)
        return False

    index = load_index()
    account = None
    for acc in index["accounts"]:
        if acc["id"] == account_id:
            account = acc
            break

    if not account:
        print(f"계정을 찾을 수 없습니다: {account_id}", file=sys.stderr)
        return False

    cred_file = account.get("credentialFile")
    if not cred_file:
        print(f"credential 파일이 없습니다: {account_id}", file=sys.stderr)
        return False

    cred_path = ACCOUNTS_DIR / cred_file
    if not cred_path.exists():
        print(f"credential 파일이 존재하지 않습니다: {cred_path}", file=sys.stderr)
        return False

    try:
        credential = json.loads(cred_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        print(f"credential 파싱 실패: {e}", file=sys.stderr)
        return False

    token = credential.get("claudeAiOauth", {}).get("accessToken")
    if not token:
        print(f"토큰이 없습니다: {account_id}", file=sys.stderr)
        return False

    if is_long_lived_account(account):
        expires_ms = credential.get("claudeAiOauth", {}).get("expiresAt")
        label, severity = format_expiry_dday(expires_ms)
        if severity == "expired":
            print(f"[warning] long-lived 토큰 만료됨 ({account['name']})", file=sys.stderr)
        elif severity == "danger":
            print(f"[warning] long-lived 토큰 만료 임박 ({label}, {account['name']})",
                  file=sys.stderr)
    else:
        print(f"[info] 일반 OAuth 토큰은 약 8시간 후 만료됩니다 ({account['name']})",
              file=sys.stderr)

    print(f"export CLAUDE_CODE_OAUTH_TOKEN='{token}'")
    return True
