"""Metadata-only recorder behavior, using isolated temporary data."""

import concurrent.futures
import contextlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / "hooks" / "xray.py"
XRAY = runpy.run_path(str(HELPER))


class XrayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = str(Path(self.temp.name).resolve())
        self.env = {**os.environ, "ZSTACK_XRAY": "1", "PLUGIN_DATA": self.data, "CLAUDE_PLUGIN_DATA": self.data}

    def hook(
        self, event: str | Mapping[str, object], host: str = "codex", env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        raw = event if isinstance(event, str) else json.dumps(event)
        return subprocess.run(  # noqa: S603 - Fixed interpreter/helper; event data is stdin only.
            [sys.executable, "-I", "-S", str(HELPER), "--host=" + host],
            input=raw,
            text=True,
            capture_output=True,
            env=env or self.env,
            check=True,
        )

    def read(self, host: str = "codex", session: str = "session") -> dict[str, Any]:
        return XRAY["read_records"](host, session, self.data)

    def test_disabled_writes_nothing(self) -> None:
        self.hook({"session_id": "session", "hook_event_name": "PreToolUse"}, env={**self.env, "ZSTACK_XRAY": "0"})
        self.assertEqual(list(Path(self.data).iterdir()), [])

    def test_missing_store_is_empty_but_access_errors_are_unavailable(self) -> None:
        self.assertEqual(self.read()["records"], [])
        for operation in ("lstat", "listdir"):
            with self.subTest(operation=operation):
                with patch(f"os.{operation}", side_effect=PermissionError("PRIVATE_CANARY")):
                    with self.assertRaises(PermissionError):
                        self.read()
                    with (
                        patch.object(
                            sys,
                            "argv",
                            [
                                str(HELPER),
                                "--read",
                                "--host=codex",
                                "--session-id=session",
                                "--data-dir",
                                self.data,
                            ],
                        ),
                        contextlib.redirect_stdout(io.StringIO()) as output,
                        contextlib.redirect_stderr(io.StringIO()) as errors,
                    ):
                        XRAY["main"]()
                result = json.loads(output.getvalue())
                self.assertTrue(result["coverage"]["unavailable"])
                self.assertFalse(result["coverage"]["complete"])
                self.assertEqual(result["records"], [])
                self.assertNotIn("PRIVATE_CANARY", output.getvalue() + errors.getvalue())

    def test_host_isolation_and_no_fallback(self) -> None:
        event = {"session_id": "session", "hook_event_name": "Stop"}
        self.hook(event)
        self.hook(event, "claude")
        self.assertEqual(len(self.read()["records"]), 1)
        self.assertEqual(len(self.read("claude")["records"]), 1)
        env = dict(self.env)
        del env["CLAUDE_PLUGIN_DATA"]
        self.assertIn("unavailable", self.hook(event, "claude", env).stderr)
        self.assertEqual(len(self.read("claude")["records"]), 1)

    def test_malformed_and_traversal_fail_open(self) -> None:
        for raw in ("{", "[]", json.dumps({"session_id": "../escape", "hook_event_name": "Stop"}), "x" * 262145):
            result = self.hook(raw)
            self.assertEqual(result.stdout, "")
            self.assertIn("continuing", result.stderr)
        self.assertEqual(list(Path(self.data).iterdir()), [])

    def test_privacy_pairing_and_failure(self) -> None:
        canary = "PRIVATE_PROMPT_RESULT_COMMAND_PATH_CANARY"
        event = {
            "session_id": "session",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": "tool-1",
            "agent_id": "agent-1",
            "turn_id": "turn-1",
            "tool_input": {"command": canary},
            "tool_response": canary,
            "cwd": canary,
            "transcript_path": canary,
            "prompt": canary,
        }
        self.hook(event)
        self.hook({**event, "hook_event_name": "PostToolUseFailure", "error": canary})
        result = self.read()
        self.assertNotIn(canary, json.dumps(result))
        self.assertEqual({x["status"] for x in result["records"]}, {"started", "failed"})
        self.assertEqual(result["coverage"]["unpaired_tool_ids"], 0)
        self.assertEqual(result["coverage"]["ambiguous_tool_ids"], 0)
        self.assertTrue(all(x["attribution"] == "unknown" for x in result["records"]))
        self.assertEqual(result["records"][0]["agent_id"], "agent-1")

    def test_pairing_discloses_missing_actor_or_turn(self) -> None:
        for index, identity in enumerate(({}, {"agent_id": "actor"}, {"turn_id": "turn"})):
            with self.subTest(identity=identity):
                session = f"ambiguous-{index}"
                event = {
                    "session_id": session,
                    "tool_use_id": "same",
                    **identity,
                }
                for kind in ("PreToolUse", "PostToolUse"):
                    self.hook({**event, "hook_event_name": kind})
                result = self.read(session=session)
                self.assertEqual(result["coverage"]["unpaired_tool_ids"], 0)
                self.assertEqual(result["coverage"]["ambiguous_tool_ids"], 1)
                self.assertFalse(result["coverage"]["complete"])
                for record in result["records"]:
                    for key in ("agent_id", "turn_id"):
                        if key not in identity:
                            self.assertNotIn(key, record)

    def test_explicit_skill_attribution_only(self) -> None:
        for tool, inputs in (
            ("Skill", {"skill": "zstack:how"}),
            ("Bash", {"command": "zstack:how"}),
            ("Skill", {"skill": "how"}),
        ):
            self.hook(
                {"session_id": "session", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inputs}
            )
        self.assertEqual(sum(x.get("attribution") == "zstack" for x in self.read()["records"]), 1)

    def test_concurrent_atomic_writes_and_permissions(self) -> None:
        def write(index: int) -> subprocess.CompletedProcess[str]:
            return self.hook(
                {
                    "session_id": "session",
                    "hook_event_name": "PreToolUse",
                    "tool_use_id": str(index),
                    "tool_name": "Read",
                }
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write, range(24)))
        result = self.read()
        self.assertEqual(len(result["records"]), 24)
        self.assertEqual(result["coverage"]["invalid_files"], 0)
        if os.name != "nt":
            for file in Path(self.data).joinpath("xray/codex/session/events").glob("*.json"):
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_corruption_gaps_and_session_scope(self) -> None:
        self.hook({"session_id": "session", "hook_event_name": "PreToolUse", "tool_use_id": "one"})
        self.hook({"session_id": "other", "hook_event_name": "Stop"})
        events = Path(self.data) / "xray/codex/session/events"
        (events / "bad.json").write_text("PRIVATE_CANARY")
        result = self.read()
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["coverage"]["invalid_files"], 1)
        self.assertEqual(result["coverage"]["unpaired_tool_ids"], 1)
        self.assertFalse(result["coverage"]["complete"])
        self.assertNotIn("PRIVATE_CANARY", json.dumps(result))

    @unittest.skipIf(os.name == "nt", "Windows symlinks require additional privileges")
    def test_symlink_file_refused(self) -> None:
        self.hook({"session_id": "session", "hook_event_name": "Stop"})
        events = Path(self.data) / "xray/codex/session/events"
        target = Path(self.data) / "private"
        target.write_text("PRIVATE_CANARY")
        (events / "11111111-1111-1111-1111-111111111111.json").symlink_to(target)
        result = self.read()
        self.assertEqual(result["coverage"]["invalid_files"], 1)
        self.assertNotIn("PRIVATE_CANARY", json.dumps(result))

    @unittest.skipIf(os.name == "nt", "Windows symlinks require additional privileges")
    def test_symlink_directory_refused(self) -> None:
        Path(self.data, "xray").symlink_to(self.data, target_is_directory=True)
        result = self.hook({"session_id": "session", "hook_event_name": "Stop"})
        self.assertIn("continuing", result.stderr)
        with self.assertRaises(ValueError):
            self.read()

    def test_native_expansion_and_actor_scoped_pairing(self) -> None:
        for actor, kind in (("a", "PreToolUse"), ("b", "PostToolUse")):
            self.hook({"session_id": "session", "hook_event_name": kind, "tool_use_id": "same", "agent_id": actor})
        self.hook(
            {
                "session_id": "session",
                "hook_event_name": "UserPromptExpansion",
                "command_source": "plugin",
                "command_name": "zstack:why",
                "prompt": "PRIVATE_CANARY",
            }
        )
        self.hook({"session_id": "session", "hook_event_name": "PreCompact"})
        result = self.read()
        self.assertEqual(result["coverage"]["unpaired_tool_ids"], 2)
        expansion = next(x for x in result["records"] if x["kind"] == "UserPromptExpansion")
        self.assertEqual(expansion["skill_name"], "zstack:why")
        self.assertNotIn("PRIVATE_CANARY", json.dumps(result))

    def test_internal_actual_outcome_and_interrupted_file(self) -> None:
        with patch.dict(os.environ, self.env):
            self.assertTrue(XRAY["record_internal"]("codex", "session", self.data, "disable", "state_change_failed"))
        Path(self.data, "xray/codex/session/events/.interrupted.tmp").write_text("PRIVATE_CANARY")
        result = self.read()
        self.assertEqual(result["records"][0]["status"], "failed")
        self.assertEqual(result["records"][0]["outcome"], "state_change_failed")
        self.assertEqual(result["coverage"]["interrupted_files"], 1)

    def test_cap_disclosed_and_internal_fail_open(self) -> None:
        module = XRAY["write_record"].__globals__
        with patch.dict(os.environ, self.env), patch.dict(module, {"MAX_EVENTS": 1}):
            self.assertTrue(XRAY["record_internal"]("codex", "session", self.data, "enable", "returned"))
            with contextlib.redirect_stderr(io.StringIO()) as warnings:
                self.assertFalse(XRAY["record_internal"]("codex", "session", self.data, "disable", "failed"))
            self.assertIn("continuing", warnings.getvalue())
        result = self.read()
        self.assertTrue(result["coverage"]["cap_reached"])
        self.assertEqual(len(result["records"]), 1)


if __name__ == "__main__":
    unittest.main()
