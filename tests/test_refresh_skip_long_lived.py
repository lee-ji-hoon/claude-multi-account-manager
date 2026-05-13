import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestRefreshAllSkipsLongLived(unittest.TestCase):
    def test_refresh_all_skips_long_lived_accounts(self):
        from claude_account_manager.commands import token_cmd

        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "credential_joel.json").write_text(json.dumps({
            "claudeAiOauth": {"accessToken": "old", "refreshToken": "r",
                              "expiresAt": 1}
        }))
        (tmpdir / "credential_joel_token.json").write_text(json.dumps({
            "claudeAiOauth": {"accessToken": "sk-ant-oat01-X", "refreshToken": "",
                              "expiresAt": 9999999999999,
                              "subscriptionType": "max",
                              "rateLimitTier": "default_claude_max_20x"}
        }))

        accounts = [
            {"id": "joel", "name": "joel", "email": "joel@x.com",
             "credentialFile": "credential_joel.json"},
            {"id": "joel_token", "name": "joel-ci", "email": "joel@x.com",
             "tokenType": "long-lived",
             "credentialFile": "credential_joel_token.json"},
        ]
        index = {"accounts": accounts, "activeAccountId": "joel"}

        refresh_calls = []

        def fake_refresh(credential_path, account_id, **kw):
            refresh_calls.append(account_id)
            return ({"claudeAiOauth": {"accessToken": "new", "refreshToken": "r2",
                                       "expiresAt": 2,
                                       "subscriptionType": "pro",
                                       "rateLimitTier": ""}}, None)

        with patch.object(token_cmd, "load_index", return_value=index), \
             patch.object(token_cmd, "save_index"), \
             patch.object(token_cmd, "get_current_account", return_value=None), \
             patch.object(token_cmd, "_auto_migrate"), \
             patch.object(token_cmd, "ACCOUNTS_DIR", tmpdir), \
             patch.object(token_cmd, "_safe_refresh_credential", side_effect=fake_refresh):
            token_cmd.cmd_refresh_all()

        self.assertEqual(refresh_calls, ["joel"])  # long-lived는 호출되지 않아야 함

    def test_refresh_expiring_skips_long_lived(self):
        from claude_account_manager.commands import token_cmd
        from datetime import datetime, timedelta

        # long-lived 토큰이지만 expiresAt이 1시간 이내(만료 임박)이어도 skip되어야 함
        soon_ms = int((datetime.now() + timedelta(minutes=30)).timestamp() * 1000)

        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "credential_joel_token.json").write_text(json.dumps({
            "claudeAiOauth": {"accessToken": "sk-ant-X", "refreshToken": "",
                              "expiresAt": soon_ms}
        }))

        accounts = [
            {"id": "joel_token", "name": "joel-ci", "email": "joel@x.com",
             "tokenType": "long-lived",
             "credentialFile": "credential_joel_token.json"},
        ]
        index = {"accounts": accounts, "activeAccountId": None}

        refresh_calls = []
        def fake_refresh(credential_path, account_id, **kw):
            refresh_calls.append(account_id)
            return (None, "should not be called")

        with patch.object(token_cmd, "load_index", return_value=index), \
             patch.object(token_cmd, "save_index"), \
             patch.object(token_cmd, "get_current_account", return_value=None), \
             patch.object(token_cmd, "ACCOUNTS_DIR", tmpdir), \
             patch.object(token_cmd, "_safe_refresh_credential", side_effect=fake_refresh):
            token_cmd.cmd_refresh_expiring(1)

        self.assertEqual(refresh_calls, [])


if __name__ == "__main__":
    unittest.main()
