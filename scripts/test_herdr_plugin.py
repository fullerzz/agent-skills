"""Phase 1 Herdr adapter contracts; temp fixtures only, no live Herdr or personal state."""

from __future__ import annotations

import contextlib
import copy
import fcntl
import importlib.util
import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import tomllib

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SOCKET_A = "/tmp/zstack-test-a/herdr.sock"  # noqa: S108 - never connected; identity strings only.
SOCKET_B = "/tmp/zstack-test-b/herdr.sock"  # noqa: S108


def load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hr = load("herdr_run", ROOT / "integrations/herdr/herdr_run.py")
pl = load("herdr_plugin_entry", ROOT / "integrations/herdr/plugin.py")


def render(*args: Any, width: int = 200, height: int = 1000, **kwargs: Any) -> str:  # noqa: ANN401 - board args.
    """The board frame as plain text, as a pane of `width` x `height` cells shows it."""
    console = pl.Console(file=io.StringIO(), width=width, height=height, color_system=None)
    console.print(pl.board_frame(*args, width=width, **kwargs))
    return console.file.getvalue()


REAL_CALLER_TERMINAL = hr.caller_terminal


def raw_snapshot(*panes: tuple[str, str, str | None, str | None, str | None]) -> dict[str, Any]:
    """Shape of `herdr api snapshot`; each pane is (pane_id, terminal_id, agent, session, name)."""
    pane_rows, agent_rows = [], []
    for pane_id, terminal_id, agent, session, name in panes:
        workspace = pane_id.split(":")[0]
        pane_rows.append(
            {"pane_id": pane_id, "terminal_id": terminal_id, "workspace_id": workspace, "agent_status": "unknown"}
        )
        if agent:
            row = {
                "pane_id": pane_id,
                "terminal_id": terminal_id,
                "agent": agent,
                "agent_status": "idle",
                "agent_session": {"agent": agent, "kind": "id", "source": f"herdr:{agent}", "value": session},
            }
            if name:
                row["name"] = name
            agent_rows.append(row)
    return {
        "id": "cli:api:snapshot",
        "result": {"type": "snapshot", "snapshot": {"panes": pane_rows, "agents": agent_rows}},
    }


BASE = raw_snapshot(
    ("w1:p1", "term_coord", "claude", "sess-coord", None),
    ("w1:p2", "term_worker", "codex", "sess-worker", "worker"),
)


def tree(root: Path) -> dict[str, tuple[bytes | None, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
    }


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.registry = self.root / "registry"
        environment = patch.dict(os.environ, {"ZSTACK_HERDR_REGISTRY": str(self.registry)})
        environment.start()
        self.addCleanup(environment.stop)
        for key in ("HERDR_PANE_ID", "HERDR_SOCKET_PATH", "HERDR_BIN_PATH", "XDG_STATE_HOME"):
            os.environ.pop(key, None)
        self.terminals: dict[str, str] = {}  # caller pane id (or alias) -> terminal; unknown panes resolve to None.
        caller = patch.object(hr, "caller_terminal", lambda _socket, pane: self.terminals.get(pane))
        caller.start()
        self.addCleanup(caller.stop)

    def snapshot_file(self, raw: dict[str, Any], name: str = "snapshot.json") -> str:
        path = self.root / "snapshots" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
        return str(path)

    def cli(self, *argv: str, code: int = 0) -> Any:  # noqa: ANN401 - parsed JSON or stderr text.
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(hr.main(list(argv)), code, err.getvalue())
        return json.loads(out.getvalue()) if code == 0 else err.getvalue()

    def make_run(self, name: str = "run", run_id: str = "r1", socket: str = SOCKET_A, *extra: str) -> Path:
        path = self.root / name / "herdr-run.json"
        path.parent.mkdir(exist_ok=True)
        snap = self.snapshot_file(BASE)
        self.cli(
            "init",
            str(path),
            "--run-id",
            run_id,
            "--socket",
            socket,
            "--coordinator-pane",
            "w1:p1",
            "--snapshot",
            snap,
            *extra,
        )
        return path

    def inspect(self, path: Path, raw: dict[str, Any] | None = BASE, socket: str = SOCKET_A) -> dict[str, Any]:
        snapshot = hr.normalize_snapshot(raw, socket) if raw is not None else None
        return hr.inspect_run(path, snapshot)

    def task(self, view: dict[str, Any], task_id: str) -> dict[str, Any]:
        return next(task for task in view["tasks"] if task["id"] == task_id)

    def fake_herdr(self, *args: str, **_: Any) -> dict[str, Any]:  # noqa: ANN401
        self.calls.append(args)
        if self.raw is BASE:
            self.raw = copy.deepcopy(BASE)
        panes = self.raw["result"]["snapshot"]["panes"] if self.raw else []
        pane = next((row for row in panes if row["pane_id"] == args[2]), None)
        if args[:2] == ("pane", "report-metadata") and pane is not None:
            tokens = pane.setdefault("tokens", {})
            for flag, value in itertools.pairwise(args):
                if flag == "--token":
                    name, value = value.split("=", 1)
                    tokens[name] = value.strip()[:80]  # Herdr's documented token value ceiling.
                elif flag == "--clear-token":
                    tokens.pop(value, None)
        return {}


class RecordTests(Fixture):
    def test_enroll_update_roundtrip(self) -> None:
        path = self.make_run()
        snap = self.snapshot_file(BASE)
        self.cli("task", "add", str(path), "t1", "--title", "Phase one", "--worktree", "/repo")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", snap)
        (path.parent / "report.md").write_text("done", encoding="utf-8")
        self.cli("task", "report", str(path), "t1", "report.md")
        self.cli("task", "evidence", str(path), "t1", "tests.log", "--revision", "abc123")
        task = self.cli("task", "accept", str(path), "t1")
        self.assertEqual(task["acceptance"], "accepted")
        self.assertEqual(task["evidence"], [{"ref": "tests.log", "revision": "abc123"}])
        run, gaps = hr.read_run(path)
        self.assertEqual(gaps, [])
        binding = run["tasks"][0]["binding"]
        self.assertEqual(
            (binding["terminal_id"], binding["agent_session"], binding["agent_name"]),
            ("term_worker", "sess-worker", "worker"),
        )
        self.assertEqual(run["coordinator"]["binding"]["agent_session"], "sess-coord")
        [entry] = hr.enrolled_runs(SOCKET_A, self.registry)
        self.assertEqual((entry["run_id"], entry["run_file"], entry["data_gaps"]), ("r1", str(path), []))
        view = self.task(self.inspect(path), "t1")
        self.assertEqual(view["binding_check"]["status"], "ok")
        self.assertEqual(view["lifecycle"]["observed"], "idle")
        self.assertEqual(view["reports"], [{"ref": "report.md", "exists": True}])
        self.assertEqual(view["data_gaps"], [])
        self.assertEqual(hr.resolve_focus_target(view), {"ok": True, "pane_id": "w1:p2"})
        self.assertEqual(self.cli("task", "reject", str(path), "t1")["acceptance"], "rejected")
        self.assertFalse(list(path.parent.glob(".*.tmp")))

    def test_missing_and_malformed_acceptance(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "add", str(path), "t2")
        data = json.loads(path.read_text(encoding="utf-8"))
        del data["tasks"][0]["acceptance"]
        data["tasks"][1]["acceptance"] = "yes"
        path.write_text(json.dumps(data), encoding="utf-8")
        view = self.inspect(path)
        missing, malformed = self.task(view, "t1"), self.task(view, "t2")
        self.assertEqual(missing["acceptance"], "not recorded")
        self.assertFalse(any("acceptance" in gap for gap in missing["data_gaps"]))
        self.assertEqual(malformed["acceptance"], "not recorded")
        self.assertTrue(any("invalid acceptance" in gap for gap in malformed["data_gaps"]))
        self.assertIn("refusing to update", self.cli("task", "accept", str(path), "t1", code=1))

    def test_malformed_records_are_data_gaps(self) -> None:
        path = self.root / "bad" / "herdr-run.json"
        path.parent.mkdir()
        for contents in ("{not json", "[]", json.dumps({"version": 2}), json.dumps({"version": 1, "run_id": "../x"})):
            path.write_text(contents, encoding="utf-8")
            view = self.inspect(path)
            self.assertIsNone(view["run_id"])
            self.assertFalse(view["sources"]["run_file"]["ok"])
            self.assertTrue(view["data_gaps"])
        self.assertTrue(self.inspect(self.root / "absent.json")["data_gaps"])

    def test_evidence_refs(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "evidence", str(path), "t1", "https://ci.example/run/1", "--revision", "deadbeef")
        self.cli("task", "evidence", str(path), "t1", "notes/manual.md")
        view = self.task(self.inspect(path), "t1")
        self.assertEqual(
            view["evidence"],
            [{"ref": "https://ci.example/run/1", "revision": "deadbeef"}, {"ref": "notes/manual.md", "revision": None}],
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"][0]["evidence"] = [{"ref": "", "revision": 5}]
        path.write_text(json.dumps(data), encoding="utf-8")
        view = self.task(self.inspect(path), "t1")
        self.assertEqual(view["evidence"], [])
        self.assertTrue(any("evidence" in gap for gap in view["data_gaps"]))

    def test_workers_cannot_accept(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w1:p2"}):
            self.assertIn("coordinator-only", self.cli("task", "accept", str(path), "t1", code=1))
            self.assertIn("coordinator-only", self.cli("task", "evidence", str(path), "t1", "x", code=1))
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w1:p1"}):
            self.cli("task", "accept", str(path), "t1")

    def test_only_the_bound_coordinator_can_accept(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.terminals = {"w1:p1": "term_coord", "w2:p1": "term_other", "w3:p1": "term_coord"}
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w2:p1"}):  # an agent from another run, bound nowhere here.
            self.assertIn("not the bound coordinator", self.cli("task", "accept", str(path), "t1", code=1))
            self.assertIn("not the bound coordinator", self.cli("task", "evidence", str(path), "t1", "x", code=1))
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w3:p1"}):  # the coordinator after a move.
            self.cli("task", "accept", str(path), "t1")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["coordinator"]["binding"] = None
        hr.atomic_write(path, data)
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w2:p1"}):  # unbound coordinator: only workers are refused.
            self.cli("task", "reject", str(path), "t1")
        self.cli("coordinator", "bind", str(path), "--pane", "w1:p1", "--snapshot", self.snapshot_file(BASE))
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p1", "--snapshot", self.snapshot_file(BASE))
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w1:p1"}):  # a pane that is also a worker stays refused.
            self.assertIn("bound to a worker task", self.cli("task", "accept", str(path), "t1", code=1))

    def test_missing_report(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "none")
        self.cli("task", "add", str(path), "gone")
        self.cli("task", "report", str(path), "gone", "reports/gone.md")
        view = self.inspect(path)
        self.assertTrue(any("no report" in gap for gap in self.task(view, "none")["data_gaps"]))
        gone = self.task(view, "gone")
        self.assertEqual(gone["reports"], [{"ref": "reports/gone.md", "exists": False}])
        self.assertTrue(any("report file missing" in gap for gap in gone["data_gaps"]))

    def test_coordinator_bind_recovers_after_restart(self) -> None:
        raw = raw_snapshot(
            ("w1:p1", "term_restored", "codex", "sess-restored", "coordinator"),
            ("w1:p2", "term_worker", "codex", "sess-worker", "worker"),
        )
        snapshot = self.snapshot_file(raw, "restored.json")
        for name, extra in (("plain", ()), ("orch", ("--orch-store", "orch"))):
            with self.subTest(run=name):
                path = self.make_run(name, name, SOCKET_A, "--label", "Keep label", "--session", "Keep session", *extra)
                self.cli("task", "add", str(path), "t1", "--title", "Keep task", "--worktree", "/repo")
                if not extra:
                    self.cli("task", "report", str(path), "t1", "report.md")
                    self.cli("task", "evidence", str(path), "t1", "tests.log", "--revision", "abc123")
                    self.cli("task", "accept", str(path), "t1")
                before = json.loads(path.read_text(encoding="utf-8"))
                registry = tree(self.registry)
                self.assertEqual(self.inspect(path, raw)["coordinator"]["binding_check"]["status"], "occupant changed")
                result = self.cli("coordinator", "bind", str(path), "--pane", "w1:p1", "--snapshot", snapshot)
                self.assertEqual(
                    (result["binding"]["terminal_id"], result["binding"]["agent_session"], result["binding"]["agent"]),
                    ("term_restored", "sess-restored", "codex"),
                )
                self.assertEqual(result["label"], "Keep label")
                self.assertEqual(self.inspect(path, raw)["coordinator"]["binding_check"]["status"], "ok")
                after = json.loads(path.read_text(encoding="utf-8"))
                before["coordinator"]["binding"] = after["coordinator"]["binding"]
                before["updated_at"] = after["updated_at"]
                self.assertEqual(after, before)
                self.assertEqual(tree(self.registry), registry)

    def test_rebind_drops_session_carried_over_from_previous_terminal(self) -> None:
        # Phase 9 live: after a restart Herdr reported the dead pre-restart session for a fresh Claude.
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        carried = raw_snapshot(
            ("w1:p1", "term_coord_new", "claude", "sess-coord", "coord-fresh"),
            ("w1:p2", "term_worker_new", "codex", "sess-worker", "worker"),
        )
        snapshot = self.snapshot_file(carried, "carried.json")
        coordinator = self.cli("coordinator", "bind", str(path), "--pane", "w1:p1", "--snapshot", snapshot)
        task = self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", snapshot)
        for result in (coordinator, task):
            self.assertEqual((result["binding"]["terminal_id"][-3:], result["binding"]["agent_session"]), ("new", None))
            self.assertEqual(result["warnings"], [hr.CARRIED_SESSION])
        corrected = raw_snapshot(
            ("w1:p1", "term_coord_new", "claude", "sess-fresh", "coord-fresh"),
            ("w1:p2", "term_worker_new", "codex", "sess-fresh-worker", "worker"),
        )
        for raw in (carried, corrected):
            view = self.inspect(path, raw)
            self.assertEqual(view["coordinator"]["binding_check"]["status"], "ok")
            self.assertEqual(self.task(view, "t1")["binding_check"]["status"], "ok")
        rebound = self.cli(
            "coordinator", "bind", str(path), "--pane", "w1:p1", "--snapshot", self.snapshot_file(corrected)
        )
        self.assertEqual((rebound["binding"]["agent_session"], "warnings" in rebound), ("sess-fresh", False))

    def test_concurrent_enrollments_of_one_run_id_conflict(self) -> None:
        first = self.make_run("a", "r1")
        second = self.root / "b" / "herdr-run.json"
        second.parent.mkdir()
        second.write_bytes(first.read_bytes())
        entry = hr.registry_path(self.registry, SOCKET_A, "r1")
        entry.unlink()  # neither file is enrolled; both enrollments race for the same registry entry.
        writing, release, real_write = threading.Event(), threading.Event(), hr.atomic_write

        def slow_write(path: Path, data: dict[str, Any]) -> None:
            if path.name == entry.name and not writing.is_set():
                writing.set()
                release.wait(5)
            real_write(path, data)

        results: dict[str, Any] = {}

        def enroll(name: str, run_file: Path) -> None:
            try:
                results[name] = hr.enroll(run_file, self.registry)
            except hr.UserError as error:
                results[name] = error

        with patch.object(hr, "atomic_write", slow_write):
            one = threading.Thread(target=enroll, args=("first", first))
            one.start()
            self.assertTrue(writing.wait(5))
            two = threading.Thread(target=enroll, args=("second", second))
            two.start()
            two.join(0.3)
            self.assertTrue(two.is_alive())  # waits on the registry lock instead of passing the conflict check.
            release.set()
            one.join(5)
            two.join(5)
        self.assertIsInstance(results["second"], hr.UserError)
        self.assertEqual(json.loads(entry.read_text(encoding="utf-8"))["run_file"], str(first))

    def test_repeated_evidence_is_recorded_once(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        for revision in ("abc", "abc", "def"):
            self.cli("task", "evidence", str(path), "t1", "tests.log", "--revision", revision)
        self.assertEqual(
            [item["revision"] for item in json.loads(path.read_text(encoding="utf-8"))["tasks"][0]["evidence"]],
            ["abc", "def"],
        )

    def test_worker_guard_falls_back_to_pane_for_bindings_without_terminal(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"][0]["binding"] = {"pane_id": "w1:p2", "terminal_id": None}
        hr.atomic_write(path, data)
        self.terminals["w1:p2"] = "term_worker"
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w1:p2"}):
            self.assertIn("coordinator-only", self.cli("task", "accept", str(path), "t1", code=1))

    def test_malformed_snapshot_result_is_an_error_not_a_crash(self) -> None:
        for raw in ({"result": "busy"}, {"result": []}, {"result": {"snapshot": None}}):
            with self.subTest(raw=raw), self.assertRaises(hr.UserError):
                hr.normalize_snapshot(raw, SOCKET_A)

    def test_coordinator_bind_invalid_pane_leaves_record_intact(self) -> None:
        path = self.make_run()
        raw = raw_snapshot(("w1:p1", "", "claude", "sess-coord", None))
        snapshot = self.snapshot_file(raw)
        before = tree(self.root)
        for pane, error in (("w9:p9", "not found"), ("w1:p1", "no terminal_id")):
            with self.subTest(pane=pane):
                self.assertIn(
                    error,
                    self.cli("coordinator", "bind", str(path), "--pane", pane, "--snapshot", snapshot, code=1),
                )
                self.assertEqual(tree(self.root), before)

    def test_unresolvable_report_ref_is_a_gap(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "report", str(path), "t1", "~zstack-no-such-user/report.md")
        view = self.cli("inspect", str(path), "--snapshot", self.snapshot_file(BASE))
        task = self.task(view, "t1")
        self.assertEqual(task["reports"], [{"ref": "~zstack-no-such-user/report.md", "exists": False}])
        self.assertTrue(any("report file missing" in gap for gap in task["data_gaps"]))

    def test_concurrent_updates_are_serialized(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        loaded, release = threading.Event(), threading.Event()
        original = hr.load_for_update

        def slow_load(target: Path) -> dict[str, Any]:
            run = original(target)
            if not loaded.is_set():  # hold the first writer between its read and its write.
                loaded.set()
                release.wait(5)
            return run

        def command(*argv: str) -> threading.Thread:
            thread = threading.Thread(target=hr.command_task, args=(hr.parser().parse_args(["task", *argv]),))
            thread.start()
            return thread

        with patch.object(hr, "load_for_update", slow_load):
            accept = command("accept", str(path), "t1")
            self.assertTrue(loaded.wait(5))
            report = command("report", str(path), "t1", "r.md")
            report.join(0.3)
            self.assertTrue(report.is_alive(), "worker report did not wait for the coordinator's update")
            self.assertEqual(self.task(self.inspect(path), "t1")["acceptance"], "not recorded")  # readers never block.
            release.set()
            accept.join(5)
            report.join(5)
        task = self.task(self.inspect(path), "t1")
        self.assertEqual((task["acceptance"], [item["ref"] for item in task["reports"]]), ("accepted", ["r.md"]))

    def test_refuses_to_write_records_it_would_reject(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        for argv in (
            ("report", "t1", " "),
            ("evidence", "t1", "tests.log", "--revision", ""),
            ("add", "t2", "--title", ""),
            ("add", "t2", "--repository", " "),
            ("add", "t2", "--worktree", ""),
        ):
            with self.subTest(argv=argv):
                before = path.read_bytes()
                self.assertIn("refusing to write", self.cli("task", argv[0], str(path), *argv[1:], code=1))
                self.assertEqual(path.read_bytes(), before)
        self.cli("task", "accept", str(path), "t1")
        snap = self.snapshot_file(BASE)
        for flag in ("--session", "--orch-store"):
            with self.subTest(flag=flag):
                fresh = self.root / flag.strip("-") / "herdr-run.json"
                fresh.parent.mkdir()
                argv = ("init", str(fresh), "--run-id", flag.strip("-"), "--socket", SOCKET_A, "--snapshot", snap)
                self.assertIn("refusing to write", self.cli(*argv, flag, "", code=1))
                self.assertEqual(list(fresh.parent.iterdir()), [])
                self.cli(*argv)

    def test_worker_guard_follows_terminal_after_move(self) -> None:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        moved = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w2:p1", "term_worker", "codex", "sess-worker", "worker"),
        )
        self.cli("task", "bind", str(path), "t1", "--pane", "w2:p1", "--snapshot", self.snapshot_file(moved))
        self.terminals = {"w1:p2": "term_worker", "w2:p1": "term_worker", "w1:p1": "term_coord"}
        for pane in ("w1:p2", "w2:p1"):  # the worker's launch-time id is an alias after the move.
            with patch.dict(os.environ, {"HERDR_PANE_ID": pane}):
                self.assertIn("coordinator-only", self.cli("task", "accept", str(path), "t1", code=1))
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w1:p1"}):
            self.cli("task", "accept", str(path), "t1")
        self.cli("task", "reject", str(path), "t1")  # a coordinator outside Herdr has no HERDR_PANE_ID.
        self.terminals = {}
        with patch.dict(os.environ, {"HERDR_PANE_ID": "w2:p1"}):  # unresolvable: fall back to pane ids.
            self.assertIn("coordinator-only", self.cli("task", "accept", str(path), "t1", code=1))
        fake = self.root / "fake-herdr"
        fake.write_text(
            '#!/bin/sh\n[ "$1 $2 $3" = "pane get w1:p2" ] || exit 1\n'
            'echo \'{"result": {"type": "pane_info", "pane": {"pane_id": "w2:p1", "terminal_id": "term_worker"}}}\'\n'
        )
        fake.chmod(0o755)
        with patch.dict(os.environ, {"HERDR_BIN_PATH": str(fake)}):
            self.assertEqual(REAL_CALLER_TERMINAL(SOCKET_A, "w1:p2"), "term_worker")
            self.assertIsNone(REAL_CALLER_TERMINAL(SOCKET_A, "w9:p9"))
        with patch.dict(os.environ, {"HERDR_BIN_PATH": str(self.root / "absent")}):
            self.assertIsNone(REAL_CALLER_TERMINAL(SOCKET_A, "w1:p2"))

    def test_updates_through_a_symlink_reach_the_target(self) -> None:
        target = self.make_run("shared dir")
        link = self.root / "task dir" / "herdr-run.json"
        link.parent.mkdir()
        link.symlink_to(target)
        self.cli("task", "add", str(link), "t9")
        self.assertTrue(link.is_symlink())
        self.assertEqual([task["id"] for task in hr.read_run(target)[0]["tasks"]], ["t9"])


class RegistryTests(Fixture):
    def test_endpoint_session_collision(self) -> None:
        a = self.make_run("a", "same", SOCKET_A)
        b = self.make_run("b", "same", SOCKET_B)
        [entry_a] = hr.enrolled_runs(SOCKET_A, self.registry)
        [entry_b] = hr.enrolled_runs(SOCKET_B, self.registry)
        self.assertEqual((entry_a["run_file"], entry_b["run_file"]), (str(a), str(b)))
        self.assertNotEqual(entry_a["registry_entry"], entry_b["registry_entry"])
        # Same pane IDs on another server are not this run's panes.
        view = self.inspect(a, BASE, SOCKET_B)
        self.assertEqual(view["coordinator"]["binding_check"]["status"], "stale endpoint")
        self.assertFalse(hr.resolve_focus_target({"id": "c", **view["coordinator"]})["ok"])
        # Same run ID on the same endpoint from another file is refused unless replaced.
        c = self.root / "c" / "herdr-run.json"
        c.parent.mkdir()
        c.write_text(a.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertIn("already enrolled", self.cli("enroll", str(c), code=1))
        self.cli("enroll", str(a))  # idempotent for the same file
        self.cli("enroll", str(c), "--replace")
        [entry] = hr.enrolled_runs(SOCKET_A, self.registry)
        self.assertEqual(entry["run_file"], str(c))

    def test_unrelated_runs(self) -> None:
        a = self.make_run("a", "alpha")
        b = self.make_run("b", "beta")
        self.make_run("other", "gamma", SOCKET_B)
        self.cli("task", "add", str(a), "ta")
        self.cli("task", "add", str(b), "tb")
        self.assertEqual([task["id"] for task in self.inspect(a)["tasks"]], ["ta"])
        self.assertEqual(sorted(entry["run_id"] for entry in self.cli("runs", "--socket", SOCKET_A)), ["alpha", "beta"])
        (self.registry / hr.endpoint_key(SOCKET_A) / "junk.json").write_text("{", encoding="utf-8")
        entries = hr.enrolled_runs(SOCKET_A, self.registry)
        self.assertTrue(any(entry["data_gaps"] for entry in entries))
        self.assertEqual(hr.enrolled_runs("/tmp/none.sock", self.registry), [])  # noqa: S108

    def test_registry_location(self) -> None:
        with patch.dict(os.environ, {"ZSTACK_HERDR_REGISTRY": "", "XDG_STATE_HOME": str(self.root / "state")}):
            self.assertEqual(hr.registry_root(), self.root / "state/zstack/herdr/runs")
        self.assertEqual(hr.registry_root(self.root / "x"), self.root / "x")


class BindingTests(Fixture):
    def bound(self) -> Path:
        path = self.make_run()
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        return path

    def status(self, path: Path, raw: dict[str, Any]) -> dict[str, Any]:
        return self.task(self.inspect(path, raw), "t1")

    def test_reused_agent_names(self) -> None:
        path = self.bound()
        # Name now belongs to another agent while the bound terminal is still alive.
        raw = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w1:p2", "term_worker", "codex", "sess-worker", None),
            ("w1:p3", "term_new", "codex", "sess-new", "worker"),
        )
        self.assertEqual(self.status(path, raw)["binding_check"]["observed_pane_id"], "w1:p2")
        # Bound terminal gone; the reused name elsewhere is not the task's worker.
        raw = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None), ("w1:p3", "term_new", "codex", "sess-new", "worker")
        )
        task = self.status(path, raw)
        self.assertEqual(task["binding_check"]["status"], "pane missing")
        self.assertFalse(hr.resolve_focus_target(task)["ok"])

    def test_changed_occupant(self) -> None:
        path = self.bound()
        raw = raw_snapshot(("w1:p2", "term_worker", "codex", "sess-other", "worker"))
        task = self.status(path, raw)
        self.assertEqual(task["binding_check"]["status"], "occupant changed")
        self.assertIsNone(task["lifecycle"]["observed"])
        self.assertFalse(hr.resolve_focus_target(task)["ok"])
        self.assertEqual(
            self.status(path, raw_snapshot(("w1:p2", "term_worker", None, None, None)))["binding_check"]["status"],
            "occupant changed",
        )
        reused = raw_snapshot(("w1:p2", "term_fresh", "codex", "sess-worker", None))
        self.assertEqual(self.status(path, reused)["binding_check"]["status"], "occupant changed")

    def test_moved_pane(self) -> None:
        path = self.bound()
        task = self.status(path, raw_snapshot(("w2:p7", "term_worker", "codex", "sess-worker", "worker")))
        self.assertEqual(
            (task["binding_check"]["status"], task["binding_check"]["observed_pane_id"]), ("moved", "w2:p7")
        )
        # Same terminal and session in a new pane: focusable at the observed pane.
        self.assertEqual(hr.resolve_focus_target(task), {"ok": True, "pane_id": "w2:p7"})
        # A moved terminal with a different session is not the bound occupant.
        other = self.status(path, raw_snapshot(("w2:p7", "term_worker", "codex", "sess-other", "worker")))
        self.assertEqual(other["binding_check"]["status"], "occupant changed")
        self.assertFalse(hr.resolve_focus_target(other)["ok"])

    def test_focus_rejects_unvalidated_statuses(self) -> None:
        for status in ("ambiguous", "stale endpoint", "occupant changed", "pane missing", "snapshot unavailable"):
            task = {"id": "t", "binding_check": {"status": status, "observed_pane_id": "w1:p2"}}
            self.assertFalse(hr.resolve_focus_target(task)["ok"], status)

    def test_ambiguous_and_unavailable(self) -> None:
        path = self.bound()
        dup = raw_snapshot(
            ("w1:p2", "term_worker", "codex", "sess-worker", None), ("w1:p9", "term_worker", None, None, None)
        )
        self.assertEqual(self.status(path, dup)["binding_check"]["status"], "ambiguous")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"][0]["binding"]["terminal_id"] = None
        path.write_text(json.dumps(data), encoding="utf-8")
        task = self.status(path, BASE)
        self.assertEqual(task["binding_check"]["status"], "ambiguous")
        self.assertFalse(hr.resolve_focus_target(task)["ok"])
        self.assertEqual(self.task(self.inspect(path, None), "t1")["binding_check"]["status"], "snapshot unavailable")
        with self.assertRaises(hr.UserError):
            hr.normalize_snapshot({"error": {"code": "server_not_running"}}, SOCKET_A)
        with patch.dict(os.environ, {"HERDR_BIN_PATH": str(self.root / "missing-herdr")}):
            view = self.cli("inspect", str(path))
        self.assertFalse(view["sources"]["herdr"]["ok"])
        self.assertIn("snapshot failed", view["sources"]["herdr"]["error"])


class OrchAndReadOnlyTests(Fixture):
    def orch_run(self) -> tuple[Path, Path]:
        sys.path.insert(0, str(hr.ORCH_DIR))
        from store import Store

        store_dir = self.root / "run" / "orch"
        store = Store(store_dir)
        try:
            store.init()
            store.unit_add("u1", "main", "Build adapter")
            store.unit_add("u2", "main")
            store.unit_set("u1", "review", pr=7, sha="a" * 40)
            store.ledger_record(7, "a" * 40, "unit-test-verified", "uv run tests", "z-agent")
            store.ledger_record(8, "b" * 40, "type-check-only", "unrelated")
            store.inbox_push("worker", "u1", "done", "reports/u1.md")
        finally:
            store.close()
        path = self.make_run("run", "orch-run", SOCKET_A, "--orch-store", "orch")
        self.cli("task", "add", str(path), "u1")
        self.cli("task", "bind", str(path), "u1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        return path, store_dir

    def test_orch_evidence_matches_the_units_current_revision(self) -> None:
        path, store_dir = self.orch_run()
        from store import Store

        store = Store(store_dir)
        try:
            store.ledger_record(7, "c" * 40, "unit-test-verified", "older revision")
            store.unit_set("u2", "review", pr=7)
        finally:
            store.close()
        view = self.inspect(path)
        self.assertEqual([item["revision"] for item in self.task(view, "u1")["evidence"]], ["a" * 40])
        self.assertEqual(self.task(view, "u2")["evidence"], [])

    def test_orch_store_mapping(self) -> None:
        path, _ = self.orch_run()
        view = self.inspect(path)
        u1, u2 = self.task(view, "u1"), self.task(view, "u2")
        self.assertEqual(u1["title"], "Build adapter")
        self.assertEqual(u1["acceptance"], "not recorded")
        self.assertEqual(u1["binding_check"]["status"], "ok")
        self.assertEqual(u1["lifecycle"], {"observed": "idle", "orch_state": "review", "reported_status": "done"})
        self.assertEqual(u1["reports"], [{"ref": "reports/u1.md", "exists": False}])
        self.assertEqual(
            u1["evidence"],
            [{"ref": "uv run tests", "revision": "a" * 40, "verdict": "unit-test-verified", "source": "orch ledger"}],
        )
        self.assertEqual((u2["binding_check"]["status"], u2["evidence"]), ("unbound", []))
        self.assertIn("orch store", self.cli("task", "accept", str(path), "u1", code=1))
        self.assertIn("orch inbox push", self.cli("task", "report", str(path), "u1", "x.md", code=1))
        stored = json.loads(path.read_text(encoding="utf-8"))["tasks"][0]
        self.assertFalse({"acceptance", "evidence", "reports"} & stored.keys())

    def test_inspection_is_read_only(self) -> None:
        path, store_dir = self.orch_run()
        plain = self.make_run("plain", "plain")
        self.cli("task", "add", str(plain), "t1")
        self.cli("task", "report", str(plain), "t1", "r.md")
        snap = self.snapshot_file(BASE)
        before = tree(self.root)
        self.inspect(path)
        self.inspect(plain)
        self.cli("inspect", str(path), "--snapshot", snap)
        self.cli("inspect", str(plain), "--snapshot", snap)
        self.cli("runs", "--socket", SOCKET_A)
        hr.enrolled_runs(SOCKET_A, self.registry)
        self.assertEqual(tree(self.root), before)
        self.assertFalse((store_dir / ".orch.lock").exists())
        self.assertFalse((store_dir / "status.md").exists())
        self.assertEqual(len(list((store_dir / "inbox").glob("*.tsv"))), 1)

    def test_missing_orch_package_is_a_gap_in_fresh_processes(self) -> None:
        package = self.root / "package with spaces" / "integrations/herdr"
        package.mkdir(parents=True)
        for name in ("herdr_run.py", "plugin.py"):
            (package / name).write_bytes((ROOT / "integrations/herdr" / name).read_bytes())
        path = self.make_run("run", "orch-run", SOCKET_A, "--orch-store", "orch")
        self.cli("task", "add", str(path), "u1")
        self.cli("task", "bind", str(path), "u1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        plain = self.make_run("plain", "plain")
        raw = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w1:p2", "term_worker", "codex", "sess-worker", "worker"),
            ("w1:p3", "term_plain", "claude", "sess-plain", None),
        )
        data = json.loads(plain.read_text(encoding="utf-8"))
        data["coordinator"]["binding"] = hr.capture_binding(hr.normalize_snapshot(raw, SOCKET_A), "w1:p3")
        hr.atomic_write(plain, data)
        snapshot = self.snapshot_file(raw)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        state = Path(directory.name)
        fake = state / "fake-herdr"
        fake.write_text('#!/bin/sh\ncase "$1" in api) cat "$FAKE_SNAPSHOT";; *) echo "{}";; esac\n')
        fake.chmod(0o755)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HERDR_BIN_PATH": str(fake),
            "HERDR_SOCKET_PATH": SOCKET_A,
            "HERDR_PLUGIN_STATE_DIR": str(state / "observations"),
            "ZSTACK_HERDR_REGISTRY": str(self.registry),
            "FAKE_SNAPSHOT": snapshot,
        }
        before = tree(self.root)
        commands = [
            ("herdr_run.py", ["inspect", str(path), "--snapshot", snapshot], "w1:p2", '"orch_store"'),
            ("plugin.py", ["board"], "w1:p2", "STALE: orch_store"),
            ("plugin.py", ["open-board"], "w1:p2", "board opened for pane w1:p2"),
            ("plugin.py", ["focus-coordinator"], "w1:p2", "focused coordinator at w1:p1"),
            ("plugin.py", ["focus-worker"], "w1:p1", "focused u1 at w1:p2"),
            ("plugin.py", ["reconcile"], "w1:p2", "orch-run: orch_store:"),
            ("plugin.py", ["open-board"], "w1:p3", "board opened for pane w1:p3"),
        ]
        for script, args, pane, expected in commands:
            with self.subTest(command=args[0], pane=pane):
                # Isolated fresh interpreters cannot reuse an imported Store or a site-package fallback. The
                # board alone keeps site-packages for rich, which its pane command adds; no `store` is installed.
                flags = ["-I", "-B"] if args == ["board"] else ["-I", "-S", "-B"]
                result = subprocess.run(  # noqa: S603
                    [sys.executable, *flags, str(package / script), *args],
                    env={**environment, "HERDR_PANE_ID": pane},
                    input="q",
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)
                if script == "herdr_run.py":
                    view = json.loads(result.stdout)
                    self.assertFalse(view["sources"]["orch_store"]["ok"])
                    self.assertTrue(any("No module named 'store'" in gap for gap in view["data_gaps"]))
                    self.assertEqual(view["coordinator"]["binding_check"]["status"], "ok")
        observation = pl.read_observation(pl.observation_path(state / "observations", SOCKET_A, "orch-run"))
        self.assertIn("orch_store", observation["stale"])
        self.assertEqual(tree(self.root), before)


class PluginTests(Fixture):
    """Board, run resolution, and metadata with a fake Herdr; no live server."""

    def setUp(self) -> None:
        super().setUp()
        self.calls: list[tuple[str, ...]] = []
        self.raw: dict[str, Any] | None = copy.deepcopy(BASE)
        fake_snapshot = patch.object(hr, "live_snapshot", self.fake_snapshot)
        fake_herdr = patch.object(pl, "herdr", self.fake_herdr)
        for fake in (fake_snapshot, fake_herdr):
            fake.start()
            self.addCleanup(fake.stop)

    def fake_snapshot(self, socket: str) -> dict[str, Any]:
        if self.raw is None:
            raise hr.UserError("herdr snapshot failed: server_not_running")
        return hr.normalize_snapshot(self.raw, socket)

    def worker_run(self, name: str = "run", run_id: str = "r1") -> Path:
        path = self.make_run(name, run_id)
        self.cli("task", "add", str(path), "t1", "--title", "Phase two", "--worktree", "/repo wt")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        return path

    def board(self, pane: str = "w1:p2") -> Any:  # noqa: ANN401 - plugin Board.
        return pl.Board(SOCKET_A, pane, self.registry, io.StringIO())

    def test_resolve_run_none_one_many(self) -> None:
        snapshot = self.fake_snapshot(SOCKET_A)
        self.assertEqual(pl.resolve_run(SOCKET_A, "w1:p2", self.registry, snapshot)["choices"], [])
        self.assertIn("no enrolled run on this", pl.resolve_run(SOCKET_A, "w1:p2", self.registry, snapshot)["error"])
        self.assertFalse(self.registry.exists())  # resolution wrote nothing.
        path = self.worker_run("a", "alpha")
        one = pl.resolve_run(SOCKET_A, "w1:p2", self.registry, snapshot)
        self.assertEqual((one["run_id"], one["run_file"], one["roles"]), ("alpha", str(path), ["t1"]))
        self.assertIn(
            "no enrolled run for pane w1:p9", pl.resolve_run(SOCKET_A, "w1:p9", self.registry, snapshot)["error"]
        )
        self.make_run("b", "beta")  # same coordinator pane in a second run.
        many = pl.resolve_run(SOCKET_A, "w1:p1", self.registry, snapshot)
        self.assertNotIn("run_file", many)
        self.assertEqual(sorted(item["run_id"] for item in many["choices"]), ["alpha", "beta"])
        self.assertEqual(pl.resolve_run(SOCKET_A, "w1:p2", self.registry, snapshot)["run_id"], "alpha")
        # Unvalidated bindings never claim a pane, and no snapshot means no guess.
        gone = hr.normalize_snapshot(raw_snapshot(("w1:p1", "term_coord", "claude", "sess-coord", None)), SOCKET_A)
        self.assertNotIn("run_file", pl.resolve_run(SOCKET_A, "w1:p2", self.registry, gone))
        self.assertIn("snapshot unavailable", pl.resolve_run(SOCKET_A, "w1:p2", self.registry, None)["error"])

    def test_context_pane(self) -> None:
        context = json.dumps({"focused_pane_id": "w1:p2"})
        with patch.dict(os.environ, {"HERDR_PLUGIN_CONTEXT_JSON": context, "HERDR_PANE_ID": "w1:p9"}):
            self.assertEqual(pl.context_pane(), "w1:p2")
        with patch.dict(os.environ, {"HERDR_PLUGIN_CONTEXT_JSON": "{bad", "HERDR_PANE_ID": "w1:p9"}):
            self.assertEqual(pl.context_pane(), "w1:p9")

    def test_board_render_fresh(self) -> None:
        path = self.worker_run()
        (path.parent / "r.md").write_text("done", encoding="utf-8")
        self.cli("task", "report", str(path), "t1", "r.md")
        self.cli("task", "evidence", str(path), "t1", "tests.log", "--revision", "0123456789abcdef")
        self.cli("task", "accept", str(path), "t1")
        board = self.board()
        board.refresh()
        text = render(board.view, board.last_ok, board.stale, board.message)
        for expected in (
            "zstack r1 · read ",
            "coord  claude @ w1:p1 ok",
            "1 focus · c coord · r refresh · q quit",
        ):
            self.assertIn(expected, text)
        self.assertRegex(
            text, r'\n1 +t1 +ok +accepted +1@0123456 +1/1 +idle +codex "worker" @ w1:p2 +repo wt +Phase two'
        )
        self.assertNotIn("!", text)  # nothing outside the table needs saying.
        self.assertNotIn("STALE", text)
        self.assertNotIn("never", text)

    def test_board_stale_keeps_last_good_view(self) -> None:
        path = self.worker_run()
        board = self.board()
        board.refresh()
        good, stamps = board.view, dict(board.last_ok)
        self.raw = None  # Herdr read fails.
        board.refresh()
        self.assertIs(board.view, good)
        self.assertIn("server_not_running", board.stale)
        self.assertEqual(board.last_ok["herdr"], stamps["herdr"])
        self.assertIn("STALE: herdr", render(board.view, board.last_ok, board.stale))
        self.raw = BASE
        path.write_text("{corrupt", encoding="utf-8")  # run-file read fails.
        board.refresh()
        self.assertIs(board.view, good)
        self.assertIn("run_file", board.stale)
        text = render(board.view, board.last_ok, board.stale)
        self.assertIn("STALE: run_file", text)
        self.assertRegex(text, r"\n1 +t1 ")  # last good data still shown.
        self.cli("task", "add", str(self.make_run("fresh", "r1", SOCKET_A, "--registry", str(self.root / "r2"))), "t9")
        path.write_text((self.root / "fresh/herdr-run.json").read_text(encoding="utf-8"), encoding="utf-8")
        board.refresh()  # recovers on the next good read.
        self.assertIsNone(board.stale)
        self.assertEqual([task["id"] for task in board.view["tasks"]], ["t9"])

    def test_board_shows_gaps_and_no_run(self) -> None:
        path = self.worker_run()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"][0]["acceptance"] = "maybe"
        path.write_text(json.dumps(data), encoding="utf-8")
        board = self.board()
        board.refresh()
        text = render(board.view, board.last_ok, board.stale)
        self.assertIn("! task t1: invalid acceptance", text)
        self.assertNotIn("no report registered", text)  # the rpt column shows "-".
        self.assertRegex(text, r"\n1 +t1 +ok +- ")
        nobody = self.board("w1:p9")
        nobody.refresh()
        self.assertIsNone(nobody.view)
        self.assertIn("no enrolled run for pane w1:p9", render(nobody.view, {}, None, nobody.message))

    def test_board_choose_run(self) -> None:
        self.worker_run("a", "alpha")
        self.worker_run("b", "beta")
        board = self.board("w1:p1")
        board.refresh()
        text = render(board.view, board.last_ok, board.stale, board.message, board.choices)
        self.assertIn("several enrolled runs bind pane w1:p1", text)
        self.assertIn("[2] beta", text)
        board.key("2")
        self.assertEqual(board.view["run_id"], "beta")

    def test_board_is_read_only_and_labels_own_source(self) -> None:
        self.worker_run()
        before = tree(self.root)
        board = self.board()
        board.refresh()
        board.refresh()
        self.assertEqual(tree(self.root), before)
        self.assertEqual(len(self.calls), 2)  # coordinator + worker once; unchanged labels are not resent.
        for call in self.calls:
            self.assertEqual(call[:2], ("pane", "report-metadata"))
            self.assertEqual(call[call.index("--source") + 1], pl.SOURCE)
            flags = {arg for arg in call if arg.startswith("--")}
            self.assertEqual(flags, {"--source", "--token"})
        worker = next(call for call in self.calls if call[2] == "w1:p2")
        tokens = [worker[i + 1] for i, arg in enumerate(worker) if arg == "--token"]
        self.assertEqual(tokens, ["zstack_phase=not recorded", "zstack_role=worker", "zstack_run=r1", "zstack_task=t1"])

    def test_labels_only_for_validated_bindings(self) -> None:
        path = self.worker_run()
        moved = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w2:p7", "term_worker", "codex", "sess-worker", None),
        )
        changed = raw_snapshot(("w1:p2", "term_worker", "codex", "sess-new", None))
        self.assertEqual(set(pl.label_tokens(self.inspect(path, moved))), {"w1:p1", "w2:p7"})
        self.assertEqual(pl.label_tokens(self.inspect(path, changed)), {})

    def test_entries_after_nine_get_letter_keys(self) -> None:
        path = self.make_run()
        for index in range(1, 11):
            self.cli("task", "add", str(path), f"t{index}")
        self.cli("task", "bind", str(path), "t10", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        board = self.board()
        board.refresh()
        text = render(board.view, board.last_ok)
        self.assertRegex(text, r"\n9 +t9 ")
        self.assertRegex(text, r"\na +t10 ")
        self.assertIn("1-a focus", text)
        self.assertTrue(board.key("a"))
        self.assertIn(("agent", "focus", "w1:p2"), self.calls)

    def test_render_strips_terminal_controls(self) -> None:
        path = self.worker_run()
        self.cli("task", "add", str(path), "t2", "--title", "evil \x1b]0;owned\x07 \x1b[2J title\x9b")
        board = self.board()
        board.refresh()
        text = render(board.view, board.last_ok, message="note \x1b[31m")
        self.assertFalse(set(text) & {"\x1b", "\x07", "\x9b"})
        self.assertIn("evil ]0;owned [2J title", text)

    def test_open_board_without_enrollment_fails(self) -> None:
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": SOCKET_A, "HERDR_PANE_ID": "w1:p9"}):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(pl.command_open_board(), 1)
        self.assertIn("board not opened", out.getvalue())
        self.assertFalse([call for call in self.calls if call[:3] == ("plugin", "pane", "open")])

    def test_open_board_opens_a_tab_for_the_caller(self) -> None:
        self.worker_run()
        context = json.dumps({"focused_pane_id": "w1:p2", "workspace_id": "w1"})
        environment = {"HERDR_SOCKET_PATH": SOCKET_A, "HERDR_PLUGIN_CONTEXT_JSON": context}
        with patch.dict(os.environ, environment), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pl.command_open_board(), 0)
        opened = next(call for call in self.calls if call[:3] == ("plugin", "pane", "open"))
        self.assertEqual(opened[opened.index("--placement") + 1], "tab")
        self.assertEqual(opened[opened.index("--workspace") + 1], "w1")
        self.assertEqual(opened[opened.index("--env") + 1], "ZSTACK_BOARD_PANE=w1:p2")
        self.assertNotIn("--target-pane", opened)  # Herdr rejects a target pane for tab plugin panes.
        with patch.dict(os.environ, {**environment, "ZSTACK_BOARD_PANE": "w1:p1"}):
            self.assertEqual(pl.context_pane(), "w1:p1")  # the board tab resolves its caller, not itself.

    def test_board_notes_and_fit(self) -> None:
        path = self.worker_run()
        self.cli("task", "report", str(path), "t1", "gone.md")
        self.raw = raw_snapshot(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w2:p7", "term_worker", "codex", "sess-worker", None),
        )
        board = self.board("w1:p1")
        board.refresh()
        text = render(board.view, board.last_ok)
        self.assertIn('! t1: codex "worker" @ w2:p7 moved from w1:p2', text)
        self.assertIn("! t1: missing report gone.md", text)
        self.assertNotIn("report file missing", text)
        self.assertRegex(text, r" 0/1 ")
        lines = render(board.view, board.last_ok, width=20, height=5).rstrip("\n").split("\n")
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(len(line) <= 20 for line in lines))
        self.assertTrue(lines[0].startswith("zstack r1"))
        self.assertTrue(lines[3].startswith("… "))
        self.assertEqual(lines[4], "1 focus · c coord ·…")  # the key line survives, cut with an ellipsis.

    def test_narrow_overflowing_pane_keeps_state_columns_and_notices(self) -> None:
        path = self.worker_run()
        self.cli("task", "accept", str(path), "t1")
        self.cli("task", "add", str(path), "x" * 80, "--title", "a long descriptive title " * 4)
        for index in range(20):
            self.cli("task", "add", str(path), f"n{index}")
        board = self.board()
        board.refresh()
        frame = render(board.view, board.last_ok, message="focus refused: gone", width=80, height=24)
        lines = frame.rstrip("\n").split("\n")
        self.assertEqual(len(lines), 24)
        self.assertTrue(all(len(line) <= 80 for line in lines), lines)
        rows = [line for line in lines if line[:2] in ("1 ", "2 ")]
        self.assertRegex(rows[0], r"^1 +t1 +ok +accepted ")  # a long sibling ID does not push state off.
        self.assertRegex(rows[1], r"^2 +x+… +unbound ")
        self.assertIn("focus refused: gone", lines)  # notices survive vertical clipping.
        self.assertRegex(lines[-2], r"^… \d+ more lines")

    def test_malformed_snapshot_result_makes_the_board_stale(self) -> None:
        self.worker_run()
        board = self.board()
        board.refresh()
        self.raw = {"result": []}
        board.refresh()
        self.assertIn("herdr", board.stale or "")
        self.assertIsNotNone(board.view)

    def test_board_ignores_non_ascii_digit_keys(self) -> None:
        self.worker_run()
        board = self.board()
        board.refresh()
        for choices in ([], [{"run_id": "r1", "run_file": "x"}]):
            board.choices = choices
            self.assertTrue(board.key("\u00b2"))
            self.assertTrue(board.key("\u0661"))
        self.assertFalse([call for call in self.calls if call[:2] == ("agent", "focus")])

    def test_unresolvable_report_ref_does_not_crash_board(self) -> None:
        path = self.worker_run()
        self.cli("task", "report", str(path), "t1", "~zstack-no-such-user/report.md")
        board = self.board()
        board.refresh()
        self.assertIsNone(board.stale)
        self.assertTrue(any("report file missing" in gap for gap in self.task(board.view, "t1")["data_gaps"]))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.assertEqual(pl.reconcile(SOCKET_A, self.registry, Path(directory.name), "startup")[0][:6], "r1: ok")

    def test_focus_revalidates(self) -> None:
        path = self.worker_run()
        self.assertEqual(pl.focus(SOCKET_A, path, "t1"), "focused t1 at w1:p2")
        self.assertEqual(self.calls[-1], ("agent", "focus", "w1:p2"))
        self.raw = raw_snapshot(("w2:p7", "term_worker", "codex", "sess-worker", None))
        self.assertEqual(pl.focus(SOCKET_A, path, "t1"), "focused t1 at w2:p7")
        self.raw = raw_snapshot(("w1:p2", "term_other", "codex", "sess-worker", None))
        with self.assertRaises(hr.UserError):
            pl.focus(SOCKET_A, path, "t1")
        self.raw = None
        with self.assertRaises(hr.UserError):
            pl.focus(SOCKET_A, path, "coordinator")
        self.assertEqual(len([call for call in self.calls if call[0] == "agent"]), 2)
        # A board key's result stays visible across refreshes until the next key.
        self.raw = BASE
        board = self.board()
        board.refresh()
        board.key("1")
        board.refresh()
        board.draw()
        self.assertIn("focused t1 at w1:p2", board.console.file.getvalue())

    def test_board_loop_exits_and_refreshes_sequentially(self) -> None:
        self.worker_run()
        refreshes: list[float] = []

        def run(keys: bytes, close: bool, interval: float) -> int:
            board = self.board()
            original = board.refresh
            board.refresh = lambda: (refreshes.append(time.monotonic()), original())[1]
            read, write = os.pipe()
            self.addCleanup(os.close, read)
            os.write(write, keys)
            if close:
                os.close(write)
            else:
                self.addCleanup(os.close, write)
            return pl.run_board(board, read, interval)

        self.assertEqual(run(b"q", close=False, interval=60), 0)
        self.assertEqual(run(b"", close=True, interval=60), 0)  # EOF exits.
        refreshes.clear()
        read, write = os.pipe()
        self.addCleanup(os.close, read)
        board = self.board()
        original = board.refresh
        board.refresh = lambda: (refreshes.append(time.monotonic()), original())[1]
        timer = threading.Timer(0.35, os.write, (write, b"q"))
        timer.start()
        self.addCleanup(os.close, write)
        self.assertEqual(pl.run_board(board, read, 0.1), 0)
        timer.join()
        self.assertGreaterEqual(len(refreshes), 3)
        self.assertTrue(all(b - a >= 0.1 for a, b in itertools.pairwise(refreshes)))


class ReconcileTests(Fixture):
    """Event/startup reconcile with a fake Herdr whose metadata calls patch the fake snapshot's pane tokens."""

    def setUp(self) -> None:
        super().setUp()
        directory = tempfile.TemporaryDirectory()  # outside self.root so tree(self.root) covers coordinator files.
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name) / "plugin-state"
        self.calls: list[tuple[str, ...]] = []
        self.snapshots = 0
        self.raw: dict[str, Any] | None = copy.deepcopy(BASE)
        for fake in (
            patch.object(hr, "live_snapshot", self.fake_snapshot),
            patch.object(pl, "herdr", self.fake_herdr),
            patch.object(hr, "herdr", self.fake_herdr),
        ):
            fake.start()
            self.addCleanup(fake.stop)

    def fake_snapshot(self, socket: str) -> dict[str, Any]:
        self.snapshots += 1
        if self.raw is None:
            raise hr.UserError("herdr snapshot failed: server_not_running")
        return hr.normalize_snapshot(self.raw, socket)

    def run_with_worker(self, name: str = "run", run_id: str = "r1") -> Path:
        path = self.make_run(name, run_id)
        self.cli("task", "add", str(path), "t1")
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        return path

    def event(self, name: str, **data: Any) -> list[str]:  # noqa: ANN401
        payload = json.dumps({"event": name.replace(".", "_"), "data": data})
        return pl.reconcile(SOCKET_A, self.registry, self.state, name, payload)

    def observation(self, run_id: str = "r1") -> dict[str, Any]:
        return pl.read_observation(pl.observation_path(self.state, SOCKET_A, run_id))

    def tokens(self, pane: str) -> dict[str, str]:
        rows = self.raw["result"]["snapshot"]["panes"]
        return next(row for row in rows if row["pane_id"] == pane).get("tokens", {})

    def set_raw(self, *panes: tuple[str, str, str | None, str | None, str | None]) -> None:
        """Replace the fake server state, carrying live tokens by terminal like Herdr does on a move."""
        old = {row["terminal_id"]: row.get("tokens") for row in (self.raw or BASE)["result"]["snapshot"]["panes"]}
        self.raw = copy.deepcopy(raw_snapshot(*panes))
        for row in self.raw["result"]["snapshot"]["panes"]:
            if old.get(row["terminal_id"]):
                row["tokens"] = dict(old[row["terminal_id"]])

    def test_malformed_observation_fields_are_rebuilt(self) -> None:
        self.run_with_worker()
        path = pl.observation_path(self.state, SOCKET_A, "r1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 1, "bindings": ["bad"], "labeled": 7}), encoding="utf-8")
        self.assertEqual(self.event("pane.agent_status_changed", pane_id="w1:p2")[0][:6], "r1: ok")
        self.assertEqual(set(self.observation()["bindings"]), {"coordinator", "t1"})

    def test_pane_labeled_by_another_run_is_not_taken_over(self) -> None:
        self.run_with_worker("one", "r1")
        self.run_with_worker("two", "r2")
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        owner = self.tokens("w1:p2")["zstack_run"]
        self.calls.clear()
        for _ in range(2):
            self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.assertEqual(self.tokens("w1:p2")["zstack_run"], owner)
        self.assertFalse([call for call in self.calls if call[:2] == ("pane", "report-metadata")])
        other = "r2" if owner == "r1" else "r1"
        self.assertNotIn("w1:p2", self.observation(other)["labeled"])
        self.assertIn("w1:p2", self.observation(owner)["labeled"])
        hr.registry_path(self.registry, SOCKET_A, owner).unlink()  # an owner deleted without unenroll.
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.assertEqual(self.tokens("w1:p2")["zstack_run"], other)
        self.assertIn("w1:p2", self.observation(other)["labeled"])

    def test_unenroll_clears_labels_then_deletes_the_entry(self) -> None:
        path = self.run_with_worker()
        entry = hr.registry_path(self.registry, SOCKET_A, "r1")
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        labeled, self.raw = self.raw, None
        self.assertIn("snapshot failed", self.cli("unenroll", str(path), code=1))
        self.assertTrue(entry.exists())
        self.raw = labeled
        other = self.root / "other" / "herdr-run.json"
        other.parent.mkdir()
        other.write_bytes(path.read_bytes())
        self.assertIn("enrolled on this endpoint for", self.cli("unenroll", str(other), code=1))
        self.assertTrue(entry.exists())
        result = self.cli("unenroll", str(path))
        self.assertEqual(result["cleared_panes"], ["w1:p1", "w1:p2"])
        self.assertEqual(result["registry_entry"], str(entry))
        self.assertFalse(entry.exists())
        self.assertFalse({"zstack_run", "zstack_role"} & (self.tokens("w1:p1").keys() | self.tokens("w1:p2").keys()))
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.assertNotIn("zstack_run", self.tokens("w1:p2"))
        self.assertEqual(self.cli("unenroll", str(path)), {"run_id": "r1", "registry_entry": None, "cleared_panes": []})

    def test_pane_with_several_bindings_gets_no_labels(self) -> None:
        path = self.run_with_worker()
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.assertEqual(self.tokens("w1:p2")["zstack_task"], "t1")
        self.cli("task", "add", str(path), "t2")
        self.cli("task", "bind", str(path), "t2", "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.assertFalse({"zstack_run", "zstack_task"} & self.tokens("w1:p2").keys())
        self.assertNotIn("w1:p2", self.observation()["labeled"])
        self.assertEqual(self.tokens("w1:p1")["zstack_role"], "coordinator")

    def test_event_targets(self) -> None:
        self.assertIsNone(pl.event_targets("startup", None))
        self.assertIsNone(pl.event_targets("pane.closed", "{bad"))
        moved = {"data": {"previous_pane_id": "w1:p2", "pane": {"pane_id": "w2:p1"}, "workspace_id": "w1"}}
        self.assertEqual(pl.event_targets("pane.moved", json.dumps(moved)), ({"w1:p2", "w2:p1"}, set()))
        closed = {"data": {"workspace_id": "w2", "workspace": {"workspace_id": "w2"}}}
        self.assertEqual(pl.event_targets("workspace.closed", json.dumps(closed)), (set(), {"w2"}))

    def test_identity_drift_refuses_actions_and_preserves_board_and_observation(self) -> None:
        path = self.run_with_worker()
        board = pl.Board(SOCKET_A, "w1:p2", self.registry, io.StringIO(), self.state)
        board.refresh()
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        good_view, good_observation = board.view, self.observation()
        record = path.read_bytes()
        data = json.loads(record)
        for drift in ({"run_id": "never-enrolled"}, {"endpoint": {"socket": SOCKET_B, "session": None}}):
            with self.subTest(drift=drift):
                hr.atomic_write(path, {**data, **drift})
                self.calls.clear()
                resolution = pl.resolve_run(SOCKET_A, "w1:p2", self.registry, self.fake_snapshot(SOCKET_A))
                self.assertNotIn("run_file", resolution)
                self.assertIn("registry entry", resolution["error"])
                board.refresh()
                self.assertIs(board.view, good_view)
                self.assertIn("registry entry", board.stale)
                self.assertIn("showing last good data", render(board.view, board.last_ok, board.stale))
                board.key("1")
                self.assertIn("focus refused", board.notice)
                with self.assertRaisesRegex(hr.UserError, "registry entry"):
                    pl.focus(SOCKET_A, path, "t1")
                self.assertIn("registry entry", pl.reconcile(SOCKET_A, self.registry, self.state, "startup")[0])
                stale = self.observation()
                for key in ("bindings", "labeled", "last_good_at"):
                    self.assertEqual(stale[key], good_observation[key])
                self.assertEqual(self.calls, [])
        path.write_text("{corrupt", encoding="utf-8")
        board.refresh()
        self.assertIs(board.view, good_view)
        self.assertIn("run_file", board.stale)
        path.write_bytes(record)
        board.refresh()
        self.assertIsNone(board.stale)
        # Reenrolling the same file as another identity must not switch a selected board.
        hr.atomic_write(path, {**data, "run_id": "replacement"})
        hr.enroll(path, self.registry)
        self.calls.clear()
        board.refresh()
        self.assertEqual(board.view["run_id"], "r1")
        board.key("1")
        self.assertIn("focus refused", board.notice)
        self.assertEqual(self.calls, [])

    def test_board_clears_invalid_bindings_after_missed_hook(self) -> None:
        self.run_with_worker()
        board = pl.Board(SOCKET_A, "w1:p2", self.registry, io.StringIO())
        board.refresh()
        self.set_raw(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w1:p2", "term_worker", "codex", "sess-new", None),
            ("w1:p3", "term_other", "codex", "sess-other", None),
        )
        self.tokens("w1:p2")["other_tok"] = "keep-me"
        self.raw["result"]["snapshot"]["panes"][2]["tokens"] = {"zstack_run": "another-run", "zstack_task": "other"}
        self.calls.clear()
        board.refresh()  # No hook delivered the changed session.
        self.assertEqual(self.tokens("w1:p2"), {"other_tok": "keep-me"})
        self.assertEqual(self.tokens("w1:p3"), {"zstack_run": "another-run", "zstack_task": "other"})
        self.assertEqual(self.task(board.view, "t1")["binding_check"]["status"], "occupant changed")
        [clear] = self.calls
        self.assertEqual(clear[:5], ("pane", "report-metadata", "w1:p2", "--source", pl.SOURCE))
        self.assertEqual(sorted(clear[i + 1] for i, arg in enumerate(clear) if arg == "--clear-token"), list(hr.TOKENS))
        board.refresh()
        self.assertEqual(self.calls, [clear])

    def test_identifier_ceiling_prevents_normalized_token_aliases(self) -> None:
        boundary, too_long = "r" * 80, "r" * 81
        path = self.make_run("limit", boundary)
        self.cli("task", "add", str(path), boundary)
        self.cli("task", "bind", str(path), boundary, "--pane", "w1:p2", "--snapshot", self.snapshot_file(BASE))
        board = pl.Board(SOCKET_A, "w1:p2", self.registry, io.StringIO())
        board.refresh()
        board.refresh()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.tokens("w1:p2")["zstack_task"], boundary)
        self.assertTrue(
            all(len(value) <= 80 for row in self.raw["result"]["snapshot"]["panes"] for value in row["tokens"].values())
        )
        bad = self.root / "too-long.json"
        self.assertIn("run id", self.cli("init", str(bad), "--run-id", too_long, "--socket", SOCKET_A, code=1))
        self.assertFalse(bad.exists())
        before = path.read_bytes()
        self.assertIn("task id", self.cli("task", "add", str(path), too_long, code=1))
        self.assertEqual(path.read_bytes(), before)
        data = json.loads(before)
        hr.atomic_write(path, {**data, "run_id": too_long})
        self.assertIsNone(hr.read_run(path)[0])
        data["tasks"][0]["id"] = too_long
        hr.atomic_write(path, data)
        view = self.inspect(path)
        self.assertTrue(view["tasks"][0]["data_gaps"])
        self.assertEqual(set(pl.label_tokens(view)), {"w1:p1"})
        orch, store_dir = OrchAndReadOnlyTests.orch_run(self)  # type: ignore[arg-type]
        from store import Store

        store = Store(store_dir)
        try:
            store.unit_set("u1", "  " + "p" * 81 + "\x01  ")
        finally:
            store.close()
        orch_board = pl.Board(SOCKET_A, "w1:p2", self.registry, io.StringIO())
        self.raw = copy.deepcopy(BASE)  # drop the first run's labels; another run's labels are never taken over.
        self.calls.clear()
        orch_board.refresh()
        orch_board.refresh()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.tokens("w1:p2")["zstack_phase"], "p" * 80)
        store = Store(store_dir)
        try:
            store.unit_add(too_long, "main")
        finally:
            store.close()
        before_store = tree(store_dir)
        view = self.inspect(orch)
        self.assertFalse(view["sources"]["orch_store"]["ok"])
        self.assertTrue(any("task id" in gap for gap in view["data_gaps"]))
        self.assertNotIn(too_long, [task["id"] for task in view["tasks"]])
        self.assertEqual(tree(store_dir), before_store)

    def test_coordinator_identifier_is_reserved_in_records_inputs_and_orch(self) -> None:
        path = self.run_with_worker("plain")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["tasks"][0]["id"] = "coordinator"
        hr.atomic_write(path, data)
        view = self.inspect(path)
        self.assertEqual(pl.observed_bindings(view, self.fake_snapshot(SOCKET_A))["coordinator"]["pane_id"], "w1:p1")
        self.assertNotIn("coordinator", [task["id"] for task in view["tasks"]])
        self.assertIn("reserved", view["tasks"][0]["data_gaps"][0])
        data["tasks"][0]["id"] = "t1"
        hr.atomic_write(path, data)
        self.assertIn("reserved", self.cli("task", "add", str(path), "coordinator", code=1))
        orch, store_dir = OrchAndReadOnlyTests.orch_run(self)  # type: ignore[arg-type]
        from store import Store

        store = Store(store_dir)
        try:
            store.unit_add("coordinator", "main")
        finally:
            store.close()
        before_store = tree(store_dir)
        view = self.inspect(orch)
        self.assertFalse(view["sources"]["orch_store"]["ok"])
        self.assertTrue(any("reserved" in gap for gap in view["data_gaps"]))
        self.assertNotIn("coordinator", [task["id"] for task in view["tasks"]])
        self.assertEqual(pl.observed_bindings(view, self.fake_snapshot(SOCKET_A))["coordinator"]["pane_id"], "w1:p1")
        self.assertEqual(tree(store_dir), before_store)

    def test_duplicate_events_same_end_state(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        self.assertEqual(self.event("pane.agent_status_changed", pane_id="w1:p2"), ["r1: ok (set w1:p1, set w1:p2)"])
        first = self.observation()
        self.assertEqual(self.event("pane.agent_status_changed", pane_id="w1:p2"), ["r1: ok"])
        second = self.observation()
        self.assertEqual(len(self.calls), 2)  # live tokens already match: the duplicate wrote no labels.
        for item in (first, second):
            del item["reconciled_at"], item["last_good_at"]
        self.assertEqual(first, second)
        self.assertEqual(
            second["bindings"]["t1"], {"status": "ok", "pane_id": "w1:p2", "workspace_id": "w1", "agent_status": "idle"}
        )
        self.assertEqual(second["labeled"], ["w1:p1", "w1:p2"])
        self.assertEqual(second["trigger"], {"event": "pane.agent_status_changed", "targets": ["w1:p2"]})
        self.assertIsNone(second["stale"])

    def test_unrelated_events_write_nothing(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.assertEqual(
            pl.reconcile(SOCKET_A, self.registry, self.state, "startup"), ["startup: no enrolled run affected"]
        )
        self.run_with_worker()
        before = tree(self.root)
        self.assertEqual(
            self.event("pane.closed", pane_id="w7:p1", workspace_id="w1"), ["pane.closed: no enrolled run affected"]
        )
        self.assertEqual(
            self.event("workspace.closed", workspace_id="w9"), ["workspace.closed: no enrolled run affected"]
        )
        self.assertFalse(self.state.exists())
        self.assertEqual((self.snapshots, self.calls), (0, []))
        self.assertEqual(tree(self.root), before)

    def test_stale_observation_recovers_from_snapshot(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        path = pl.observation_path(self.state, SOCKET_A, "r1")
        path.parent.mkdir(parents=True)
        path.write_text("{corrupt", encoding="utf-8")
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.assertEqual(self.observation()["bindings"]["t1"]["status"], "ok")
        stale = {
            **self.observation(),
            "bindings": {"t1": {"status": "pane missing", "pane_id": "w9:p9"}},
            "labeled": ["w9:p9"],
        }
        hr.atomic_write(path, stale)
        self.calls.clear()
        self.assertEqual(self.event("pane.closed", pane_id="w9:p9"), ["r1: ok"])  # old pane id still routes here.
        self.assertEqual(self.observation()["bindings"]["t1"]["pane_id"], "w1:p2")
        self.assertEqual(self.observation()["labeled"], ["w1:p1", "w1:p2"])
        self.assertEqual(self.calls, [])

    def test_move_close_and_workspace_close(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.set_raw(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w2:p7", "term_worker", "codex", "sess-worker", None),
        )
        self.event("pane.moved", previous_pane_id="w1:p2", pane={"pane_id": "w2:p7"})
        moved = self.observation()["bindings"]["t1"]
        self.assertEqual((moved["status"], moved["pane_id"], moved["workspace_id"]), ("moved", "w2:p7", "w2"))
        self.assertEqual(self.tokens("w2:p7")["zstack_task"], "t1")  # carried by the move; not resent.
        self.assertEqual(len(self.calls), 2)
        self.set_raw(("w1:p1", "term_coord", "claude", "sess-coord", None))
        self.assertEqual(self.event("workspace.closed", workspace_id="w2"), ["r1: ok"])
        observation = self.observation()
        self.assertEqual(
            observation["bindings"]["t1"],
            {"status": "pane missing", "pane_id": "w1:p2", "workspace_id": None, "agent_status": None},
        )
        self.assertEqual(observation["labeled"], ["w1:p1"])

    def test_clears_only_our_tokens_for_this_run(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.set_raw(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w1:p2", "term_worker", "codex", "sess-new", None),  # same terminal, new session: occupant changed.
            ("w1:p3", "term_other", "codex", "sess-o", None),
        )
        self.tokens("w1:p2")["other_tok"] = "keep-me"
        self.raw["result"]["snapshot"]["panes"][2]["tokens"] = {"zstack_run": "someone-else", "zstack_role": "worker"}
        self.calls.clear()
        self.assertEqual(self.event("pane.agent_status_changed", pane_id="w1:p2"), ["r1: ok (clear w1:p2)"])
        [call] = self.calls
        self.assertEqual(call[:5], ("pane", "report-metadata", "w1:p2", "--source", pl.SOURCE))
        self.assertEqual({arg for arg in call if arg.startswith("--")}, {"--source", "--clear-token"})
        self.assertEqual(sorted(call[i + 1] for i, arg in enumerate(call) if arg == "--clear-token"), list(hr.TOKENS))
        self.assertEqual(self.tokens("w1:p2"), {"other_tok": "keep-me"})
        self.assertEqual(self.tokens("w1:p3"), {"zstack_run": "someone-else", "zstack_role": "worker"})
        self.assertEqual(self.observation()["bindings"]["t1"]["status"], "occupant changed")
        self.assertEqual(self.observation()["labeled"], ["w1:p1"])

    def test_relabelled_pane_drops_unused_keys(self) -> None:
        path = self.run_with_worker()
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.assertEqual(self.tokens("w1:p2")["zstack_task"], "t1")
        self.set_raw(
            ("w1:p1", "term_coord", "claude", "sess-coord", None),
            ("w1:p2", "term_worker", "codex", "sess-worker", "worker"),
            ("w1:p3", "term_new", "codex", "sess-new", None),
        )
        snapshot = self.snapshot_file(self.raw, "relabel.json")
        self.cli("coordinator", "bind", str(path), "--pane", "w1:p2", "--snapshot", snapshot)
        self.cli("task", "bind", str(path), "t1", "--pane", "w1:p3", "--snapshot", snapshot)
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.assertEqual(self.tokens("w1:p2"), {"zstack_run": "r1", "zstack_role": "coordinator"})
        self.assertEqual(self.tokens("w1:p3")["zstack_task"], "t1")
        self.calls.clear()
        self.assertEqual(pl.reconcile(SOCKET_A, self.registry, self.state, "startup"), ["r1: ok"])
        self.assertEqual(self.calls, [])

    def test_failed_reads_keep_state_and_labels(self) -> None:
        self.raw = copy.deepcopy(BASE)
        path = self.run_with_worker()
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        good = self.observation()
        self.calls.clear()
        self.raw = None  # Herdr unreachable.
        self.assertIn("server_not_running", pl.reconcile(SOCKET_A, self.registry, self.state, "startup")[0])
        stale = self.observation()
        self.assertIn("herdr", stale["stale"])
        self.assertEqual(
            (stale["bindings"], stale["labeled"], stale["last_good_at"]),
            (good["bindings"], good["labeled"], good["last_good_at"]),
        )
        self.raw = copy.deepcopy(BASE)
        self.raw["result"]["snapshot"]["panes"] = self.raw["result"]["snapshot"]["panes"][:1]  # worker gone...
        record = path.read_bytes()
        path.write_text("{corrupt", encoding="utf-8")  # ...but the run file is unreadable: no label changes.
        self.assertIn("run_file", pl.reconcile(SOCKET_A, self.registry, self.state, "startup")[0])
        self.assertEqual(self.observation()["bindings"], good["bindings"])
        self.assertEqual(self.calls, [])
        path.write_bytes(record)
        self.assertEqual(pl.reconcile(SOCKET_A, self.registry, self.state, "startup"), ["r1: ok (set w1:p1)"])
        self.assertEqual(self.observation()["bindings"]["t1"]["status"], "pane missing")

    def test_lock_held_skips_without_reading(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        directory = self.state / hr.endpoint_key(SOCKET_A)
        directory.mkdir(parents=True)
        with (directory / ".reconcile.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn("skipped", pl.reconcile(SOCKET_A, self.registry, self.state, "startup")[0])
        self.assertEqual((self.snapshots, self.calls, self.observation()), (0, [], {}))
        self.assertEqual(
            pl.reconcile(SOCKET_A, self.registry, self.state, "startup")[0], "r1: ok (set w1:p1, set w1:p2)"
        )

    def test_two_processes_do_not_double_act(self) -> None:
        self.run_with_worker()
        snapshot, calls = Path(self.snapshot_file(BASE)), self.root / "calls.log"
        fake = self.root / "fake-herdr"
        script = 'case "$1" in api) sleep 1; cat "$FAKE_SNAPSHOT";; *) echo "$*" >> "$FAKE_CALLS"; echo "{}";; esac'
        fake.write_text(f"#!/bin/sh\n{script}\n")
        fake.chmod(0o755)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HERDR_BIN_PATH": str(fake),
            "HERDR_SOCKET_PATH": SOCKET_A,
            "HERDR_PLUGIN_STATE_DIR": str(self.state),
            "HERDR_PLUGIN_EVENT": "startup",
            "ZSTACK_HERDR_REGISTRY": str(self.registry),
            "FAKE_SNAPSHOT": str(snapshot),
            "FAKE_CALLS": str(calls),
        }
        before = tree(self.root)
        argv = [sys.executable, "-I", str(ROOT / "integrations/herdr/plugin.py"), "reconcile"]
        processes = [subprocess.Popen(argv, env=environment, stdout=subprocess.PIPE, text=True) for _ in range(2)]  # noqa: S603
        outputs = sorted(process.communicate(timeout=30)[0] for process in processes)
        self.assertEqual([process.returncode for process in processes], [0, 0])
        self.assertEqual(
            outputs, ["r1: ok (set w1:p1, set w1:p2)\n", "startup: skipped, another reconcile holds the lock\n"]
        )
        self.assertEqual(len(calls.read_text().splitlines()), 2)
        self.assertEqual(self.observation()["bindings"]["t1"]["status"], "ok")
        calls.unlink()
        self.assertEqual(tree(self.root), before)

    def test_reconcile_never_writes_coordinator_records(self) -> None:
        self.raw = copy.deepcopy(BASE)
        orch = OrchAndReadOnlyTests.orch_run(self)  # type: ignore[arg-type]
        self.run_with_worker("plain", "plain")
        before = tree(self.root)
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        self.raw = None
        pl.reconcile(SOCKET_A, self.registry, self.state, "startup")
        self.assertEqual(tree(self.root), before)
        self.assertFalse((orch[1] / ".orch.lock").exists())
        self.assertEqual(
            sorted(path.name for path in (self.state / hr.endpoint_key(SOCKET_A)).iterdir()),
            [".reconcile.lock", "orch-run.json", "plain.json"],
        )

    def test_board_shows_last_reconcile(self) -> None:
        self.raw = copy.deepcopy(BASE)
        self.run_with_worker()
        board = pl.Board(SOCKET_A, "w1:p2", self.registry, io.StringIO(), self.state)
        board.refresh()
        self.assertIn("hooks none recorded", render(board.view, board.last_ok, hook=board.hook))
        self.event("pane.agent_status_changed", pane_id="w1:p2")
        board.refresh()
        text = render(board.view, board.last_ok, hook=board.hook)
        self.assertRegex(text, r"hooks \d\d:\d\d:\d\d via pane.agent_status_changed")
        self.assertNotIn("hooks", render(board.view, board.last_ok))  # no state dir: line omitted.


class PackagingTests(unittest.TestCase):
    """The Herdr manifest resolves from its own directory; the native package never needs it."""

    def test_manifest_structure(self) -> None:
        manifest = ROOT / "herdr-plugin.toml"
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        for field in ("id", "name", "version", "min_herdr_version", "description", "platforms"):
            self.assertTrue(data.get(field), field)
        # Reconcile locks with fcntl, so the manifest must stay POSIX-only.
        self.assertIs(pl.fcntl, fcntl)
        self.assertTrue(data["platforms"])
        self.assertLessEqual(set(data["platforms"]), {"linux", "macos"})
        for kind in ("actions", "panes"):
            ids = [entry["id"] for entry in data[kind]]
            self.assertEqual(len(ids), len(set(ids)), kind)
            self.assertFalse([entry_id for entry_id in ids if "." in entry_id], kind)
        commands = [entry["command"] for kind in ("actions", "panes", "startup", "events") for entry in data[kind]]
        for command in commands:
            script = command[command.index("--script") + 1]
            self.assertFalse(Path(script).is_absolute(), script)
            self.assertTrue((manifest.parent / script).is_file(), script)
        self.assertEqual(hr.ORCH_DIR, manifest.parent / "skills/z-mode/scripts/orch")
        self.assertTrue((hr.ORCH_DIR / "store.py").is_file())

    def test_native_package_does_not_need_herdr_plugin(self) -> None:
        packaging = load("package_plugin", ROOT / "scripts/package_plugin.py")
        self.assertFalse([name for name in packaging.RESOURCES if name in ("integrations", "herdr-plugin.toml")])
        referencing = [
            str(path.relative_to(ROOT))
            for name in packaging.RESOURCES
            for path in ([ROOT / name] if (ROOT / name).is_file() else (ROOT / name).rglob("*"))
            if path.is_file()
            and not packaging.excluded(path.relative_to(ROOT))
            and b"integrations/herdr" in path.read_bytes()
        ]
        self.assertEqual(referencing, [])


if __name__ == "__main__":
    unittest.main()
