import json
import subprocess
import unittest
from unittest import mock

from claude_account_manager import keychain


class KeychainPersistenceTest(unittest.TestCase):
    def test_update_never_deletes_existing_credential_before_replacement(self):
        credential = {
            "claudeAiOauth": {
                "accessToken": "new-access",
                "refreshToken": "new-refresh",
            }
        }
        completed = subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(
            keychain.subprocess, "run", return_value=completed
        ) as run, mock.patch.object(
            keychain, "_read_keychain_entry", return_value=credential
        ):
            saved = keychain.set_keychain_credential(credential)

        self.assertTrue(saved)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(1, len(commands))
        self.assertEqual("add-generic-password", commands[0][1])
        self.assertIn("-U", commands[0])
        self.assertNotIn("delete-generic-password", commands[0])


if __name__ == "__main__":
    unittest.main()
