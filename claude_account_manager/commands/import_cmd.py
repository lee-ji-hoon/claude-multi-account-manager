"""
cmd_import: Import account from another machine
"""
import json
import os
import sys
from datetime import datetime

from pathlib import Path

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index, load_claude_json
from ..keychain import set_keychain_credential
from ..account import detect_plan_from_credential, is_account_duplicate, generate_account_id, get_org_info, _is_real_org


def cmd_import(json_data=None):
    """다른 컴의 계정 정보를 가져와서 등록

    Args:
        json_data (str, optional): JSON 형식의 계정 정보, 또는 파일 경로. 없으면 대화형 입력.

    사용자로부터 다음 정보를 입력받음:
    1. 다른 컴의 ~/.claude.json 내용 (profile)
    2. 다른 컴의 Keychain credential (OAuth 토큰)

    또는 통합 JSON을 입력받을 수도 있음:
    {
        "profile": {...},
        "credential": {...}
    }

    또는 claude_auth.json 형식:
    {
        "oauthAccount": {...},
        ...
    }
    """
    # 인자로 JSON이 전달된 경우 직접 처리
    if json_data:
        return _process_import_data(json_data)

    print()
    print(c(Colors.BOLD, "다른 컴의 계정 가져오기"))
    print(c(Colors.DIM, "─" * 50))
    print()

    # 입력 방식 선택
    print("어떤 방식으로 정보를 입력하시겠어요?")
    print()
    print(c(Colors.DIM, "  " + "─" * 50))
    print("  [1] 통합 JSON 입력 (권장)")
    print("  [2] 단계별 입력 (profile → credential)")
    print(c(Colors.DIM, "  " + "─" * 50))
    print(f"  {c(Colors.DIM, '번호를 입력하세요 (기본: 1)')}: ", end="", flush=True)

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    if choice == "2":
        return _import_step_by_step()
    else:
        return _import_unified_json()


def _process_import_data(data_or_path):
    """JSON 데이터 또는 파일 경로에서 계정 정보를 처리

    Args:
        data_or_path (str): JSON 문자열 또는 파일 경로

    Returns:
        bool: 성공 여부
    """
    # 파일 경로인지 확인
    if data_or_path.startswith("/") or data_or_path.startswith("~"):
        path = Path(data_or_path).expanduser()
        if path.exists() and path.is_file():
            try:
                json_data = path.read_text(encoding='utf-8')
                print(c(Colors.CYAN, f"  파일에서 읽음: {path}"))
            except Exception as e:
                print(c(Colors.RED, f"  파일 읽기 오류: {e}"))
                return False
        else:
            # 파일이 아니면 그냥 JSON 문자열로 취급
            json_data = data_or_path
    else:
        json_data = data_or_path

    # JSON 파싱
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
        return False

    # 형식 감지 및 처리
    # 1. 표준 export 형식: { "profile": {...}, "credential": {...} }
    if "profile" in data and "credential" in data:
        profile = data.get("profile")
        credential = data.get("credential")
        if profile and credential:
            return _register_account(profile, credential)
        else:
            print(c(Colors.RED, "  profile과 credential이 모두 필요합니다."))
            return False

    # 2. claude_auth.json 형식: { "oauthAccount": {...}, ... }
    if "oauthAccount" in data:
        profile = data.get("oauthAccount")
        # credential은 없으므로 사용자에게 입력받아야 함
        print(c(Colors.YELLOW, "  ⚠ claude_auth.json 형식 감지 (credential 없음)"))
        print(c(Colors.DIM, "  OAuth 토큰 정보를 입력하세요"))
        print(c(Colors.DIM, "  입력 형식: "), end="", flush=True)

        try:
            credential_str = input().strip()
            credential = json.loads(credential_str)
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False
        except json.JSONDecodeError as e:
            print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
            return False

        return _register_account(profile, credential)

    # 3. 기타 형식: profile 또는 oauthAccount 필요
    print(c(Colors.RED, "  알 수 없는 형식입니다."))
    print(c(Colors.DIM, "  필요한 형식:"))
    print(c(Colors.DIM, '    표준: { "profile": {...}, "credential": {...} }'))
    print(c(Colors.DIM, '    또는: { "oauthAccount": {...}, ... }'))
    return False


def _import_unified_json():
    """통합 JSON 형식으로 입력받음"""
    print()
    print(c(Colors.YELLOW, "  다음과 같은 JSON 형식으로 입력하세요:"))
    print()
    print(c(Colors.DIM, """  {
    "profile": { ... ~/.claude.json의 oauthAccount 내용 ... },
    "credential": { ... Keychain의 credential 내용 ... }
  }"""))
    print()
    print(c(Colors.DIM, "  Ctrl+D (Mac) 또는 Ctrl+Z+Enter (Windows)로 입력 종료"))
    print(c(Colors.DIM, "  또는 한 줄로 입력: "), end="", flush=True)

    try:
        # 첫 줄 입력 (한 줄 JSON 가능)
        first_line = input().strip()

        # 한 줄 JSON인지 확인
        if first_line.startswith('{') and first_line.endswith('}'):
            json_str = first_line
        else:
            # 여러 줄 입력
            lines = [first_line]
            print(c(Colors.DIM, "  나머지 입력: "), end="", flush=True)
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            json_str = "\n".join(lines)
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print()
        print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
        return False

    profile = data.get("profile")
    credential = data.get("credential")

    if not profile:
        print(c(Colors.RED, "  profile 정보가 없습니다."))
        return False

    if not credential:
        print(c(Colors.RED, "  credential 정보가 없습니다."))
        return False

    return _register_account(profile, credential)


def _import_step_by_step():
    """단계별로 입력받음"""
    print()
    print(c(Colors.YELLOW, "  1단계: 다른 컴의 ~/.claude.json에서 oauthAccount 부분을 입력하세요"))
    print(c(Colors.DIM, "  (예: {\"emailAddress\": \"...\", ...})"))
    print(c(Colors.DIM, "  입력: "), end="", flush=True)

    try:
        profile_str = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    try:
        profile = json.loads(profile_str)
    except json.JSONDecodeError as e:
        print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
        return False

    print()
    print(c(Colors.YELLOW, "  2단계: 다른 컴의 Keychain credential을 입력하세요"))
    print(c(Colors.DIM, "  (예: {\"access_token\": \"...\", ...})"))
    print(c(Colors.DIM, "  입력: "), end="", flush=True)

    try:
        credential_str = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("취소됨")
        return False

    try:
        credential = json.loads(credential_str)
    except json.JSONDecodeError as e:
        print(c(Colors.RED, f"  JSON 파싱 오류: {e}"))
        return False

    return _register_account(profile, credential)


def _register_account(profile, credential):
    """계정 정보를 바탕으로 실제 등록

    Args:
        profile: oauthAccount 정보
        credential: OAuth 토큰 정보

    Returns:
        bool: 성공 여부
    """
    # 이메일 확인
    email = profile.get("emailAddress", "")
    if not email:
        print(c(Colors.RED, "  프로필에 emailAddress가 없습니다."))
        return False

    # Organization 정보 추출
    org_name, org_uuid = get_org_info(profile)

    # 중복 확인 (email + org)
    if is_account_duplicate(email, org_uuid):
        org_suffix = f" ({org_name})" if _is_real_org(org_name) else ""
        print(c(Colors.RED, f"  이미 등록된 계정입니다: {email}{org_suffix}"))
        return False

    # ID 생성 (org 포함)
    account_id = generate_account_id(email, org_name)

    # 계정명 결정
    name = profile.get("displayName", account_id)

    # Plan 자동 감지
    plan = detect_plan_from_credential(credential)

    # 프로필 저장
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # Credential을 Keychain에 저장
    keychain_saved = set_keychain_credential(credential)

    # Credential도 파일로 저장
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
        "createdAt": datetime.now().isoformat()
    }
    if org_name:
        account_entry["organizationName"] = org_name
    if org_uuid:
        account_entry["organizationUuid"] = org_uuid
    index["accounts"].append(account_entry)
    index["activeAccountId"] = account_id
    save_index(index)

    # 성공 메시지
    print()
    print(c(Colors.GREEN, "  계정 가져오기 완료"))
    print(c(Colors.DIM, "  " + "─" * 50))
    print(f"  ID: {account_id}")
    print(f"  이름: {name}")
    print(f"  이메일: {email}")
    if _is_real_org(org_name):
        print(f"  조직: {org_name}")
    print(f"  Plan: {plan}")
    if keychain_saved:
        print(f"  Keychain: {c(Colors.GREEN, '저장됨')}")
    else:
        print(f"  Keychain: {c(Colors.YELLOW, '저장 실패 (파일만 저장됨)')}")
    print()

    return True
