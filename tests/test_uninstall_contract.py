import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UninstallContractTest(unittest.TestCase):
    def test_uninstall_removes_the_installed_account_plugin(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            plugin_directory = home / ".claude/plugins/cache/local/account/2.5.10"
            plugin_directory.mkdir(parents=True)
            registry = home / ".claude/plugins/installed_plugins.json"
            registry.parent.mkdir(parents=True, exist_ok=True)
            registry.write_text(json.dumps({
                "plugins": {
                    "account@local": [{"installPath": str(plugin_directory)}],
                    "other@local": [],
                }
            }))
            environment = os.environ.copy()
            environment["HOME"] = str(home)

            result = subprocess.run(
                ["bash", str(ROOT / "uninstall.sh")],
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode)
            self.assertFalse((home / ".claude/plugins/cache/local/account").exists())
            data = json.loads(registry.read_text())
            self.assertNotIn("account@local", data["plugins"])
            self.assertIn("other@local", data["plugins"])


if __name__ == "__main__":
    unittest.main()
