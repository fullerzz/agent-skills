# Retain the stdlib unittest runner used by the repository.
# ruff: noqa: PT009

"""Exercise explicit Codex mode controls without personal configuration."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "hooks/session_start.py"


class CodexHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="zstack hook ")
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name)
        self.env = dict(os.environ, PLUGIN_ROOT=str(ROOT), PLUGIN_DATA=str(self.data))

    def hook(self, session: str = "session-a", source: str = "startup") -> str:
        result = subprocess.run(  # noqa: S603 - Trusted fixture/manifest commands.
            [sys.executable, "-I", "-S", str(HELPER)],
            input=json.dumps(
                {
                    "hook_event_name": "SessionStart",
                    "source": source,
                    "session_id": session,
                }
            ),
            text=True,
            capture_output=True,
            check=True,
            env=self.env,
        )
        self.assertEqual(result.stderr, "")
        return result.stdout

    def control(self, action: str, session: str = "session-a", check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - Fixed interpreter and local helper.
            [sys.executable, "-I", "-S", str(HELPER), action, f"--session-id={session}", "--data-dir", str(self.data)],
            text=True,
            capture_output=True,
            check=check,
        )

    def test_configured_command_and_emitted_controls(self) -> None:
        (self.data / "uv.toml").write_text("invalid TOML [")
        marker = self.data / "site-loaded"
        (self.data / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').close()\n")
        self.env["PYTHONPATH"] = str(self.data)
        group = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"][0]
        for source in ("startup", "resume", "compact", "clear", "fork"):
            self.assertIsNotNone(re.fullmatch(group["matcher"], source))
        result = subprocess.run(  # noqa: S602 - Trusted fixture/manifest commands.
            group["hooks"][0]["command"],
            shell=True,
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "session_id": "session-a"}),
            text=True,
            capture_output=True,
            check=True,
            cwd=self.data,
            env=self.env,
        )
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        commands = dict(
            line.split(": ", 1) for line in context.splitlines() if line.startswith(("Enable: ", "Disable: "))
        )
        for action in ("Enable", "Disable"):
            # Exercise shell quoting in commands emitted by our local trusted hook.
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
            active = "was explicitly enabled" in self.hook()
            self.assertEqual(active, action == "Enable")
            self.assertFalse(marker.exists())

    def test_emitted_controls_accept_leading_hyphen_session_ids(self) -> None:
        for session in ("-session", "--session-id", "-"):
            with self.subTest(session=session):
                context = json.loads(self.hook(session=session))["hookSpecificOutput"]["additionalContext"]
                commands = dict(
                    line.split(": ", 1) for line in context.splitlines() if line.startswith(("Enable: ", "Disable: "))
                )
                for action in ("Enable", "Disable"):
                    subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
                    self.assertEqual("was explicitly enabled" in self.hook(session=session), action == "Enable")

    def test_fork_controls_are_fresh_and_do_not_change_parent_state(self) -> None:
        self.control("enable", session="parent")
        context = json.loads(self.hook(session="child", source="fork"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("No stored", context)
        self.assertIn("supersede any controls inherited", context)
        self.assertIn("Parent activation does not activate a fork", context)
        commands = dict(
            line.split(": ", 1) for line in context.splitlines() if line.startswith(("Enable: ", "Disable: "))
        )
        for action in ("Enable", "Disable"):
            self.assertIn("--session-id=child", commands[action])
            self.assertNotIn("parent", commands[action])
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
            self.assertEqual(
                "was explicitly enabled" in self.hook(session="child", source="resume"), action == "Enable"
            )
            self.assertIn("was explicitly enabled", self.hook(session="parent", source="resume"))

    def test_disabled_default_session_isolation_and_clear(self) -> None:
        self.assertIn("No stored", self.hook())
        self.assertEqual(list(self.data.iterdir()), [])
        self.control("enable")
        for source in ("startup", "resume", "compact"):
            self.assertIn("was explicitly enabled", self.hook(source=source))
            self.assertIn("No stored", self.hook(session="session-b", source=source))
        self.assertIn("No stored", self.hook(source="clear"))
        self.assertIn("No stored", self.hook(source="resume"))
        self.control("disable")

    def test_invalid_identity_and_corrupt_state_fail_inactive(self) -> None:
        for session in ("../outside", "x/y", "x; touch outside", "", "x" * 129):
            self.assertEqual(self.hook(session=session), "")
            self.assertNotEqual(self.control("enable", session=session, check=False).returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])
        state = self.data / "z-mode/session-a.json"
        state.parent.mkdir()
        for value in ("invalid", "[]", '{"active":"true"}', "null"):
            state.write_text(value)
            self.assertIn("No stored", self.hook(source="compact"))

    def test_clear_reports_state_removal_failure(self) -> None:
        state = self.data / "z-mode/session-a.json"
        state.mkdir(parents=True)
        output = json.loads(self.hook(source="clear"))
        self.assertIn("could not be removed", output["systemMessage"])
        self.assertIn("inactive for this cleared context", output["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("No stored", output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("stale stored activation", output["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
