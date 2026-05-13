import unittest
from claude_account_manager.long_lived import validate_token_format


class TestValidateTokenFormat(unittest.TestCase):
    def test_accepts_sk_ant_oat_prefix(self):
        self.assertTrue(validate_token_format("sk-ant-oat01-abc123"))

    def test_accepts_sk_ant_prefix_general(self):
        self.assertTrue(validate_token_format("sk-ant-anything-xyz"))

    def test_rejects_empty(self):
        self.assertFalse(validate_token_format(""))

    def test_rejects_whitespace_only(self):
        self.assertFalse(validate_token_format("   "))

    def test_rejects_wrong_prefix(self):
        self.assertFalse(validate_token_format("bearer-token-foo"))

    def test_rejects_none(self):
        self.assertFalse(validate_token_format(None))

    def test_strips_whitespace(self):
        self.assertTrue(validate_token_format("  sk-ant-oat01-x  "))


if __name__ == "__main__":
    unittest.main()
