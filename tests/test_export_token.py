import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestCmdExportToken(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.accounts_dir = Path(self.tmpdir)

    def _write_credential(self, account_id, token):
        path = self.accounts_dir / f"credential_{account_id}.json"
        path.write_text(json.dumps({
            "claudeAiOauth": {"accessToken": token, "refreshToken": "",
                              "expiresAt": 9999999999999}
        }))
        return path

    def _index(self, accounts):
        return {"accounts": accounts, "activeAccountId": None}

    def test_outputs_export_line_for_long_lived(self):
        from claude_account_manager.commands import export_token_cmd
        self._write_credential("joel_token", "sk-ant-oat01-XYZ")
        with patch.object(export_token_cmd, "ACCOUNTS_DIR", self.accounts_dir), \
             patch.object(export_token_cmd, "load_index", return_value=self._index([
                 {"id": "joel_token", "name": "joel", "tokenType": "long-lived",
                  "credentialFile": "credential_joel_token.json"}
             ])):
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                rc = export_token_cmd.cmd_export_token("joel_token")
            self.assertTrue(rc)
            self.assertIn("export CLAUDE_CODE_OAUTH_TOKEN=", captured.getvalue())
            self.assertIn("sk-ant-oat01-XYZ", captured.getvalue())

    def test_returns_false_on_missing_account(self):
        from claude_account_manager.commands import export_token_cmd
        with patch.object(export_token_cmd, "load_index",
                          return_value=self._index([])):
            self.assertFalse(export_token_cmd.cmd_export_token("nope"))

    def test_export_line_uses_single_quotes_for_safety(self):
        from claude_account_manager.commands import export_token_cmd
        self._write_credential("joel_token", "sk-ant-oat01-Has$pecial")
        with patch.object(export_token_cmd, "ACCOUNTS_DIR", self.accounts_dir), \
             patch.object(export_token_cmd, "load_index", return_value=self._index([
                 {"id": "joel_token", "name": "joel", "tokenType": "long-lived",
                  "credentialFile": "credential_joel_token.json"}
             ])):
            captured = io.StringIO()
            with patch.object(sys, "stdout", captured):
                export_token_cmd.cmd_export_token("joel_token")
            self.assertIn("export CLAUDE_CODE_OAUTH_TOKEN='sk-ant-oat01-Has$pecial'",
                          captured.getvalue())


if __name__ == "__main__":
    unittest.main()
