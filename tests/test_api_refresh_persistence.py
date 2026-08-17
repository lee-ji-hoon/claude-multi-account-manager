import unittest
import urllib.error
import json
from pathlib import Path
import stat
import tempfile
from unittest import mock

from claude_account_manager import api, token
from claude_account_manager.commands import token_cmd
from claude_account_manager.token import TokenStatus


class UsageRefreshPersistenceTest(unittest.TestCase):
    class TokenResponse:
        status = 200

        def read(self):
            return json.dumps(
                {
                    "access_token": "rotated-access-token",
                    "refresh_token": "rotated-one-time-token",
                    "expires_in": 28800,
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def test_status_check_preserves_keychain_source_during_refresh(self):
        credential = {
            "claudeAiOauth": {
                "accessToken": "expired-access-token",
                "refreshToken": "one-time-refresh-token",
            }
        }
        refreshed = {"claudeAiOauth": {"accessToken": "new-access-token"}}

        with mock.patch.object(token, "get_keychain_credential", return_value=credential), \
             mock.patch.object(token, "is_token_expired", return_value=True), \
             mock.patch.object(token, "refresh_access_token", return_value=(refreshed, None)) as refresh:
            status, message = token.check_token_status()

        self.assertEqual(TokenStatus.REFRESHED, status)
        self.assertIn("자동으로 갱신", message)
        refresh.assert_called_once_with(None)

    def test_status_check_reports_error_when_rotated_token_cannot_be_saved(self):
        credential = {
            "claudeAiOauth": {
                "accessToken": "expired-access-token",
                "refreshToken": "one-time-refresh-token",
            }
        }
        refreshed = {"claudeAiOauth": {"accessToken": "new-access-token"}}

        with mock.patch.object(token, "get_keychain_credential", return_value=credential), \
             mock.patch.object(token, "is_token_expired", return_value=True), \
             mock.patch.object(
                 token,
                 "refresh_access_token",
                 return_value=(refreshed, "Keychain 저장 실패"),
             ):
            status, message = token.check_token_status()

        self.assertEqual(TokenStatus.ERROR, status)
        self.assertIn("저장 실패", message)

    def test_status_401_reports_error_when_rotated_token_cannot_be_saved(self):
        credential = {
            "claudeAiOauth": {
                "accessToken": "rejected-access-token",
                "refreshToken": "one-time-refresh-token",
            }
        }
        refreshed = {"claudeAiOauth": {"accessToken": "new-access-token"}}
        unauthorized = urllib.error.HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        with mock.patch.object(token, "get_keychain_credential", return_value=credential), \
             mock.patch.object(token, "is_token_expired", return_value=False), \
             mock.patch.object(token.urllib.request, "urlopen", side_effect=unauthorized), \
             mock.patch.object(
                 token,
                 "refresh_access_token",
                 return_value=(refreshed, "Keychain 저장 실패"),
             ):
            status, message = token.check_token_status()

        self.assertEqual(TokenStatus.ERROR, status)
        self.assertIn("저장 실패", message)

    def test_current_account_401_refreshes_from_keychain_source(self):
        credential = {
            "claudeAiOauth": {
                "accessToken": "expired-access-token",
                "refreshToken": "one-time-refresh-token",
                "subscriptionType": "max",
            }
        }
        unauthorized = urllib.error.HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        with mock.patch.object(api, "get_keychain_credential", return_value=credential), \
             mock.patch.object(api.urllib.request, "urlopen", side_effect=unauthorized), \
             mock.patch.object(api, "refresh_access_token", return_value=(None, "stopped")) as refresh:
            usage, status = api._fetch_usage_from_api(include_token_status=True)

        self.assertIsNone(usage)
        self.assertEqual(TokenStatus.EXPIRED, status)
        refresh.assert_called_once_with(None, credential_file=None)

    def test_usage_fetch_attempts_only_one_refresh_after_consecutive_401s(self):
        old_credential = {
            "claudeAiOauth": {
                "accessToken": "expired-access-token",
                "refreshToken": "old-one-time-token",
                "subscriptionType": "max",
            }
        }
        new_credential = {
            "claudeAiOauth": {
                "accessToken": "rejected-new-access-token",
                "refreshToken": "new-one-time-token",
                "subscriptionType": "max",
            }
        }
        unauthorized = urllib.error.HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        with mock.patch.object(api, "get_keychain_credential", return_value=old_credential), \
             mock.patch.object(api.urllib.request, "urlopen", side_effect=unauthorized) as urlopen, \
             mock.patch.object(api, "refresh_access_token", return_value=(new_credential, None)) as refresh:
            usage, status = api._fetch_usage_from_api(include_token_status=True)

        self.assertIsNone(usage)
        self.assertEqual(TokenStatus.EXPIRED, status)
        self.assertEqual(2, urlopen.call_count)
        refresh.assert_called_once_with(None, credential_file=None)

    def test_usage_fetch_does_not_retry_when_rotated_token_cannot_be_saved(self):
        old_credential = {
            "claudeAiOauth": {
                "accessToken": "expired-access-token",
                "refreshToken": "old-one-time-token",
                "subscriptionType": "max",
            }
        }
        new_credential = {
            "claudeAiOauth": {
                "accessToken": "new-access-token",
                "refreshToken": "new-one-time-token",
                "subscriptionType": "max",
            }
        }
        unauthorized = urllib.error.HTTPError(
            url="https://api.anthropic.com/api/oauth/usage",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

        with mock.patch.object(api, "get_keychain_credential", return_value=old_credential), \
             mock.patch.object(api.urllib.request, "urlopen", side_effect=unauthorized) as urlopen, \
             mock.patch.object(
                 api,
                 "refresh_access_token",
                 return_value=(new_credential, "Keychain 저장 실패"),
             ):
            usage, status = api._fetch_usage_from_api(include_token_status=True)

        self.assertIsNone(usage)
        self.assertEqual(TokenStatus.ERROR, status)
        self.assertEqual(1, urlopen.call_count)

    def test_rotated_keychain_token_is_written_to_recovery_when_keychain_save_fails(self):
        old_credential = {
            "claudeAiOauth": {
                "accessToken": "old-access-token",
                "refreshToken": "consumed-one-time-token",
                "expiresAt": 1,
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            recovery_directory = Path(temporary) / "recovery"
            with mock.patch.object(
                token.urllib.request, "urlopen", return_value=self.TokenResponse()
            ), mock.patch.object(
                token, "get_keychain_credential", return_value=old_credential
            ), mock.patch.object(
                token, "set_keychain_credential", return_value=False
            ), mock.patch.object(
                token, "TOKEN_RECOVERY_DIR", recovery_directory, create=True
            ):
                new_credential, error = token.refresh_access_token()

            self.assertIsNotNone(new_credential)
            self.assertIn("복구", error)
            recovery_files = list(recovery_directory.glob("*.json"))
            self.assertEqual(1, len(recovery_files))
            recovered = json.loads(recovery_files[0].read_text())
            self.assertEqual(
                "rotated-one-time-token",
                recovered["claudeAiOauth"]["refreshToken"],
            )
            self.assertEqual(0o600, stat.S_IMODE(recovery_files[0].stat().st_mode))

    def test_rotated_account_file_uses_atomic_recovery_when_replace_fails(self):
        old_credential = {
            "claudeAiOauth": {
                "accessToken": "old-access-token",
                "refreshToken": "consumed-one-time-token",
                "expiresAt": 1,
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            credential_path = Path(temporary) / "credential_account.json"
            credential_path.write_text(json.dumps(old_credential))
            credential_path.chmod(0o600)
            with mock.patch.object(
                token.urllib.request, "urlopen", return_value=self.TokenResponse()
            ), mock.patch.object(token.os, "replace", side_effect=OSError("replace failed")):
                new_credential, error = token.refresh_access_token(
                    old_credential, credential_file=credential_path
                )

            self.assertIsNotNone(new_credential)
            self.assertIn("복구", error)
            self.assertEqual(old_credential, json.loads(credential_path.read_text()))
            recovery_files = list(
                credential_path.parent.glob(".credential_account.json.refresh-recovery-*")
            )
            self.assertEqual(1, len(recovery_files))
            recovered = json.loads(recovery_files[0].read_text())
            self.assertEqual(
                "rotated-one-time-token",
                recovered["claudeAiOauth"]["refreshToken"],
            )

    def test_locked_account_refresh_does_not_truncate_file_after_rotation(self):
        old_credential = {
            "claudeAiOauth": {
                "accessToken": "old-access-token",
                "refreshToken": "consumed-one-time-token",
                "expiresAt": 1,
            }
        }
        new_credential = {
            "claudeAiOauth": {
                "accessToken": "rotated-access-token",
                "refreshToken": "rotated-one-time-token",
                "expiresAt": 4102444800000,
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            credential_path = Path(temporary) / "credential_account.json"
            recovery_path = Path(temporary) / ".credential_account.json.refresh-recovery-test"
            credential_path.write_text(json.dumps(old_credential))
            credential_path.chmod(0o600)
            with mock.patch.object(token_cmd, "_cc_fleet_accounts", return_value=set()), \
                 mock.patch.object(
                     token_cmd,
                     "refresh_access_token",
                     return_value=(new_credential, None),
                 ), mock.patch.object(
                     token_cmd,
                     "persist_credential_file",
                     return_value=(False, recovery_path),
                     create=True,
                 ) as persist, mock.patch.object(token_cmd, "log"), \
                 mock.patch.object(token_cmd, "log_token_info"):
                refreshed, error = token_cmd._safe_refresh_credential(
                    credential_path, "account", skip_fresh_check=True
                )

            self.assertEqual(new_credential, refreshed)
            self.assertIn("복구", error)
            self.assertEqual(old_credential, json.loads(credential_path.read_text()))
            persist.assert_called_once_with(new_credential, credential_path)


if __name__ == "__main__":
    unittest.main()
