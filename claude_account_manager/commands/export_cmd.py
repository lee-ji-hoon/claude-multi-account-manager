"""
cmd_export_for_import: Export account info for importing to another machine
"""
import json
import sys

from ..storage import get_current_account
from ..keychain import get_keychain_credential
from ..ui import c, Colors


def cmd_export_for_import():
    """현재 로그인된 계정 정보를 JSON으로 내보내기

    다른 컴에서 /account import로 가져갈 수 있는 형식

    Returns:
        dict: 내보낼 계정 정보 (또는 실패 시 None)
    """
    print()
    print(c(Colors.BOLD, "다른 컴에서 사용할 수 있는 계정 정보 추출 중..."))
    print()

    # 1. 현재 로그인된 계정 정보 (profile)
    profile = get_current_account()
    if not profile:
        print(c(Colors.RED, "  로그인된 계정이 없습니다."))
        return None

    email = profile.get("emailAddress", "")
    if not email:
        print(c(Colors.RED, "  프로필에 emailAddress가 없습니다."))
        return None

    # 2. Keychain에서 OAuth 토큰 (credential)
    credential = get_keychain_credential()
    if not credential:
        print(c(Colors.RED, "  Keychain에서 토큰을 읽을 수 없습니다."))
        print(c(Colors.DIM, "  먼저 /login으로 로그인하세요."))
        return None

    # 3. 통합 JSON 생성
    export_data = {
        "profile": profile,
        "credential": credential
    }

    # 4. JSON 출력
    print(c(Colors.GREEN, "  ✓ 계정 정보 추출 완료"))
    print()
    print(c(Colors.BOLD, "다음을 복사해서 다른 컴에서 /account import로 붙여넣으세요:"))
    print()
    print(c(Colors.DIM, "─" * 60))
    json_output = json.dumps(export_data, ensure_ascii=False)
    print(json_output)
    print(c(Colors.DIM, "─" * 60))
    print()

    # 5. 클립보드 복사 시도
    try:
        import subprocess
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(json_output.encode('utf-8'))
        print(c(Colors.GREEN, "  ✓ 클립보드에 복사되었습니다!"))
        print(c(Colors.DIM, "  다른 컴에서: /account import 후 Cmd+V로 붙여넣기"))
    except Exception:
        print(c(Colors.YELLOW, "  클립보드 복사 실패"))
        print(c(Colors.DIM, "  위의 JSON을 수동으로 복사하세요."))

    print()
    return export_data
