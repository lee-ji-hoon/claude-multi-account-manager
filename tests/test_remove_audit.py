"""
cmd_remove 감사 로깅 회귀 테스트

2026-07-08 실사고: dlwlgns1240_soop 계정 항목이 원인 불명으로 두 차례 삭제됨.
remove_cmd는 삭제 전 y/n 확인을 거치지만 누가/언제/어떤 경로로 지웠는지 로그가 없어
사후 추적이 불가능했다. 삭제 직전 log("WARN", ...)로 계정 식별자·actor 컨텍스트를
남기는지 검증한다.

실행: python3 -m unittest discover -s tests
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_account_manager.commands import remove_cmd


class TestRemoveAudit(unittest.TestCase):
    def _account(self):
        return {
            "id": "user_soop",
            "name": "soop",
            "email": "user@sooplive.com",
            "plan": "Team",
            "profileFile": "profile_user_soop.json",
            "credentialFile": "credential_user_soop.json",
            "organizationName": "soop",
        }

    def _run_remove(self, accounts_dir, credential_exists=True):
        acc = self._account()
        (accounts_dir / acc["profileFile"]).write_text("{}")
        if credential_exists:
            (accounts_dir / acc["credentialFile"]).write_text("{}")
        index = {"version": 1, "accounts": [acc], "activeAccountId": acc["id"]}

        logged = []
        with mock.patch.object(remove_cmd, "ACCOUNTS_DIR", accounts_dir), \
             mock.patch.object(remove_cmd, "load_index", return_value=index), \
             mock.patch.object(remove_cmd, "save_index"), \
             mock.patch.object(remove_cmd, "log", side_effect=lambda lvl, msg: logged.append((lvl, msg))), \
             mock.patch("builtins.input", return_value="y"), \
             mock.patch("sys.stdout", new=io.StringIO()):
            result = remove_cmd.cmd_remove("user_soop")

        return result, logged

    def test_removal_is_audit_logged_with_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, logged = self._run_remove(Path(tmp))

        self.assertTrue(result)
        warn_logs = [msg for lvl, msg in logged if lvl == "WARN"]
        self.assertTrue(any("user_soop" in m and "user@sooplive.com" in m for m in warn_logs),
                         f"삭제 감사 로그 없음: {logged}")

    def test_audit_log_records_missing_credential(self):
        # 2026-07-08 사고 재현 조건: credentialFile 없는 반쪽 상태에서 삭제
        with tempfile.TemporaryDirectory() as tmp:
            result, logged = self._run_remove(Path(tmp), credential_exists=False)

        self.assertTrue(result)
        warn_logs = [msg for lvl, msg in logged if lvl == "WARN"]
        self.assertTrue(any("credential=없음" in m for m in warn_logs),
                         f"credential 없음 상태가 로그에 안 남음: {logged}")

    def test_cancelled_removal_is_not_logged_as_deletion(self):
        acc = self._account()
        index = {"version": 1, "accounts": [acc], "activeAccountId": acc["id"]}
        logged = []
        with tempfile.TemporaryDirectory() as tmp:
            accounts_dir = Path(tmp)
            (accounts_dir / acc["profileFile"]).write_text("{}")
            (accounts_dir / acc["credentialFile"]).write_text("{}")
            with mock.patch.object(remove_cmd, "ACCOUNTS_DIR", accounts_dir), \
                 mock.patch.object(remove_cmd, "load_index", return_value=index), \
                 mock.patch.object(remove_cmd, "save_index"), \
                 mock.patch.object(remove_cmd, "log", side_effect=lambda lvl, msg: logged.append((lvl, msg))), \
                 mock.patch("builtins.input", return_value="n"), \
                 mock.patch("sys.stdout", new=io.StringIO()):
                result = remove_cmd.cmd_remove("user_soop")

            self.assertFalse(result)
            self.assertEqual(logged, [])
            self.assertTrue((accounts_dir / acc["profileFile"]).exists())


if __name__ == "__main__":
    unittest.main()
