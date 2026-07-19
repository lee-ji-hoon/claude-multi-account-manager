import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from claude_account_manager.commands import list_cmd
from claude_account_manager.ui import Colors


class CodexUsageDisplayTest(unittest.TestCase):
    def _render_current_usage(self, usage):
        stored_auth = {
            "tokens": {"access_token": "stored-stale-token", "account_id": "account-1"},
            "last_refresh": "2020-01-01T00:00:00Z",
        }
        live_auth = {
            "tokens": {"access_token": "live-refreshed-token", "account_id": "account-1"},
            "last_refresh": "2099-01-01T00:00:00Z",
        }
        codex_index = {
            "accounts": [
                {
                    "id": "saved-1",
                    "account_id": "account-1",
                    "name": "work",
                    "email": "work@example.com",
                    "plan": "Plus",
                }
            ]
        }

        def read_auth(auth_file=None):
            return live_auth if auth_file is None else stored_auth

        fetched_auth = []

        def fetch_usage(auth):
            fetched_auth.append(auth)
            return usage if auth is live_auth else None

        stdout = io.StringIO()
        with (
            patch.object(list_cmd, "load_index", return_value={"accounts": []}),
            patch.object(list_cmd, "get_current_account", return_value={}),
            patch.object(list_cmd, "c", side_effect=lambda _color, text: text),
            patch("claude_account_manager.ui.USE_COLOR", True),
            patch("claude_account_manager.codex_provider.is_codex_available", return_value=True),
            patch("claude_account_manager.codex_provider.load_codex_index", return_value=codex_index),
            patch("claude_account_manager.codex_provider.get_current_codex_account_id", return_value="account-1"),
            patch("claude_account_manager.codex_provider.read_codex_auth", side_effect=read_auth),
            patch(
                "claude_account_manager.codex_provider.get_codex_auth_info",
                return_value={"name": "work", "email": "work@example.com", "plan": "Plus"},
            ),
            patch("claude_account_manager.codex_provider.fetch_codex_usage", side_effect=fetch_usage),
            patch("claude_account_manager.codex_provider.get_codex_token_status", return_value="ok"),
            redirect_stdout(stdout),
        ):
            list_cmd.cmd_list()

        return stdout.getvalue(), fetched_auth, live_auth

    def test_current_account_uses_live_auth_for_status_usage(self):
        usage = {
            "rate_limit": {
                "primary_window": {
                    "limit_window_seconds": 18000,
                    "used_percent": 17,
                    "reset_after_seconds": 3600,
                },
                "secondary_window": {
                    "limit_window_seconds": 604800,
                    "used_percent": 42,
                    "reset_after_seconds": 172800,
                },
            }
        }

        output, fetched_auth, live_auth = self._render_current_usage(usage)

        self.assertIn("5h", output)
        self.assertIn("83% 남음", output)
        self.assertIn("1h 0m", output)
        self.assertIn("주간", output)
        self.assertIn("58% 남음", output)
        self.assertIn("2d 0h", output)
        self.assertRegex(output, r"토큰 🔑 \d+d \d+h 후 만료")
        self.assertNotIn("🔑 -", output)
        self.assertIs(fetched_auth[0], live_auth)

    def test_weekly_primary_window_is_not_mislabeled_as_five_hours(self):
        usage = {
            "rate_limit": {
                "primary_window": {
                    "limit_window_seconds": 604800,
                    "used_percent": 49,
                    "reset_after_seconds": 591000,
                }
            },
            "additional_rate_limits": [
                {
                    "limit_name": "GPT-5.3-Codex-Mini",
                    "rate_limit": {
                        "primary_window": {
                            "limit_window_seconds": 604800,
                            "used_percent": 20,
                            "reset_after_seconds": 86400,
                        }
                    },
                }
            ],
        }

        output, _, _ = self._render_current_usage(usage)

        self.assertIn("주간", output)
        self.assertIn("51% 남음", output)
        self.assertIn("Mini 주간", output)
        self.assertIn("80% 남음", output)
        self.assertNotIn("\n      5h", output)
        self.assertNotIn("Mini 5h", output)

    def test_remaining_bar_color_matches_remaining_text_semantics(self):
        usage = {
            "rate_limit": {
                "primary_window": {
                    "limit_window_seconds": 18000,
                    "used_percent": 0,
                    "reset_after_seconds": 3600,
                },
                "secondary_window": {
                    "limit_window_seconds": 604800,
                    "used_percent": 95,
                    "reset_after_seconds": 3600,
                },
            }
        }

        output, _, _ = self._render_current_usage(usage)

        self.assertIn(Colors.GREEN + "█" * 20 + Colors.RESET, output)
        self.assertIn(Colors.RED + "█" + "░" * 19 + Colors.RESET, output)

    def test_daily_window_uses_daily_label(self):
        usage = {
            "rate_limit": {
                "primary_window": {
                    "limit_window_seconds": 86400,
                    "used_percent": 25,
                    "reset_after_seconds": 7200,
                }
            }
        }

        output, _, _ = self._render_current_usage(usage)

        self.assertIn("일간", output)
        self.assertIn("75% 남음", output)
        self.assertNotIn("\n      5h", output)
        self.assertNotIn("주간", output)

    def test_window_labels_accept_five_percent_boundaries(self):
        durations = {
            "5h": 18000,
            "일간": 86400,
            "주간": 604800,
            "월간": 2592000,
            "연간": 31536000,
        }

        for label, expected_seconds in durations.items():
            for seconds in (int(expected_seconds * 0.95), int(expected_seconds * 1.05)):
                with self.subTest(label=label, seconds=seconds):
                    usage = {
                        "rate_limit": {
                            "primary_window": {
                                "limit_window_seconds": seconds,
                                "used_percent": 25,
                                "reset_after_seconds": 7200,
                            }
                        }
                    }

                    output, _, _ = self._render_current_usage(usage)

                    self.assertIn(label, output)

    def test_unknown_window_uses_generic_limit_label(self):
        usage = {
            "rate_limit": {
                "primary_window": {
                    "limit_window_seconds": 18901,
                    "used_percent": 25,
                    "reset_after_seconds": 7200,
                }
            }
        }

        output, _, _ = self._render_current_usage(usage)

        self.assertIn("제한", output)


if __name__ == "__main__":
    unittest.main()
