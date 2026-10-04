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
    def test_hermes_metadata_privacy_roundtrip_and_host_isolation(self) -> None:
        canary = "/PRIVATE_PROMPT_RESULT_COMMAND_PATH_CANARY"
        native_ids = {
            "parent_session_id": "parent",
            "child_session_id": "child",
            "child_subagent_id": "child-agent",
            "parent_subagent_id": "parent-agent",
            "task_id": "task",
            "turn_id": "turn",
            "parent_turn_id": "parent-turn",
            "tool_call_id": "tool",
            "agent_id": "actor",
            "api_request_id": "request",
        }
        payload = {
            "session_id": "parent",
            **native_ids,
            "tool_name": "skill_view",
            "status": "ok",
            "args": {"name": "zstack:how", "path": canary},
            "result": canary,
            "error": canary,
            "prompt": canary,
            "messages": [canary],
            "cwd": canary,
            "tool_input": {"skill": canary},
            "aux_task": "compression",
        }
        with patch.dict(os.environ, self.env):
            for hook in XRAY["HERMES_KINDS"]:
                self.assertTrue(XRAY["record_hermes"](hook, payload, self.data))
        records = self.read("hermes", "parent")["records"]
        self.assertEqual(len(records), len(XRAY["HERMES_KINDS"]))
        self.assertNotIn(canary, json.dumps(records))
        self.assertEqual(self.read("codex", "parent")["records"], [])
        self.assertEqual(self.read("claude", "parent")["records"], [])
        self.assertEqual(self.read("hermes", "child")["records"], [])
        for record in records:
            for key, value in native_ids.items():
                self.assertEqual(record[key], value)
            self.assertEqual(record["tool_use_id"], "tool")
            if record["kind"] in ("PreToolUse", "PostToolUse"):
                self.assertEqual(record["skill_name"], "zstack:how")
                self.assertEqual(record["tool_name"], "skill_view")
        read = subprocess.run(  # noqa: S603 - Fixed helper and isolated capture.
            [
                sys.executable,
                "-I",
                "-S",
                str(HELPER),
                "--read",
                "--host=hermes",
                "--session-id=parent",
                "--data-dir",
                self.data,
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(json.loads(read.stdout)["records"], records)

    def test_hermes_subagents_use_parent_scope_without_invented_identity(self) -> None:
        payload = {"session_id": "child", "parent_session_id": "parent", "task_id": "task"}
        with patch.dict(os.environ, self.env):
            self.assertTrue(XRAY["record_hermes"]("subagent_start", payload, self.data))
        record = self.read("hermes", "parent")["records"][0]
        self.assertEqual(record["task_id"], "task")
        self.assertNotIn("agent_id", record)
        self.assertNotIn("turn_id", record)
        self.assertNotIn("child_session_id", record)
        self.assertEqual(self.read("hermes", "child")["records"], [])

    def test_hermes_tool_outcomes_and_missing_pair_identity(self) -> None:
        with patch.dict(os.environ, self.env):
            for status in ("ok", "error", "blocked", "cancelled", "unexpected"):
                payload = {"session_id": "session", "tool_call_id": status, "status": status}
                for hook in ("pre_tool_call", "post_tool_call"):
                    self.assertTrue(XRAY["record_hermes"](hook, payload, self.data))
        result = self.read("hermes")
        self.assertEqual(result["coverage"]["ambiguous_tool_ids"], 4)
        self.assertEqual(result["coverage"]["unpaired_tool_ids"], 1)
        self.assertEqual(
            {record["status"] for record in result["records"]},
            {"started", "returned", "failed", "blocked", "cancelled", "unknown"},
        )

    def test_hermes_rejects_unverified_attribution_and_invalid_identifiers(self) -> None:
        for tool, args in (
            ("skill_view", {"name": "how"}),
            ("skill_view", {"name": "zstack:how/path"}),
            ("terminal", {"name": "zstack:how"}),
            ("Skill", {"name": "zstack:how"}),
        ):
            record = XRAY["normalize_hermes"](
                "pre_tool_call",
                {
                    "session_id": "session",
                    "tool_name": tool,
                    "args": args,
                    "tool_input": {"skill": "zstack:how"},
                    **dict.fromkeys(XRAY["IDENTIFIER_FIELDS"], "/private/path"),
                },
            )
            self.assertEqual(record["attribution"], "unknown")
            self.assertNotIn("skill_name", record)
            self.assertFalse(set(record) & set(XRAY["IDENTIFIER_FIELDS"]))

    def test_hermes_disabled_and_fail_open(self) -> None:
        with patch.dict(os.environ, {"ZSTACK_XRAY": "0"}):
            self.assertFalse(XRAY["record_hermes"]("unknown", {}, self.data))
        self.assertEqual(list(Path(self.data).iterdir()), [])

        with patch.dict(os.environ, self.env), contextlib.redirect_stderr(io.StringIO()) as errors:
            for hook, payload in (
                ("unknown", {}),
                ("pre_tool_call", {"session_id": "../private"}),
                ("subagent_start", {"session_id": "child", "parent_session_id": "../private"}),
            ):
                self.assertFalse(XRAY["record_hermes"](hook, payload, self.data))
        self.assertNotIn("private", errors.getvalue())
        self.assertEqual(list(Path(self.data).iterdir()), [])
        with (
            patch.dict(os.environ, self.env),
            patch("os.lstat", side_effect=PermissionError("/PRIVATE_STORAGE_PATH")),
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertFalse(XRAY["record_hermes"]("pre_tool_call", {"session_id": "session"}, self.data))
        self.assertNotIn("PRIVATE", errors.getvalue())
        self.assertIn("continuing", errors.getvalue())

    def test_hermes_compression_observes_only_model_calls(self) -> None:
        with patch.dict(os.environ, self.env), contextlib.redirect_stderr(io.StringIO()):
            for task in (None, "title", "memory"):
                self.assertFalse(
                    XRAY["record_hermes"](
                        "pre_auxiliary_call",
                        {
                            "session_id": "session",
                            "aux_task": task,
                        },
                        self.data,
                    )
                )
            for hook, error in (
                ("pre_auxiliary_call", None),
                ("post_auxiliary_call", None),
                ("post_auxiliary_call", "/PRIVATE_ERROR"),
            ):
                self.assertTrue(
                    XRAY["record_hermes"](
                        hook,
                        {
                            "session_id": "session",
                            "aux_task": "compression",
                            "error": error,
                            "api_request_id": "request",
                            "retry_count": 123,
                            "messages": "/PRIVATE_PROMPT",
                        },
                        self.data,
                    )
                )
        records = self.read("hermes")["records"]
        self.assertEqual(
            [record["kind"] for record in records], ["PreCompressionCall", "PostCompressionCall", "PostCompressionCall"]
        )
        self.assertEqual([record["status"] for record in records], ["started", "returned", "failed"])
        self.assertNotIn("PRIVATE", json.dumps(records))
        self.assertTrue(all(record["api_request_id"] == "request" for record in records))
        self.assertTrue(all("retry_count" not in record for record in records))

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
