"""Fail-closed provider switching for Switchboard's machine-readable seam."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

from .account import is_same_account
from . import codex_provider
from .config import ACCOUNTS_DIR
from .grok_profiles import get_grok_launch_contract
from .keychain import (
    KEYCHAIN_ACCOUNT,
    KEYCHAIN_SERVICE,
    get_keychain_credential,
    set_keychain_credential,
)
from .owner import credential_matches_slot
from .storage import (
    get_current_account,
    load_claude_json,
    load_index,
    save_claude_json,
    save_index,
)
from .token import is_credential_valid


@dataclass(frozen=True)
class SwitchResult:
    ok: bool
    provider: str
    requestedAccountID: str
    activeAccountID: Optional[str]
    restartRequired: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _result(
    ok: bool,
    provider: str,
    requested_account_id: str,
    active_account_id: Optional[str],
    restart_required: bool,
    message: str,
) -> SwitchResult:
    return SwitchResult(
        ok=ok,
        provider=provider,
        requestedAccountID=requested_account_id,
        activeAccountID=active_account_id,
        restartRequired=restart_required,
        message=message,
    )


def _load_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("파일을 읽을 수 없습니다: %s" % path.name) from error
    if not isinstance(value, dict):
        raise ValueError("JSON 객체가 아닙니다: %s" % path.name)
    return value


def _account_file(filename: object) -> Path:
    if not isinstance(filename, str) or not filename:
        raise ValueError("저장 파일 정보가 없습니다")
    root = ACCOUNTS_DIR.resolve()
    path = (ACCOUNTS_DIR / filename).resolve()
    if path.parent != root:
        raise ValueError("계정 저장소 밖의 파일은 사용할 수 없습니다")
    return path


def _delete_keychain_credential() -> bool:
    try:
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
            ],
            capture_output=True,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _restore_claude_state(
    claude_data: Dict[str, Any],
    credential: Optional[Dict[str, Any]],
    index: Dict[str, Any],
    expected_claude: Dict[str, Any],
    expected_credential: Dict[str, Any],
    expected_index: Dict[str, Any],
) -> bool:
    """Rollback only values written by this transaction (compare-and-swap)."""
    restored = True
    current_claude = load_claude_json()
    if current_claude == expected_claude:
        try:
            save_claude_json(claude_data)
        except OSError:
            restored = False
    elif current_claude != claude_data:
        restored = False

    current_credential = get_keychain_credential()
    if current_credential == expected_credential:
        if credential is None:
            restored = _delete_keychain_credential() and restored
        else:
            restored = set_keychain_credential(credential) and restored
    elif current_credential != credential:
        # A concurrent refresh/login owns this newer state. Never overwrite it.
        restored = False

    current_index = load_index()
    if current_index == expected_index:
        try:
            save_index(index)
        except OSError:
            restored = False
    elif current_index != index:
        restored = False
    try:
        profile_matches = load_claude_json() == claude_data
        credential_matches = get_keychain_credential() == credential
        index_matches = load_index() == index
        return restored and profile_matches and credential_matches and index_matches
    except (OSError, ValueError):
        return False


def _switch_claude(account_id: str) -> SwitchResult:
    index = load_index()
    account = next(
        (item for item in index.get("accounts", []) if item.get("id") == account_id),
        None,
    )
    if not account:
        return _result(False, "claude", account_id, None, False, "저장된 Claude 계정을 찾을 수 없습니다")

    try:
        profile = _load_object(_account_file(account.get("profileFile")))
        credential = _load_object(_account_file(account.get("credentialFile")))
    except ValueError as error:
        return _result(False, "claude", account_id, None, False, str(error))
    if not is_same_account(account, profile):
        return _result(False, "claude", account_id, None, False, "프로필 identity가 계정 인덱스와 일치하지 않습니다")
    if not is_credential_valid(credential):
        return _result(False, "claude", account_id, None, False, "저장된 Claude credential이 불완전합니다")
    owner_match = credential_matches_slot(credential, account)
    if owner_match is False:
        return _result(False, "claude", account_id, None, False, "저장된 credential 소유자가 Claude 계정 슬롯과 일치하지 않습니다")
    if owner_match is None:
        return _result(False, "claude", account_id, None, False, "저장된 credential 소유자를 확인할 수 없어 전환하지 않았습니다")

    previous_claude = copy.deepcopy(load_claude_json())
    previous_credential = copy.deepcopy(get_keychain_credential())
    previous_index = copy.deepcopy(index)
    try:
        next_claude = copy.deepcopy(previous_claude)
        next_claude["oauthAccount"] = profile
        next_index = copy.deepcopy(index)
        next_index["activeAccountId"] = account_id
        save_claude_json(next_claude)
        if not set_keychain_credential(credential):
            raise RuntimeError("Keychain 저장 실패")
        current_credential = get_keychain_credential()
        credential_readback_ok = current_credential == credential
        if not credential_readback_ok and current_credential:
            credential_readback_ok = credential_matches_slot(current_credential, account) is True
        if get_current_account() != profile or not credential_readback_ok:
            raise RuntimeError("전환 후 인증 저장소 readback이 일치하지 않습니다")
        save_index(next_index)
        # Index is metadata, but it is part of the public account ID readback.
        if load_index().get("activeAccountId") != account_id:
            raise RuntimeError("전환 후 계정 인덱스 readback이 일치하지 않습니다")
    except (OSError, RuntimeError) as error:
        restored = _restore_claude_state(
            previous_claude,
            previous_credential,
            previous_index,
            next_claude,
            credential,
            next_index,
        )
        suffix = "" if restored else " (이전 인증 상태 자동 복구 실패)"
        return _result(False, "claude", account_id, None, False, "%s%s" % (error, suffix))

    return _result(
        True,
        "claude",
        account_id,
        account_id,
        True,
        "Claude 계정 전환 완료; 새 Claude Code 세션에서 적용됩니다",
    )


def _switch_codex(account_id: str) -> SwitchResult:
    index = codex_provider.load_codex_index()
    account = next(
        (item for item in index.get("accounts", []) if item.get("id") == account_id),
        None,
    )
    if not account:
        return _result(False, "codex", account_id, None, False, "저장된 Codex 계정을 찾을 수 없습니다")
    ok, message = codex_provider.switch_codex_account(account)
    expected_upstream_id = account.get("account_id")
    if not ok or not expected_upstream_id:
        return _result(False, "codex", account_id, None, False, message)
    active_upstream_id = codex_provider.get_current_codex_account_id()
    if active_upstream_id != expected_upstream_id:
        return _result(False, "codex", account_id, None, False, "전환 후 Codex auth readback이 일치하지 않습니다")
    return _result(
        True,
        "codex",
        account_id,
        account_id,
        True,
        "Codex 계정 전환 완료; 새 Codex 세션에서 적용됩니다",
    )


def _switch_grok(account_id: str) -> SwitchResult:
    try:
        contract = get_grok_launch_contract(account_id)
    except ValueError as error:
        return _result(False, "grok", account_id, None, False, str(error))
    grok_home = contract["environment"]["GROK_HOME"]
    return _result(
        False,
        "grok",
        account_id,
        None,
        True,
        "현재 세션은 바뀌지 않습니다. GROK_HOME=%s 로 새 Grok 프로세스를 실행하세요" % grok_home,
    )


def switch_provider(provider: str, account_id: str) -> SwitchResult:
    normalized = provider.strip().lower()
    try:
        if normalized == "claude":
            return _switch_claude(account_id)
        if normalized == "codex":
            return _switch_codex(account_id)
        if normalized == "grok":
            return _switch_grok(account_id)
        if normalized in ("agy", "gemini", "antigravity"):
            return _result(
                False,
                normalized,
                account_id,
                None,
                False,
                "%s 계정 전환은 안전한 공식 로컬 seam이 없어 지원하지 않습니다" % normalized,
            )
        return _result(False, normalized, account_id, None, False, "지원하지 않는 공급자입니다")
    except Exception:
        # Keep the machine-readable seam intact without exposing filesystem,
        # credential, or subprocess details in its error message.
        return _result(
            False,
            normalized,
            account_id,
            None,
            False,
            "계정 전환 중 내부 오류가 발생했습니다",
        )
