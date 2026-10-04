# Retain the stdlib unittest runner used by the repository.
# ruff: noqa: PT009

"""Exercise explicit Codex mode controls without personal configuration."""

import json
import os
import re
import runpy
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "hooks/session_start.py"


class CodexHooksTests(unittest.TestCase):
    def test_xray_is_loaded_only_with_explicit_opt_in_and_host(self) -> None:
        record = runpy.run_path(str(HELPER))["record_xray"]
        with patch.dict(os.environ, {"ZSTACK_XRAY": "0"}), patch("runpy.run_path") as loader:
            record("codex", "session-a", str(self.data), "enable", "enabled")
            loader.assert_not_called()
        with patch.dict(os.environ, {"ZSTACK_XRAY": "1"}), patch("runpy.run_path") as loader:
            record(None, "session-a", str(self.data), "enable", "enabled")
            loader.assert_not_called()
            record("codex", "session-a", str(self.data), "enable", "enabled")
            loader.return_value["record_internal"].assert_called_once_with(
                "codex", "session-a", str(self.data), "enable", "enabled"
            )
        with patch.dict(os.environ, {"ZSTACK_XRAY": "1"}), patch("runpy.run_path", side_effect=OSError):
            record("codex", "session-a", str(self.data), "enable", "enabled")

    def test_opt_in_context_has_current_session_read_controls(self) -> None:
        self.env["ZSTACK_XRAY"] = "1"
        context = json.loads(self.hook())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("host codex, session session-a", context)
        self.assertIn("--read --host=codex --session-id=session-a", context)
        self.assertIn("PowerShell Read xray:", context)
        self.assertLess(len(context), 4000)
        self.assertIn("No stored z-mode", context)
        self.assertIn("--host=codex", context)
        read_command = next(
            line.split(": ", 1)[1] for line in context.splitlines() if line.startswith("POSIX sh Read xray:")
        )
        result = subprocess.run(  # noqa: S603 - Command emitted by trusted isolated fixture.
            shlex.split(read_command),
            check=True,
            capture_output=True,
            text=True,
            env=self.env,
        )
        records = json.loads(result.stdout)["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "session_start")
        self.assertEqual(records[0]["attribution"], "zstack")
        self.assertEqual(records[0]["source"], "startup")

    def test_internal_records_follow_actual_control_results(self) -> None:
        fixture = self.data / "plugin"
        (fixture / "hooks").mkdir(parents=True)
        helper = fixture / "hooks/session_start.py"
        helper.write_bytes(HELPER.read_bytes())
        recorder = fixture / "hooks/xray.py"
        recorder.write_text(
            "import json, os\n"
            "def record_internal(host, session_id, data_dir, action, outcome):\n"
            "    with open(os.path.join(data_dir, 'recorded.jsonl'), 'a') as stream:\n"
            "        stream.write(json.dumps([host, session_id, action, outcome]) + '\\n')\n"
        )
        env = dict(self.env, ZSTACK_XRAY="1")
        arguments = [sys.executable, "-I", "-S", str(helper)]
        for action in ("enable", "disable"):
            subprocess.run(  # noqa: S603 - Isolated fixture helper.
                [*arguments, action, "--host=claude", "--session-id=session-a", "--data-dir", str(self.data)],
                check=True,
                env=env,
                capture_output=True,
            )
        state = self.data / "z-mode/session-a.json"
        state.mkdir()
        failed = subprocess.run(  # noqa: S603 - Isolated fixture helper.
            [*arguments, "disable", "--host=claude", "--session-id=session-a", "--data-dir", str(self.data)],
            check=False,
            env=env,
            capture_output=True,
        )
        self.assertEqual(failed.returncode, 1)
        records = [json.loads(line) for line in (self.data / "recorded.jsonl").read_text().splitlines()]
        self.assertEqual(
            records,
            [
                ["claude", "session-a", "enable", "enabled"],
                ["claude", "session-a", "disable", "disabled"],
                ["claude", "session-a", "disable", "state_change_failed"],
            ],
        )
        subprocess.run(  # noqa: S603 - Legacy invocation has no host and does not record.
            [*arguments, "enable", "--session-id=legacy", "--data-dir", str(self.data)],
            check=True,
            env=env,
            capture_output=True,
        )
        self.assertEqual(len((self.data / "recorded.jsonl").read_text().splitlines()), 3)

    def test_xray_context_uses_complete_fallback_with_fixed_budget(self) -> None:
        context = runpy.run_path(str(HELPER))["xray_context"]
        arguments = ("codex", "session-a", "/data", "/plugin/hooks/session_start.py")
        full = context(*arguments, budget=4000)
        self.assertIn("Read xray:", full)
        fallback = context(*arguments, budget=400)
        self.assertLessEqual(len(fallback), 400)
        self.assertIn("recorded-events reference", fallback)
        self.assertNotIn("Read xray:", fallback)
        self.assertEqual(context(*arguments, budget=0), "")

    def test_metadata_hook_manifest_events_and_host_isolation(self) -> None:
        shared = {
            "PreToolUse",
            "PostToolUse",
            "SubagentStart",
            "SubagentStop",
            "SessionEnd",
            "PreCompact",
            "PostCompact",
        }
        for host, filename in (("codex", "codex.json"), ("claude", "hooks.json")):
            hooks = json.loads((ROOT / "hooks" / filename).read_text())["hooks"]
            expected = shared | {"SessionStart"}
            if host == "claude":
                expected |= {"PostToolUseFailure", "UserPromptExpansion"}
            self.assertEqual(set(hooks), expected)
            self.assertEqual(len(hooks["SessionStart"][0]["hooks"]), 1)
            for event in expected - {"SessionStart"}:
                hook = hooks[event][0]["hooks"][0]
                command = hook["command"] if host == "codex" else " ".join(hook["args"])
                self.assertIn("xray.py", command)
                self.assertIn(f"--host={host}", command)
                self.assertNotIn("session_start.py", command)

    def test_disabled_codex_recorders_never_launch_uv(self) -> None:
        # A sentinel executable proves the manifest gate runs before uv, even
        # with malformed stdin and paths containing shell metacharacters.
        launcher = self.data / "uv"
        launcher.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\ncat\n')
        launcher.chmod(0o700)
        hooks = json.loads((ROOT / "hooks/codex.json").read_text())["hooks"]
        plugin_root = str(self.data / "plugin's $root `literal`")
        for event, groups in hooks.items():
            if event == "SessionStart":
                continue
            for value in (None, "", "0", "true", "1"):
                with self.subTest(event=event, value=value):
                    env = dict(self.env, PATH=f"{self.data}:/bin", PLUGIN_ROOT=plugin_root)
                    if value is not None:
                        env["ZSTACK_XRAY"] = value
                    result = subprocess.run(  # noqa: S602 - Trusted manifest and isolated sentinel.
                        groups[0]["hooks"][0]["command"],
                        shell=True,
                        input="malformed input",
                        text=True,
                        capture_output=True,
                        check=True,
                        env=env,
                    )
                    self.assertEqual(result.stderr, "")
                    expected = (
                        f"run\n--no-project\n--no-config\npython\n-I\n-S\n{plugin_root}/hooks/xray.py\n"
                        "--host=codex\nmalformed input"
                    )
                    self.assertEqual(result.stdout, expected if value == "1" else "")

    def test_claude_tool_recorders_are_nonblocking_exec_hooks(self) -> None:
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]
        for event, groups in hooks.items():
            hook = groups[0]["hooks"][0]
            self.assertEqual(hook["command"], "uv")
            self.assertIsInstance(hook["args"], list)
            self.assertEqual(hook.get("async", False), event in {"PreToolUse", "PostToolUse", "PostToolUseFailure"})

    def test_shell_serialization_preserves_apostrophes_and_metacharacters(self) -> None:
        serialize = runpy.run_path(str(HELPER))["control_command"]
        arguments = ["uv", "C:\\Users\\O'Neil\\plugin $root `literal`\\session_start.py", "--data-dir", "C:\\O'Neil"]
        self.assertEqual(shlex.split(serialize(arguments, "posix")), arguments)
        powershell = serialize(arguments, "powershell")
        self.assertEqual(
            powershell,
            "& 'uv' 'C:\\Users\\O''Neil\\plugin $root `literal`\\session_start.py' '--data-dir' 'C:\\O''Neil'",
        )
        self.assertEqual(
            serialize(["uv", "C:\\\u2018O\u2019Neil"], "powershell"), "& 'uv' 'C:\\\u2018\u2018O\u2019\u2019Neil'"
        )

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="zstack hook ")
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name).resolve()
        inherited = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("CLAUDE_PLUGIN_") and key != "ZSTACK_XRAY"
        }
        self.env = dict(inherited, PLUGIN_ROOT=str(ROOT), PLUGIN_DATA=str(self.data))

    def hook(self, session: str = "session-a", source: str = "startup") -> str:
        result = subprocess.run(  # noqa: S603 - Trusted fixture/manifest commands.
            [sys.executable, "-I", "-S", str(HELPER), "--host=codex"],
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
        self.assertIn(
            result.stderr,
            ("", "zstack xray: metadata capture unavailable; continuing\n")
            if self.env.get("ZSTACK_XRAY") == "1"
            else ("",),
        )
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
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        group = json.loads((ROOT / manifest["hooks"]).read_text())["hooks"]["SessionStart"][0]
        self.env["CLAUDE_PLUGIN_ROOT"] = str(self.data / "unrelated-plugin")
        self.env["CLAUDE_PLUGIN_DATA"] = str(self.data / "unrelated-data")
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
            line.removeprefix("POSIX sh ").split(": ", 1)
            for line in context.splitlines()
            if line.startswith(("POSIX sh Enable: ", "POSIX sh Disable: "))
        )
        for action in ("Enable", "Disable"):
            # Exercise shell quoting in commands emitted by our local trusted hook.
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
            active = "was explicitly enabled" in self.hook()
            self.assertEqual(active, action == "Enable")
            self.assertFalse(marker.exists())

    def test_configured_command_uses_claude_plugin_variables(self) -> None:
        plugin_root = self.data / "Claude's plugin $root `literal`"
        (plugin_root / "hooks").mkdir(parents=True)
        (plugin_root / "hooks/session_start.py").write_bytes(HELPER.read_bytes())
        env = {key: value for key, value in self.env.items() if key not in ("PLUGIN_ROOT", "PLUGIN_DATA")}
        env |= {
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "CLAUDE_PLUGIN_DATA": str(self.data),
            "PLUGIN_DATA": "unrelated-relative",
        }
        group = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"][0]
        for source in ("startup", "resume", "compact", "clear", "fork"):
            self.assertIsNotNone(re.fullmatch(group["matcher"], source))
        hook = group["hooks"][0]
        # Model Claude's documented exec-form placeholder substitution, without a shell.
        command = [hook["command"], *(arg.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root)) for arg in hook["args"])]
        for inherited_data in ("unrelated-relative", str(self.data / "unrelated-absolute")):
            env["PLUGIN_DATA"] = inherited_data
            result = subprocess.run(  # noqa: S603 - Trusted fixture/manifest commands.
                command,
                input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "session_id": "claude-a"}),
                text=True,
                capture_output=True,
                check=True,
                cwd=self.data,
                env=env,
            )
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            enable = next(
                line.split(": ", 1)[1] for line in context.splitlines() if line.startswith("POSIX sh Enable: ")
            )
            self.assertEqual(shlex.split(enable)[-1], str(self.data))
            self.assertIn("PowerShell Enable: & 'uv'", context)
            self.assertIn("PowerShell Disable: & 'uv'", context)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        enable = next(line.split(": ", 1)[1] for line in context.splitlines() if line.startswith("POSIX sh Enable: "))
        self.assertIn(str((plugin_root / "hooks/session_start.py").resolve()), shlex.split(enable))
        subprocess.run(enable, shell=True, check=True, env=env, cwd=self.data)  # noqa: S602
        self.assertTrue((self.data / "z-mode/claude-a.json").is_file())

    def test_emitted_controls_accept_leading_hyphen_session_ids(self) -> None:
        for session in ("-session", "--session-id", "-"):
            with self.subTest(session=session):
                context = json.loads(self.hook(session=session))["hookSpecificOutput"]["additionalContext"]
                commands = dict(
                    line.removeprefix("POSIX sh ").split(": ", 1)
                    for line in context.splitlines()
                    if line.startswith(("POSIX sh Enable: ", "POSIX sh Disable: "))
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
            line.removeprefix("POSIX sh ").split(": ", 1)
            for line in context.splitlines()
            if line.startswith(("POSIX sh Enable: ", "POSIX sh Disable: "))
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
