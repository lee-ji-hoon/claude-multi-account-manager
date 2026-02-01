"""
cmd_check, cmd_refresh_all, cmd_refresh_expiring: Token management commands
"""
import json
import os
import sys

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index, get_current_account
from ..keychain import get_keychain_credential
from ..token import TokenStatus, check_token_status, refresh_access_token, is_token_expiring_soon
from ..api import _fetch_usage_from_api
from ..account import detect_plan_from_credential


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


def cmd_refresh_expiring(hours=1):
    """만료 임박 토큰만 갱신 (UserPromptSubmit Hook용)

    세션 중간에 토큰 만료를 방지하기 위해,
    만료 N시간 이내인 토큰만 선택적으로 갱신합니다.

    Args:
        hours: 만료 임박 기준 시간 (기본 1시간)

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
        # 현재 계정은 스킵 (이미 활성 상태)
        if acc["email"] == current_email:
            continue

        credential_file = acc.get("credentialFile")
        if not credential_file:
            continue

        credential_path = ACCOUNTS_DIR / credential_file
        if not credential_path.exists():
            continue

        try:
            credential = json.loads(credential_path.read_text())
        except (json.JSONDecodeError, IOError):
            continue

        # 만료 임박 토큰만 갱신
        if not is_token_expiring_soon(credential, hours=hours):
            continue

        new_credential, error = refresh_access_token(credential)
        if new_credential:
            credential_path.write_text(json.dumps(new_credential, indent=2, ensure_ascii=False))
            os.chmod(credential_path, 0o600)

            detected_plan = detect_plan_from_credential(new_credential)
            acc["plan"] = detected_plan

            refreshed_count += 1
            print(f"[refresh] {acc['id']}: 만료 임박 토큰 갱신됨 [{detected_plan}]")

    if refreshed_count > 0:
        save_index(index)

    return refreshed_count
