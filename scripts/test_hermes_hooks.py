"""Hermes lifecycle payload fixtures without a personal installation or model call."""

import inspect
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from test_hermes_plugin import ROOT, Registry, load_plugin
from validate import load_yaml

from hooks import hermes, session_start, xray

if TYPE_CHECKING:
    from collections.abc import Callable


class HermesHookTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="zstack Hermes '")
        self.addCleanup(temporary.cleanup)
        self.data = str(Path(temporary.name).resolve())
        self.hooks = hermes.HermesHooks(lambda: self.data)
        environment = patch.dict(os.environ, {"ZSTACK_XRAY": "0"})
        environment.start()
        self.addCleanup(environment.stop)

    def control(self, context: str, action: str) -> None:
        prefix = f"POSIX sh {action}: "
        command = next(line.removeprefix(prefix) for line in context.splitlines() if line.startswith(prefix))
        argv = shlex.split(command)
        # Exercise the exact generated helper arguments without invoking a second uv resolver.
        result = subprocess.run(  # noqa: S603 - Generated isolated helper, explicit argv, no shell.
            [sys.executable, *argv[argv.index("-I") :]],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_registration_is_declarative_and_manifest_matches(self) -> None:
        registry = Registry()
        load_plugin(ROOT / "__init__.py").register(registry)
        manifest = load_yaml((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            self.fail("Plugin manifest must be a mapping")
        self.assertEqual(set(registry.hooks), set(manifest["provides_hooks"]))
        for callback in registry.hooks.values():
            self.assertTrue(any(p.kind == p.VAR_KEYWORD for p in inspect.signature(callback).parameters.values()))
        self.assertEqual(list(Path(self.data).iterdir()), [])

    def test_explicit_activation_survives_new_adapter_resume_and_same_id_compaction(self) -> None:
        initial = self.hooks.pre_llm_call(session_id="session_a", is_first_turn=True)["context"]
        self.assertIn("No stored z-mode activation", initial)
        self.assertIn("--host=hermes", initial)
        self.assertFalse((Path(self.data) / "z-mode").exists())
        self.control(initial, "Enable")
        restarted = hermes.HermesHooks(lambda: self.data)
        for history in ([{"role": "user", "content": "prior turn"}], [{"role": "user", "content": "summary"}]):
            context = restarted.pre_llm_call(session_id="session_a", conversation_history=history)["context"]
            self.assertIn("z-mode was explicitly enabled", context)
        self.control(context, "Disable")
        self.assertIn("No stored z-mode activation", restarted.pre_llm_call(session_id="session_a")["context"])

    def test_fork_subagent_and_unverified_rotation_do_not_inherit_activation(self) -> None:
        parent = self.hooks.pre_llm_call(session_id="parent")["context"]
        self.control(parent, "Enable")
        for child in ("branch", "subagent", "rotated"):
            self.hooks.observe("subagent_start", parent_session_id="parent", child_session_id=child)
            context = self.hooks.pre_llm_call(session_id=child, parent_session_id="parent")["context"]
            self.assertIn("No stored z-mode activation", context)
            self.assertIn(f"--session-id={child}", context)
            self.assertNotIn("--session-id=parent", context)
            self.control(context, "Disable")
        self.assertIn("z-mode was explicitly enabled", self.hooks.pre_llm_call(session_id="parent")["context"])

    def test_reset_clears_only_replacement_and_end_does_not_destroy_resume(self) -> None:
        for session in ("old", "new"):
            context = self.hooks.pre_llm_call(session_id=session)["context"]
            self.control(context, "Enable")
            self.control(context, "Herdr")
        self.hooks.on_session_reset(session_id="new", old_session_id="old", new_session_id="new")
        self.assertIn("No stored z-mode activation", self.hooks.pre_llm_call(session_id="new")["context"])
        self.assertNotIn("Herdr execution was explicitly enabled", self.hooks.pre_llm_call(session_id="new")["context"])
        for event in ("on_session_end", "on_session_finalize"):
            self.hooks.observe(event, session_id="old", completed=True)
        self.assertIn("z-mode was explicitly enabled", self.hooks.pre_llm_call(session_id="old")["context"])
        self.assertIn("Herdr execution was explicitly enabled", self.hooks.pre_llm_call(session_id="old")["context"])

    def test_execution_preference_survives_adapter_restart_but_not_new_sessions(self) -> None:
        context = self.hooks.pre_llm_call(session_id="parent")["context"]
        self.control(context, "Herdr")
        restarted = hermes.HermesHooks(lambda: self.data)
        context = restarted.pre_llm_call(session_id="parent")["context"]
        self.assertIn("Herdr execution was explicitly enabled", context)
        self.assertIn("No stored z-mode activation", context)
        self.assertNotIn(
            "Herdr execution was explicitly enabled", restarted.pre_llm_call(session_id="child")["context"]
        )
        self.control(context, "Native")
        self.assertNotIn(
            "Herdr execution was explicitly enabled", restarted.pre_llm_call(session_id="parent")["context"]
        )

    def test_failed_reset_stays_inactive_until_clear_can_be_retried(self) -> None:
        self.control(self.hooks.pre_llm_call(session_id="session")["context"], "Enable")
        with patch.object(session_start, "set_active", side_effect=PermissionError("private error")):
            self.hooks.on_session_reset(session_id="session")
            context = self.hooks.pre_llm_call(session_id="session")["context"]
        self.assertIn("inactive for this cleared context", context)
        self.assertNotIn("was explicitly enabled", context)
        self.assertNotIn("private error", context)
        self.assertIn("No stored z-mode activation", self.hooks.pre_llm_call(session_id="session")["context"])

    def test_bad_identity_never_uses_task_or_parent_as_session(self) -> None:
        for invalid in (None, "", "../parent", "parent:child", 12):
            context = self.hooks.pre_llm_call(session_id=invalid, task_id="task", parent_session_id="parent")["context"]
            self.assertIn("controls", context)
            self.assertNotIn("POSIX sh Enable:", context)
        self.assertEqual(list(Path(self.data).iterdir()), [])

    def test_corrupt_state_is_inactive_and_profile_state_is_isolated(self) -> None:
        path = Path(session_start.state_path(self.data, "same_id"))
        path.parent.mkdir()
        path.write_text("broken", encoding="utf-8")
        self.assertIn("No stored z-mode activation", self.hooks.pre_llm_call(session_id="same_id")["context"])
        self.control(self.hooks.pre_llm_call(session_id="same_id")["context"], "Enable")
        other_profile = hermes.HermesHooks(lambda: str(Path(self.data) / "other-profile"))
        self.assertIn("No stored z-mode activation", other_profile.pre_llm_call(session_id="same_id")["context"])

    def test_observers_are_disabled_by_default_and_never_block_tools_on_failure(self) -> None:
        observer: Callable[..., object] = self.hooks.observe
        with patch.object(xray, "record_hermes") as recorder:
            self.assertIsNone(observer("pre_tool_call", session_id="session", tool_name="terminal"))
            recorder.assert_not_called()
        with (
            patch.dict(os.environ, {"ZSTACK_XRAY": "1"}),
            patch.object(xray, "record_hermes", side_effect=OSError("private failure")),
        ):
            self.assertIsNone(observer("pre_tool_call", session_id="session", tool_name="terminal"))

    def test_xray_records_opt_in_without_activating_and_ignores_non_compression_auxiliary(self) -> None:
        with patch.dict(os.environ, {"ZSTACK_XRAY": "1"}):
            context = self.hooks.pre_llm_call(session_id="session", user_message="PRIVATE PROMPT")["context"]
            self.assertIn("Optional xray recording is enabled for host hermes", context)
            self.assertIn("No stored z-mode activation", context)
            self.hooks.observe("pre_auxiliary_call", session_id="session", aux_task="title_generation")
        records = xray.read_records("hermes", "session", self.data)
        events = records["records"]
        if not isinstance(events, list):
            self.fail("Xray records must be a list")
        self.assertEqual({record["kind"] for record in events}, {"session_start", "PreLLMCall"})
        self.assertNotIn("PRIVATE PROMPT", str(records))


if __name__ == "__main__":
    unittest.main()
