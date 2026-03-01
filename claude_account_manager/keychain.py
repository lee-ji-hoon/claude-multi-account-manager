"""
macOS Keychain operations for credential management
"""
import hashlib
import json
import os
import pwd
import subprocess


def get_keychain_service():
    """Claude Code가 사용하는 실제 keychain service name 결정"""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if config_dir:
        hash_suffix = hashlib.sha256(config_dir.encode()).hexdigest()[:8]
        return f"Claude Code-credentials-{hash_suffix}"
    return "Claude Code-credentials"


KEYCHAIN_SERVICE = get_keychain_service()
KEYCHAIN_ACCOUNT = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name


def get_keychain_credential():
    """Keychain에서 Claude Code credential 읽기"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
        return None
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        print(f"  Keychain 읽기 실패: {e}")
        return None


def set_keychain_credential(credential_data):
    """Keychain에 Claude Code credential 저장"""
    try:
        credential_json = json.dumps(credential_data, ensure_ascii=False)

        # 기존 항목 삭제 (있는 경우)
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
            capture_output=True
        )

        # NOTE: macOS security CLI는 -w 인자로만 password를 받을 수 있어
        # 프로세스 목록(ps)에 순간적으로 credential이 노출될 수 있음.
        # security CLI의 제약으로 stdin/pipe 전달은 불가.
        # 새 항목 추가
        result = subprocess.run(
            ["security", "add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w", credential_json],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"  Keychain 저장 실패: {result.stderr}")
            return False
        return True
    except subprocess.SubprocessError as e:
        print(f"  Keychain 저장 실패: {e}")
        return False
