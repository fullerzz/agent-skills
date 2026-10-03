"""Exercise explicit Codex mode controls without personal configuration."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "hooks/session-start.py"


class CodexHooksTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="zstack hook ")
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name)
        self.env = dict(os.environ, PLUGIN_ROOT=str(ROOT), PLUGIN_DATA=str(self.data))

    def hook(self, session="session-a", source="startup"):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(HELPER)],
            input=json.dumps({
                "hook_event_name": "SessionStart", "source": source,
                "session_id": session,
            }),
            text=True, capture_output=True, check=True, env=self.env,
        )
        self.assertEqual(result.stderr, "")
        return result.stdout

    def control(self, action, session="session-a", check=True):
        return subprocess.run(
            [sys.executable, "-I", "-S", str(HELPER), action, "--session-id", session,
             "--data-dir", str(self.data)],
            text=True, capture_output=True, check=check,
        )

    def test_configured_command_and_emitted_controls(self):
        (self.data / "uv.toml").write_text("invalid TOML [")
        marker = self.data / "site-loaded"
        (self.data / "sitecustomize.py").write_text(
            f"open({str(marker)!r}, 'w').close()\n"
        )
        self.env["PYTHONPATH"] = str(self.data)
        group = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"][0]
        for source in ("startup", "resume", "compact", "clear"):
            self.assertIsNotNone(re.fullmatch(group["matcher"], source))
        result = subprocess.run(
            group["hooks"][0]["command"], shell=True,
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "session_id": "session-a"}),
            text=True, capture_output=True, check=True, cwd=self.data, env=self.env,
        )
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        commands = dict(line.split(": ", 1) for line in context.splitlines()
                        if line.startswith(("Enable: ", "Disable: ")))
        for action in ("Enable", "Disable"):
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)
            active = "was explicitly enabled" in self.hook()
            self.assertEqual(active, action == "Enable")
            self.assertFalse(marker.exists())

    def test_disabled_default_session_isolation_and_clear(self):
        self.assertIn("No stored", self.hook())
        self.assertEqual(list(self.data.iterdir()), [])
        self.control("enable")
        for source in ("startup", "resume", "compact"):
            self.assertIn("was explicitly enabled", self.hook(source=source))
            self.assertIn("No stored", self.hook(session="session-b", source=source))
        self.assertIn("No stored", self.hook(source="clear"))
        self.assertIn("No stored", self.hook(source="resume"))
        self.control("disable")

    def test_invalid_identity_and_corrupt_state_fail_inactive(self):
        for session in ("../outside", "x/y", "x; touch outside", "", "x" * 129):
            self.assertEqual(self.hook(session=session), "")
            self.assertNotEqual(self.control("enable", session=session, check=False).returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])
        state = self.data / "z-mode/session-a.json"
        state.parent.mkdir()
        for value in ("invalid", "[]", '{"active":"true"}', "null"):
            state.write_text(value)
            self.assertIn("No stored", self.hook(source="compact"))

    def test_clear_reports_state_removal_failure(self):
        state = self.data / "z-mode/session-a.json"
        state.mkdir(parents=True)
        output = json.loads(self.hook(source="clear"))
        self.assertIn("could not be removed", output["systemMessage"])
        self.assertIn("inactive for this cleared context", output["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("No stored", output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("stale stored activation", output["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
