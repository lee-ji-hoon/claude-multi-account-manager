"""
토큰 소유자 검증(owner.py) + keychain→슬롯 write 가드 회귀 테스트

2026-07-08 실사고 재현: switch 직후 ~/.claude.json(oauthAccount)은 아직 이전 계정(soop)인데
Keychain에는 새 계정(gmail) 토큰이 들어간 desync 윈도우에, SessionStart hook의
cmd_refresh_all이 gmail 토큰을 soop 슬롯 credential 파일에 저장하는 교차 오염이 발생했다.
이 테스트는 소유자 검증 가드가 그 저장을 차단하는지 검증한다.

실행: python3 -m unittest discover -s tests
네트워크/Keychain/실제 ~/.claude 접근 없음 (전부 monkeypatch).
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_account_manager import owner
from claude_account_manager.commands import token_cmd

GMAIL_OWNER = {"uuid": "uuid-gmail", "email": "user@gmail.com", "org_uuid": "org-gmail"}
SOOP_OWNER = {"uuid": "uuid-soop", "email": "user@sooplive.com", "org_uuid": "org-soop"}


def _fake_credential(token="tok-1"):
    return {"claudeAiOauth": {"accessToken": token, "refreshToken": "rt", "expiresAt": 9999999999999}}


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestCredentialMatchesIdentity(unittest.TestCase):
    def _match(self, fake_owner, **kwargs):
        with mock.patch.object(owner, "fetch_token_owner", return_value=fake_owner):
            return owner.credential_matches_identity(_fake_credential(), **kwargs)

    def test_uuid_match(self):
        self.assertIs(self._match(GMAIL_OWNER, email="user@gmail.com", account_uuid="uuid-gmail"), True)

    def test_uuid_mismatch(self):
        self.assertIs(self._match(GMAIL_OWNER, email="user@sooplive.com", account_uuid="uuid-soop"), False)

    def test_email_fallback_match_case_insensitive(self):
        self.assertIs(self._match(GMAIL_OWNER, email="User@Gmail.com"), True)

    def test_email_fallback_mismatch(self):
        self.assertIs(self._match(GMAIL_OWNER, email="user@sooplive.com"), False)

    def test_same_account_different_org_is_mismatch(self):
        # 동일 이메일이 여러 org에 속할 때: 계정은 같아도 org 컨텍스트가 다르면 다른 슬롯
        self.assertIs(
            self._match(SOOP_OWNER, email="user@sooplive.com", account_uuid="uuid-soop", org_uuid="org-other"),
            False,
        )

    def test_fetch_failure_is_indeterminate(self):
        self.assertIsNone(self._match(None, email="user@gmail.com", account_uuid="uuid-gmail"))

    def test_no_expected_identity_is_indeterminate(self):
        self.assertIsNone(self._match(GMAIL_OWNER, email=""))


class TestFetchTokenOwner(unittest.TestCase):
    def test_parses_profile_and_caches_by_token(self):
        profile = {
            "account": {"uuid": "uuid-gmail", "email": "User@Gmail.com"},
            "organization": {"uuid": "org-gmail"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "owner-cache.json"
            with mock.patch.object(owner, "OWNER_CACHE_FILE", cache_file), \
                 mock.patch.object(owner, "log"), \
                 mock.patch.object(owner.urllib.request, "urlopen", return_value=FakeResponse(profile)) as m:
                first = owner.fetch_token_owner(_fake_credential("tok-cache"))
                second = owner.fetch_token_owner(_fake_credential("tok-cache"))
            self.assertEqual(first, {"uuid": "uuid-gmail", "email": "user@gmail.com", "org_uuid": "org-gmail"})
            self.assertEqual(second, first)
            self.assertEqual(m.call_count, 1)  # 두 번째는 캐시

    def test_network_error_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(owner, "OWNER_CACHE_FILE", Path(tmp) / "owner-cache.json"), \
                 mock.patch.object(owner, "log"), \
                 mock.patch.object(owner.urllib.request, "urlopen", side_effect=OSError("offline")):
                self.assertIsNone(owner.fetch_token_owner(_fake_credential("tok-err")))


class TestRefreshAllOwnerGuard(unittest.TestCase):
    """실사고 재현: 현재 계정(soop) 슬롯에 Keychain의 gmail 토큰 저장 차단"""

    def _run_refresh_all(self, accounts_dir, keychain_owner):
        soop_acc = {
            "id": "user_soop",
            "name": "soop",
            "email": "user@sooplive.com",
            "plan": "Team",
            "profileFile": "profile_user_soop.json",
            "credentialFile": "credential_user_soop.json",
            "organizationUuid": "org-soop",
        }
        (accounts_dir / "profile_user_soop.json").write_text(json.dumps({
            "accountUuid": "uuid-soop",
            "emailAddress": "user@sooplive.com",
            "organizationUuid": "org-soop",
        }))
        index = {"version": 1, "accounts": [soop_acc], "activeAccountId": "user_soop"}
        # desync 시나리오: oauthAccount(claude.json)는 soop, Keychain 토큰 소유자는 keychain_owner
        current = {"emailAddress": "user@sooplive.com", "organizationUuid": "org-soop", "accountUuid": "uuid-soop"}
        keychain_cred = _fake_credential("tok-keychain")

        with mock.patch.object(token_cmd, "ACCOUNTS_DIR", accounts_dir), \
             mock.patch.object(owner, "ACCOUNTS_DIR", accounts_dir), \
             mock.patch.object(owner, "log"), \
             mock.patch.object(owner, "fetch_token_owner", return_value=keychain_owner), \
             mock.patch.object(token_cmd, "get_current_account", return_value=current), \
             mock.patch.object(token_cmd, "get_keychain_credential", return_value=keychain_cred), \
             mock.patch.object(token_cmd, "load_index", return_value=index), \
             mock.patch.object(token_cmd, "save_index"), \
             mock.patch.object(token_cmd, "log"), \
             mock.patch.object(token_cmd, "log_token_info"), \
             mock.patch("sys.stdout", new=io.StringIO()):
            token_cmd.cmd_refresh_all()

        return accounts_dir / "credential_user_soop.json"

    def test_contaminated_keychain_token_is_not_saved(self):
        # Keychain 토큰이 gmail 소유 → soop 슬롯에 저장되면 안 됨 (2026-07-08 사고)
        with tempfile.TemporaryDirectory() as tmp:
            cred_path = self._run_refresh_all(Path(tmp), GMAIL_OWNER)
            self.assertFalse(cred_path.exists(), "교차 오염: 다른 계정 토큰이 슬롯에 저장됨")

    def test_matching_keychain_token_is_saved(self):
        # Keychain 토큰이 soop 소유 → 정상 저장
        with tempfile.TemporaryDirectory() as tmp:
            cred_path = self._run_refresh_all(Path(tmp), SOOP_OWNER)
            self.assertTrue(cred_path.exists())
            saved = json.loads(cred_path.read_text())
            self.assertEqual(saved["claudeAiOauth"]["accessToken"], "tok-keychain")

    def test_indeterminate_owner_skips_save(self):
        # 소유자 확인 불가(네트워크) → 저장 미루기 (오염 방지 우선)
        with tempfile.TemporaryDirectory() as tmp:
            cred_path = self._run_refresh_all(Path(tmp), None)
            self.assertFalse(cred_path.exists())


if __name__ == "__main__":
    unittest.main()
