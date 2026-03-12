"""
cmd_add, cmd_auto_add: Add/register accounts
"""
import json
import os
import sys
from datetime import datetime

from ..config import ACCOUNTS_DIR
from ..ui import c, Colors
from ..storage import load_index, save_index, get_current_account
from ..keychain import get_keychain_credential
from ..account import detect_plan_from_credential, generate_account_name, generate_account_id, is_account_duplicate, get_org_info, _is_real_org
from ..token import is_credential_valid


def cmd_add(name=None):
    """현재 계정을 프로필로 저장"""
    current = get_current_account()
    if not current:
        print("현재 로그인된 계정이 없습니다. 먼저 /login 하세요.")
        return False

    email = current.get("emailAddress", "")
    if not email:
        print("계정 이메일을 찾을 수 없습니다.")
        return False

    # Organization 정보 추출
    org_name, org_uuid = get_org_info(current)

    # Generate ID from email + org
    account_id = generate_account_id(email, org_name, org_uuid)

    if not name:
        name = current.get("displayName", account_id)

    index = load_index()

    # Check if already exists (email + org)
    for acc in index["accounts"]:
        if acc["email"] != email:
            continue
        stored_org = acc.get("organizationUuid")
        if stored_org and org_uuid and stored_org != org_uuid:
            continue
        if stored_org and not org_uuid:
            continue
        if not stored_org and org_uuid and _is_real_org(org_name):
            continue
        # Match found
        print(f"이미 등록된 계정입니다: {acc['id']} ({acc['name']})")
        print()
        print(c(Colors.DIM, "  " + "─" * 40))
        print(f"  [1] 토큰만 갱신 (재로그인 없이)")
        print(f"  [2] 새로 로그인 후 갱신")
        print(f"  [3] 취소")
        print(c(Colors.DIM, "  " + "─" * 40))
        print(f"  {c(Colors.DIM, '번호를 입력하세요 (기본: 1)')}: ", end="", flush=True)

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False

        if choice == "1" or choice == "":
            # 기존 계정 토큰만 갱신
            credential = get_keychain_credential()
            if credential and is_credential_valid(credential):
                credential_path = ACCOUNTS_DIR / acc.get("credentialFile", f"credential_{acc['id']}.json")
                credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
                os.chmod(credential_path, 0o600)

                # Plan도 자동 감지해서 갱신 + circuit breaker 해제
                detected_plan = detect_plan_from_credential(credential)
                for i, a in enumerate(index["accounts"]):
                    if a["id"] == acc["id"]:
                        index["accounts"][i]["plan"] = detected_plan
                        index["accounts"][i].pop("refreshBlocked", None)
                        index["accounts"][i].pop("refreshBlockedAt", None)
                        break
                save_index(index)

                print()
                print(c(Colors.GREEN, f"  토큰 갱신 완료: {acc['id']}"))
                print(f"  Plan: {detected_plan} (자동 감지)")
            elif credential:
                print(c(Colors.YELLOW, "  Keychain credential이 불완전합니다. 잠시 후 다시 시도하세요."))
            else:
                print(c(Colors.RED, "  토큰을 가져올 수 없습니다."))
            return False
        elif choice == "2":
            # 새로 로그인 요청
            print()
            print(c(Colors.YELLOW, "  새로 로그인해주세요: /login"))
            print(c(Colors.DIM, "  로그인 후 다시 /account-add 를 실행하세요."))
            return "need_login"
        else:
            print("취소됨")
            return False

    # credential에서 Plan 자동 감지
    credential = get_keychain_credential()
    detected_plan = None
    if credential:
        detected_plan = detect_plan_from_credential(credential)

    # Plan 확인 (자동 감지 결과 표시)
    print()
    if detected_plan and detected_plan != "Free":
        print(c(Colors.GREEN, f"  Plan 자동 감지: {detected_plan}"))
        plan = detected_plan
    else:
        # 자동 감지 실패 시 수동 선택
        print(c(Colors.BOLD, "  Plan 선택"))
        print(c(Colors.DIM, "  " + "─" * 40))
        plans = ["Free", "Pro", "Team", "Max5", "Max20"]
        for i, p in enumerate(plans, 1):
            desc = ""
            if p == "Max5":
                desc = c(Colors.DIM, " (5 프로젝트)")
            elif p == "Max20":
                desc = c(Colors.DIM, " (20 프로젝트)")
            print(f"  [{i}] {p}{desc}")
        print(c(Colors.DIM, "  " + "─" * 40))
        print(f"  {c(Colors.DIM, '번호를 입력하세요 (기본: 1)')}: ", end="", flush=True)

        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("취소됨")
            return False

        if choice == "":
            plan = "Free"
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(plans):
                    plan = plans[idx]
                else:
                    plan = "Free"
            except ValueError:
                plan = "Free"

    # Save profile
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # Save credential from Keychain
    credential_file = f"credential_{account_id}.json"
    credential_path = ACCOUNTS_DIR / credential_file
    credential = get_keychain_credential()
    has_credential = False
    if credential and is_credential_valid(credential):
        credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
        os.chmod(credential_path, 0o600)
        has_credential = True
    elif credential:
        print(c(Colors.YELLOW, "  Keychain credential이 불완전합니다. 토큰 저장을 건너뜁니다."))

    # Update index
    # credentialFile은 항상 파일명으로 저장 (null이면 switch 시 credential 교체가 스킵됨)
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

    print()
    print(c(Colors.GREEN, "  계정 저장 완료"))
    print(c(Colors.DIM, "  " + "─" * 40))
    print(f"  ID: {account_id}")
    print(f"  이름: {name}")
    print(f"  이메일: {email}")
    if _is_real_org(org_name):
        print(f"  조직: {org_name}")
    print(f"  Plan: {plan}")
    if has_credential:
        print(f"  OAuth: {c(Colors.GREEN, '저장됨')}")
    else:
        print(f"  OAuth: {c(Colors.YELLOW, '저장 실패 (수동 로그인 필요)')}")
    print()
    return True


def cmd_auto_add():
    """Hook용 자동 계정 등록 (비대화형)

    - 중복 시 조용히 스킵 (exit 0)
    - Plan 자동 감지 (credential에서)
    - 이름 자동 생성 (displayName > email)
    - 조직 컨텍스트 자동 감지 (같은 email이라도 조직이 다르면 별도 계정)

    Returns:
        bool: True=등록됨, False=스킵/실패
    """
    # 1. 현재 계정 정보 확인
    current = get_current_account()
    if not current:
        return False  # 로그인 안 됨

    email = current.get("emailAddress", "")
    if not email:
        return False  # 이메일 없음

    # Organization 정보 추출
    org_name, org_uuid = get_org_info(current)

    # 2. 중복 확인 (조용히 스킵) - email + org
    if is_account_duplicate(email, org_uuid):
        return False  # 이미 등록됨

    # 4. credential에서 Plan 감지
    credential = get_keychain_credential()
    if not credential:
        print("[auto-add] credential을 읽을 수 없습니다.", file=sys.stderr)
        return False
    if not is_credential_valid(credential):
        print("[auto-add] credential이 불완전합니다 (토큰 갱신 중일 수 있음).", file=sys.stderr)
        return False

    plan = detect_plan_from_credential(credential)

    # 5. 이름 자동 생성
    name = generate_account_name(current, email)

    # 5. ID 생성 (org 포함)
    account_id = generate_account_id(email, org_name, org_uuid)

    # 7. 프로필 저장
    profile_file = f"profile_{account_id}.json"
    profile_path = ACCOUNTS_DIR / profile_file
    profile_path.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    os.chmod(profile_path, 0o600)

    # 8. credential 저장
    credential_file = f"credential_{account_id}.json"
    credential_path = ACCOUNTS_DIR / credential_file
    credential_path.write_text(json.dumps(credential, indent=2, ensure_ascii=False))
    os.chmod(credential_path, 0o600)

    # 9. index 업데이트
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

    # 9. 성공 메시지
    org_suffix = f" @{org_name}" if _is_real_org(org_name) else ""
    print(f"[auto-add] 계정 등록됨: {name} ({email}{org_suffix}) [{plan}]")
    return True
