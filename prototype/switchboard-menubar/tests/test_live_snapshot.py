import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "switchboard_live_snapshot",
    ROOT / "Resources/live_snapshot.py",
)
live_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live_snapshot)


class GrokProfileTest(unittest.TestCase):
    def test_grok_usage_retries_once_after_transient_empty_parse(self):
        expected = {"label": "주간", "usedPercent": 37, "resetsIn": "1일"}
        with mock.patch.object(
            live_snapshot,
            "_run_grok_usage",
            side_effect=[None, expected],
        ) as run:
            actual = live_snapshot._safe_grok_usage("/tmp/default")

        self.assertEqual(expected, actual)
        self.assertEqual(
            [mock.call("/tmp/default", timeout=12), mock.call("/tmp/default", timeout=6)],
            run.call_args_list,
        )

    def test_grok_profiles_are_metadata_only_and_each_is_launchable(self):
        profiles = [
            {"accountID": "default", "grokHome": "/tmp/default", "authenticated": True},
            {"accountID": "work", "grokHome": "/tmp/work", "authenticated": True},
        ]
        with mock.patch("claude_account_manager.grok_profiles.list_grok_profiles", return_value=profiles), \
             mock.patch("claude_account_manager.grok_profiles.get_grok_launch_contract", side_effect=lambda profile_id: {"environment": {"GROK_HOME": "/tmp/" + profile_id}}), \
             mock.patch.object(live_snapshot, "_safe_grok_usage", return_value=None) as usage, \
             mock.patch.dict(os.environ, {"GROK_HOME": "/tmp/work"}, clear=False):
            provider = live_snapshot.grok_provider()

        self.assertEqual("grok-work", provider["activeAccountID"])
        self.assertEqual(["grok-default", "grok-work"], [account["id"] for account in provider["accounts"]])
        self.assertTrue(all(account["grokHome"].startswith("/tmp/") for account in provider["accounts"]))
        usage.assert_has_calls([mock.call("/tmp/default"), mock.call("/tmp/work")], any_order=True)

    def test_grok_shows_usage_for_inactive_profiles_too(self):
        profiles = [
            {"accountID": "default"},
            {"accountID": "work"},
        ]
        usage = {"label": "주간", "usedPercent": 34, "resetsIn": "2일", "plan": "SuperGrok"}
        with mock.patch("claude_account_manager.grok_profiles.list_grok_profiles", return_value=profiles), \
             mock.patch("claude_account_manager.grok_profiles.get_grok_launch_contract", side_effect=lambda profile_id: {"environment": {"GROK_HOME": "/tmp/" + profile_id}}), \
             mock.patch.object(live_snapshot, "_safe_grok_usage", return_value=usage), \
             mock.patch.dict(os.environ, {"GROK_HOME": "/tmp/work"}, clear=False):
            provider = live_snapshot.grok_provider()

        self.assertEqual([[usage[k] for k in ("label", "usedPercent", "resetsIn")]] * 2,
                         [[window[k] for k in ("label", "usedPercent", "resetsIn")] for account in provider["accounts"] for window in account["usage"]])
        self.assertEqual(["SuperGrok", "SuperGrok"], [account["plan"] for account in provider["accounts"]])


if __name__ == "__main__":
    unittest.main()
