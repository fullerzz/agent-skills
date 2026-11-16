"""Activation transitions use isolated state and synthetic companion evidence."""

import errno
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("activation_hook", ROOT / "hooks/session_start.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Session hook fixture could not be loaded")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class ActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = hook.state_path(directory.name, "parent")
        self.report = {
            "companion": {"status": "supported", "path": "/fixture/companion"},
            "bootstrap": {"status": "supported"},
            "session": {"status": "supported", "terminalId": "t1"},
        }

    def test_enable_persists_and_returns_guidance_for_both_hosts(self) -> None:
        for host in ("claude", "codex"):
            with self.subTest(host=host), patch.object(hook, "probe_companion", return_value=self.report) as probe:
                result = hook.apply_control(self.path, host, "enable")
                self.assertEqual(result["state"], {"active": True, "execution": "herdr", "explicitNative": False})
                self.assertEqual(result["persistence"], "persisted")
                self.assertEqual(result["guidance"], "/fixture/companion/skills/hc-workflow/SKILL.md")
                probe.assert_called_once_with(host)
                hook.set_active(self.path, False)

    def test_native_survives_enable_and_never_probes(self) -> None:
        hook.set_execution(self.path, "native")
        with patch.object(hook, "probe_companion") as probe:
            result = hook.apply_control(self.path, "codex", "enable")
        probe.assert_not_called()
        self.assertTrue(result["state"]["explicitNative"])
        self.assertEqual(hook.read_state(self.path), (True, "native"))

    def test_concurrent_native_or_disable_wins_over_inflight_probe(self) -> None:
        for action in ("native", "disable"):
            hook.set_active(self.path, False)

            def during_probe(host: str, action: str = action) -> dict[str, Any]:
                hook.apply_control(self.path, host, action)
                return self.report

            with self.subTest(action=action), patch.object(hook, "probe_companion", side_effect=during_probe):
                hook.apply_control(self.path, "codex", "enable")
            self.assertEqual(hook.read_state(self.path), (action == "native", "native"))

    def test_denied_selection_reports_actual_activation_without_claiming_persistence(self) -> None:
        write = hook.write_state

        def deny_selection(path: str, state: dict[str, object]) -> None:
            if path.endswith(".execution.json"):
                raise PermissionError(errno.EACCES, "fixture denial")
            write(path, state)

        with (
            patch.object(hook, "probe_companion", return_value=self.report),
            patch.object(hook, "write_state", side_effect=deny_selection),
        ):
            result = hook.apply_control(self.path, "claude", "enable")
        self.assertEqual(result["persistence"], "failed")
        self.assertTrue(result["approvalRequired"])
        self.assertEqual(result["state"]["execution"], "native")
        self.assertTrue(result["state"]["active"])

    def test_partial_disable_reports_remaining_execution(self) -> None:
        hook.set_active(self.path, True)
        hook.set_execution(self.path, "herdr")
        unlink = hook.unlink

        def deny_execution(path: str) -> None:
            if path.endswith(".execution.json"):
                raise PermissionError(errno.EPERM, "fixture denial")
            unlink(path)

        with patch.object(hook, "unlink", side_effect=deny_execution):
            result = hook.apply_control(self.path, "codex", "disable")
        self.assertEqual(result["persistence"], "failed")
        self.assertEqual(result["state"], {"active": False, "execution": "herdr", "explicitNative": False})

    def test_resume_compact_and_fresh_fork(self) -> None:
        hook.set_active(self.path, True)
        data = str(Path(self.path).parent.parent)
        with patch.object(hook, "probe_companion", return_value=self.report) as probe:
            context, error = hook.build_context("codex", "parent", data, "resume")
            self.assertIsNone(error)
            self.assertIn("Herdr execution is selected", context)
            hook.build_context("codex", "parent", data, "compact")
            child, error = hook.build_context("codex", "child", data, "fork")
            self.assertIn("No stored", child)
            self.assertIsNone(error)
            probe.assert_called_once()

    def test_failed_or_absent_probe_never_selects(self) -> None:
        for report in (
            {"session": {"status": "unavailable", "reason": "No caller"}},
            {"bootstrap": {"status": "failed", "reason": "Node failed"}, "session": {"status": "untested"}},
        ):
            hook.set_active(self.path, False)
            with patch.object(hook, "probe_companion", return_value=report):
                result = hook.apply_control(self.path, "codex", "enable")
            self.assertEqual(result["state"]["execution"], "native")
            self.assertIsNotNone(result["reason"])

    def test_installation_and_gui_do_not_activate(self) -> None:
        with patch.object(hook, "probe_companion") as probe, patch.dict(os.environ, {"HERDR_ENV": "1"}):
            hook.build_context("claude", "new", str(Path(self.path).parent.parent), "startup")
        probe.assert_not_called()
        self.assertFalse(Path(self.path).exists())

    def test_probe_consumes_host_listing_and_checks_caller_without_shell(self) -> None:
        for host in ("codex", "claude"):
            root = "/fixture/codex/plugins/cache/market/herdr-zstack/1.0"
            listing = (
                {
                    "installed": [
                        {
                            "name": "herdr-zstack",
                            "installed": True,
                            "enabled": True,
                            "marketplaceName": "market",
                            "version": "1.0",
                        }
                    ]
                }
                if host == "codex"
                else [{"id": "herdr-zstack@market", "enabled": True, "scope": "user", "installPath": root}]
            )
            report = self.report | {"companion": {"status": "supported", "path": root}}

            def run(
                argv: list[str],
                listing: dict[str, Any] | list[dict[str, Any]] = listing,
                root: str = root,
                report: dict[str, Any] = report,
                **kwargs: object,
            ) -> SimpleNamespace:
                self.assertNotIn("shell", kwargs)
                self.assertEqual(kwargs["timeout"], 45 if argv[1:4] == ["plugin", "list", "--json"] else 15)
                if argv[1:4] == ["plugin", "list", "--json"]:
                    return SimpleNamespace(stdout=json.dumps(listing))
                self.assertEqual(argv[:3], ["/bin/sh", root + "/scripts/preflight.sh", "/fixture/node"])
                self.assertEqual(json.loads(Path(argv[-1]).read_text()), listing)
                return SimpleNamespace(returncode=0, stdout=json.dumps(report))

            with (
                self.subTest(host=host),
                patch.dict(os.environ, {"HC_TERMINAL_ID": "t1", "CODEX_HOME": "/fixture/codex"}),
                patch("shutil.which", side_effect=lambda name: "/fixture/" + name),
                patch("subprocess.run", side_effect=run),
            ):
                self.assertEqual(hook.probe_companion(host), report)

    def test_node_symlink_keeps_its_dispatch_name(self) -> None:
        node = Path(self.path).parent.parent / "node"
        node.symlink_to(node.parent / "mise")
        listing = [{"id": "herdr-zstack@market", "enabled": True, "scope": "user", "installPath": "/fixture/companion"}]
        with (
            patch.dict(os.environ, {"HC_TERMINAL_ID": "t1"}),
            patch("shutil.which", side_effect=lambda name: str(node) if name == "node" else "/fixture/claude"),
            patch(
                "subprocess.run",
                side_effect=[
                    SimpleNamespace(stdout=json.dumps(listing)),
                    SimpleNamespace(returncode=0, stdout=json.dumps(self.report)),
                ],
            ) as run,
        ):
            hook.probe_companion("claude")
        self.assertEqual(run.call_args_list[1].args[0][2], str(node))

    def test_bootstrap_failures_and_malformed_reports_fail_closed(self) -> None:
        listing = [{"id": "herdr-zstack@market", "enabled": True, "scope": "user", "installPath": "/fixture/companion"}]
        for code, payload in (
            (0, "not json"),
            (0, "[]"),
            (2, '{"session":{"status":"untested"},"bootstrap":[]}'),
            (2, '{"session":{"status":"untested"},"companion":{"status":"supported"}}'),
            (0, "{}"),
            (0, json.dumps(self.report | {"session": {"status": "supported", "terminalId": "other"}})),
            (1, json.dumps(self.report)),
            (2, json.dumps(self.report)),
        ):
            with (
                self.subTest(code=code, payload=payload),
                patch.dict(os.environ, {"HC_TERMINAL_ID": "t1"}),
                patch("shutil.which", return_value="/fixture/node"),
                patch(
                    "subprocess.run",
                    side_effect=[
                        SimpleNamespace(stdout=json.dumps(listing)),
                        SimpleNamespace(returncode=code, stdout=payload),
                    ],
                ),
            ):
                report = hook.probe_companion("claude")
            self.assertEqual(report["session"]["status"], "untested")
            self.assertEqual(report["bootstrap"]["status"], "failed")
        for error in (
            PermissionError("denied"),
            subprocess.TimeoutExpired("fixture", 15),
            subprocess.CalledProcessError(1, "fixture"),
        ):
            with (
                patch.dict(os.environ, {"HC_TERMINAL_ID": "t1"}),
                patch("shutil.which", return_value="/fixture/node"),
                patch("subprocess.run", side_effect=error) as run,
            ):
                report = hook.probe_companion("codex")
            self.assertEqual(report["session"]["status"], "untested")
            run.assert_called_once()

    def test_absent_caller_never_runs_host_cli_or_node(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as run:
            report = hook.probe_companion("codex")
        self.assertEqual(report["session"]["status"], "unavailable")
        run.assert_not_called()

    def test_new_activation_during_probe_is_not_selected(self) -> None:
        def during_probe(host: str) -> dict[str, Any]:
            hook.set_active(self.path, False)
            hook.set_active(self.path, True)
            return self.report

        with patch.object(hook, "probe_companion", side_effect=during_probe):
            result = hook.apply_control(self.path, "codex", "enable")
        self.assertEqual(hook.read_state(self.path), (True, "native"))
        self.assertIn("newer state", result["reason"])

    def test_denied_activation_never_probes_or_retries(self) -> None:
        with (
            patch.object(hook, "write_state", side_effect=PermissionError(errno.EROFS, "denied")) as write,
            patch.object(hook, "probe_companion") as probe,
        ):
            result = hook.apply_control(self.path, "codex", "enable")
        self.assertFalse(result["state"]["active"])
        self.assertEqual(result["persistence"], "failed")
        self.assertTrue(result["approvalRequired"])
        write.assert_called_once()
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
