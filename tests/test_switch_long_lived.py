import unittest


class TestBuildShellExportLines(unittest.TestCase):
    def test_long_lived_emits_export_line(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type="long-lived",
                                        access_token="sk-ant-oat01-XYZ")
        self.assertEqual(line, "export CLAUDE_CODE_OAUTH_TOKEN='sk-ant-oat01-XYZ'")

    def test_oauth_emits_unset_line(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type="oauth", access_token="ignored")
        self.assertEqual(line, "unset CLAUDE_CODE_OAUTH_TOKEN")

    def test_oauth_default_when_missing(self):
        from claude_account_manager.commands.switch_cmd import build_shell_export_lines
        line = build_shell_export_lines(token_type=None, access_token=None)
        self.assertEqual(line, "unset CLAUDE_CODE_OAUTH_TOKEN")


if __name__ == "__main__":
    unittest.main()
