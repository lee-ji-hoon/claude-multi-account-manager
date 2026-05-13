import unittest
from unittest.mock import patch


class TestGenerateLongLivedAccountId(unittest.TestCase):
    def _mock_index(self, accounts):
        return {"accounts": accounts, "activeAccountId": None}

    def test_no_conflict_appends_token_suffix(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token")

    def test_conflict_with_existing_oauth_account(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel", "tokenType": "oauth"}
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token")

    def test_conflict_with_existing_long_lived(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel_token", "tokenType": "long-lived"}
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token_2")

    def test_multiple_collisions(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([
                              {"id": "joel_token"},
                              {"id": "joel_token_2"},
                              {"id": "joel_token_3"},
                          ])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("joel@x.com"),
                "joel_token_4")

    def test_normalizes_email_special_chars(self):
        from claude_account_manager import account as account_mod
        with patch.object(account_mod, "load_index",
                          return_value=self._mock_index([])):
            self.assertEqual(
                account_mod.generate_long_lived_account_id("Joel.Lee+ci@x.com"),
                "joel_lee_ci_token")


if __name__ == "__main__":
    unittest.main()
