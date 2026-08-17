import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "switchboard_live_snapshot",
    ROOT / "prototype/switchboard-menubar/Resources/live_snapshot.py",
)
live_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live_snapshot)


class ClaudeSnapshotSafetyTest(unittest.TestCase):
    def test_inactive_account_with_missing_credential_fails_closed(self):
        fetch = mock.Mock()

        result = live_snapshot._safe_claude_usage(
            fetch,
            is_current=False,
            credential=None,
            credential_path=Path("credential_missing.json"),
        )

        self.assertEqual((None, None), result)
        fetch.assert_not_called()

    def test_current_account_preserves_keychain_source(self):
        fetch = mock.Mock(return_value=({"fiveHour": 25}, "valid"))

        result = live_snapshot._safe_claude_usage(
            fetch,
            is_current=True,
            credential=None,
            credential_path=None,
        )

        self.assertEqual(({"fiveHour": 25}, "valid"), result)
        fetch.assert_called_once_with(
            None,
            include_token_status=True,
            credential_file=None,
            _allow_cache=False,
        )


class ExternalProviderParsingTest(unittest.TestCase):
    def test_gemini_provider_does_not_read_legacy_gemini_cli_metadata(self):
        source = (ROOT / "prototype/switchboard-menubar/Resources/live_snapshot.py").read_text()
        self.assertNotIn("google_accounts.json", source)
        self.assertNotIn("Gemini CLI 과거", source)

    def test_agy_snapshot_reads_only_gemini_quota_and_credits(self):
        usage_payload = {
            "status": "SUCCESS",
            "command": {
                "name": "usage",
                "data": {
                    "groups": [
                        {
                            "name": "Gemini Models",
                            "buckets": [
                                {"id": "gemini-weekly", "remaining_fraction": 0.75},
                                {"id": "gemini-5h", "remaining_fraction": 0.9},
                            ],
                        },
                        {
                            "name": "Claude and GPT models",
                            "buckets": [
                                {"id": "other-weekly", "remaining_fraction": 0.1},
                            ],
                        },
                    ]
                },
            },
        }
        credits_payload = {
            "status": "SUCCESS",
            "command": {"name": "credits", "data": {"remaining_credits": 3}},
        }

        windows, benefits = live_snapshot._parse_agy_snapshot(usage_payload, credits_payload)

        self.assertEqual(["5시간", "주간"], [window["label"] for window in windows])
        self.assertEqual([10, 25], [window["usedPercent"] for window in windows])
        self.assertEqual("3", benefits[0]["amount"])

    def test_grok_usage_text_parses_weekly_percent_and_plan(self):
        raw = "\x1b[32mWeekly limit (SuperGrok)\x1b[0m\n████ 28%\nResets: August 19, 00:10"

        parsed = live_snapshot._parse_grok_usage_text(raw)

        self.assertEqual("SuperGrok", parsed["plan"])
        self.assertEqual(28, parsed["usedPercent"])
        self.assertNotEqual("시각 미제공", parsed["resetsIn"])

    def test_live_snapshot_never_claims_desktop_switching_is_connected(self):
        source = (ROOT / "prototype/switchboard-menubar/Resources/live_snapshot.py").read_text()

        self.assertNotIn('"switchable": health in ("ready", "expiring")', source)
