import time
import unittest
from datetime import datetime, timedelta
from claude_account_manager.long_lived import (
    EXPIRY_DANGER_DAYS,
    EXPIRY_WARN_DAYS,
    format_expiry_dday,
    is_long_lived_account,
    plan_to_subscription_type,
    validate_token_format,
    wrap_long_lived_token,
)


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


class TestPlanToSubscriptionType(unittest.TestCase):
    def test_max20(self):
        self.assertEqual(plan_to_subscription_type("Max20"),
                         ("max", "default_claude_max_20x"))

    def test_max5(self):
        self.assertEqual(plan_to_subscription_type("Max5"),
                         ("max", "default_claude_max_5x"))

    def test_pro(self):
        self.assertEqual(plan_to_subscription_type("Pro"),
                         ("pro", ""))

    def test_team(self):
        self.assertEqual(plan_to_subscription_type("Team"),
                         ("team", ""))

    def test_free(self):
        self.assertEqual(plan_to_subscription_type("Free"),
                         ("free", ""))

    def test_unknown_defaults_to_free(self):
        self.assertEqual(plan_to_subscription_type("Foo"),
                         ("free", ""))


class TestWrapLongLivedToken(unittest.TestCase):
    def test_schema_shape(self):
        wrapped = wrap_long_lived_token("sk-ant-oat01-abc", "Max20")
        self.assertIn("claudeAiOauth", wrapped)
        oauth = wrapped["claudeAiOauth"]
        self.assertEqual(oauth["accessToken"], "sk-ant-oat01-abc")
        self.assertEqual(oauth["refreshToken"], "")
        self.assertEqual(oauth["subscriptionType"], "max")
        self.assertEqual(oauth["rateLimitTier"], "default_claude_max_20x")
        self.assertIsInstance(oauth["expiresAt"], int)

    def test_expires_at_is_about_one_year_future(self):
        before_ms = int(time.time() * 1000)
        wrapped = wrap_long_lived_token("sk-ant-oat01-abc", "Pro")
        after_ms = int(time.time() * 1000)
        expires = wrapped["claudeAiOauth"]["expiresAt"]
        one_year_ms = 365 * 24 * 60 * 60 * 1000
        self.assertGreaterEqual(expires, before_ms + one_year_ms - 5000)
        self.assertLessEqual(expires, after_ms + one_year_ms + 5000)

    def test_pro_plan_subscription_type(self):
        wrapped = wrap_long_lived_token("sk-ant-oat01-x", "Pro")
        self.assertEqual(wrapped["claudeAiOauth"]["subscriptionType"], "pro")


class TestIsLongLivedAccount(unittest.TestCase):
    def test_oauth_default_when_missing(self):
        self.assertFalse(is_long_lived_account({"id": "x"}))

    def test_explicit_oauth(self):
        self.assertFalse(is_long_lived_account({"tokenType": "oauth"}))

    def test_long_lived(self):
        self.assertTrue(is_long_lived_account({"tokenType": "long-lived"}))

    def test_none_returns_false(self):
        self.assertFalse(is_long_lived_account(None))


class TestFormatExpiryDday(unittest.TestCase):
    def _expires_in(self, days):
        return int((datetime.now() + timedelta(days=days)).timestamp() * 1000)

    def test_normal(self):
        label, severity = format_expiry_dday(self._expires_in(200))
        self.assertTrue(label.startswith("D-"))
        self.assertEqual(severity, "normal")

    def test_warn_at_30(self):
        label, severity = format_expiry_dday(self._expires_in(25))
        self.assertEqual(severity, "warn")

    def test_danger_at_7(self):
        label, severity = format_expiry_dday(self._expires_in(3))
        self.assertEqual(severity, "danger")

    def test_expired(self):
        label, severity = format_expiry_dday(self._expires_in(-1))
        self.assertEqual(label, "만료됨")
        self.assertEqual(severity, "expired")

    def test_today_is_danger(self):
        # 12시간 후 만료 = D-0 (timedelta.days floors to 0)
        expires_ms = int((datetime.now() + timedelta(hours=12)).timestamp() * 1000)
        label, severity = format_expiry_dday(expires_ms)
        self.assertEqual(severity, "danger")

    def test_severity_thresholds_constants(self):
        self.assertEqual(EXPIRY_WARN_DAYS, 30)
        self.assertEqual(EXPIRY_DANGER_DAYS, 7)

    def test_none_returns_question(self):
        label, severity = format_expiry_dday(None)
        self.assertEqual(label, "?")


if __name__ == "__main__":
    unittest.main()
