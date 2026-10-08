#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Herdr plugin entrypoints for enrolled zstack runs: a terminal board, focus actions, and reconcile hooks.

Read-only toward coordinator records: the board, actions, and hooks read `herdr-run.json`, orch stores,
and Herdr snapshots, and never write them. The only Herdr writes are display metadata tokens
under one source, pane focus when a focus action or key is chosen, and the board pane itself.
Hooks write only plugin-owned observations under HERDR_PLUGIN_STATE_DIR.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import select
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from collections.abc import Collection

sys.path.insert(0, str(Path(__file__).resolve().parent))  # works under `python -I` too.
import herdr_run as hr
from herdr_run import SOURCE, clear_flags, herdr

REFRESH_SECONDS = 5
FOCUSABLE = ("ok", "moved")
SELECT = "123456789abdefghijklmnopstuvwxyz"  # one key per entry; skips c, q, r. ASCII only.
KEYS = "q quit · r refresh · 1-9/a-z focus worker · c focus coordinator"
CONTROLS = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")  # terminal controls from run/snapshot text.
OBSERVATION_VERSION = 1


# --- Herdr calls ------------------------------------------------------------


def endpoint() -> str:
    socket = os.environ.get("HERDR_SOCKET_PATH")
    if not socket:
        raise hr.UserError("HERDR_SOCKET_PATH is not set; run this from a Herdr plugin entrypoint")
    return socket


def context_pane() -> str | None:
    """The caller's pane: plugin context first (for panes it is the launch target), then HERDR_PANE_ID."""
    try:
        pane = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}").get("focused_pane_id")
    except (ValueError, AttributeError):
        pane = None
    return pane or os.environ.get("HERDR_PANE_ID")


def snapshot_or_error(socket: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return hr.live_snapshot(socket), None
    except hr.UserError as error:
        return None, str(error)


# --- Run resolution ---------------------------------------------------------


def pane_roles(view: dict[str, Any], pane: str) -> list[str]:
    """Roles the pane holds in this run, counting only validated (ok/moved) bindings."""
    roles = []
    entries = [("coordinator", view.get("coordinator") or {}), *((task["id"], task) for task in view.get("tasks", []))]
    for role, item in entries:
        check = item.get("binding_check") or {}
        if check.get("status") in FOCUSABLE and check.get("observed_pane_id") == pane:
            roles.append(role)
    return roles


def enrollment(socket: str, root: Path, run_file: Path, run_id: str | None = None) -> dict[str, Any]:
    """Re-read the enrollment for a file, retaining a selected identity when supplied."""
    for entry in hr.enrolled_runs(socket, root):
        if entry.get("run_file") == str(run_file.absolute()) and (run_id is None or entry["run_id"] == run_id):
            return entry
    return {
        "run_file": str(run_file),
        "run_id": run_id,
        "endpoint": {"socket": socket},
        "data_gaps": ["run record no longer matches an enrolled registry entry on this endpoint"],
    }


def inspect_enrolled(
    entry: dict[str, Any], snapshot: dict[str, Any] | None, error: str | None = None
) -> dict[str, Any]:
    """Inspect the record and reject enrollment drift, including changes after the registry read."""
    view = hr.inspect_run(Path(entry["run_file"]), snapshot, error)
    gaps = list(entry.get("data_gaps") or [])
    if view["run_id"] is not None and (
        view["run_id"] != entry["run_id"]
        or hr.endpoint_socket(view["endpoint"]["socket"]) != hr.endpoint_socket(entry["endpoint"]["socket"])
    ):
        gaps.append("run record no longer matches its registry entry")
    view["sources"]["registry"] = {"ok": not gaps, "read_at": hr.now(), "error": "; ".join(gaps) or None}
    view["data_gaps"] += list(dict.fromkeys(gaps))
    return view


def resolve_run(socket: str, pane: str | None, root: Path, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Pick the one enrolled run that binds `pane`; otherwise explain why not. Never guesses."""
    entries = [entry for entry in hr.enrolled_runs(socket, root) if entry.get("run_file")]
    if not entries:
        return {"error": "no enrolled run on this Herdr endpoint", "choices": []}
    if pane is None:
        return {"error": "invocation context has no pane", "choices": []}
    if snapshot is None:
        return {"error": f"cannot validate pane {pane}: Herdr snapshot unavailable", "choices": []}
    matches, errors = [], []
    for entry in entries:
        view = inspect_enrolled(entry, snapshot)
        if not view["sources"]["registry"]["ok"]:
            errors.append(f"{entry['run_id']}: {view['sources']['registry']['error']}")
            continue
        roles = pane_roles(view, pane)
        if roles:
            matches.append({"run_id": entry["run_id"], "run_file": entry["run_file"], "roles": roles, "view": view})
    if len(matches) == 1:
        return matches[0]
    if not matches:
        detail = "; " + "; ".join(errors) if errors else ""
        return {"error": f"no enrolled run for pane {pane}{detail}", "choices": []}
    return {"error": f"several enrolled runs bind pane {pane}", "choices": matches}


# --- Metadata labels --------------------------------------------------------


def metadata_argv(pane: str, tokens: dict[str, str]) -> list[str]:
    """Token-only metadata under our own source; never titles, agent names, state labels, or clears."""
    argv = ["pane", "report-metadata", pane, "--source", SOURCE]
    for name, value in sorted(tokens.items()):
        argv += ["--token", f"{name}={value}"]
    return argv


def label_tokens(view: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Pane id -> tokens for every ok/moved binding in the view; a pane holding several bindings gets none."""
    labels: dict[str, dict[str, str]] = {}
    ambiguous: set[str] = set()
    check = (view.get("coordinator") or {}).get("binding_check") or {}
    if check.get("status") in FOCUSABLE:
        labels[check["observed_pane_id"]] = {"zstack_run": view["run_id"], "zstack_role": "coordinator"}
    for task in view.get("tasks", []):
        check = task.get("binding_check") or {}
        if check.get("status") not in FOCUSABLE:
            continue
        lifecycle = task.get("lifecycle") or {}
        phase = lifecycle.get("orch_state") or task.get("acceptance") or "not recorded"
        phase = "".join(char for char in phase if char.isprintable()).strip()[:80].rstrip() or "not recorded"
        if check["observed_pane_id"] in labels:
            ambiguous.add(check["observed_pane_id"])
        labels[check["observed_pane_id"]] = {
            "zstack_run": view["run_id"],
            "zstack_role": "worker",
            "zstack_task": task["id"],
            "zstack_phase": phase,
        }
    return {pane: tokens for pane, tokens in labels.items() if pane not in ambiguous}


# --- Focus ------------------------------------------------------------------


def focus(socket: str, run_file: Path, target: str, root: Path | None = None, run_id: str | None = None) -> str:
    """Re-snapshot, validate `target` ("coordinator" or a task id), then focus its agent pane."""
    snapshot, error = snapshot_or_error(socket)
    if snapshot is None:
        raise hr.UserError(f"not focusing: {error}")
    view = inspect_enrolled(enrollment(socket, root or hr.registry_root(), run_file, run_id), snapshot)
    if not view["sources"]["registry"]["ok"]:
        raise hr.UserError("not focusing: " + view["sources"]["registry"]["error"])
    if view["run_id"] is None:
        raise hr.UserError("not focusing: run record unreadable: " + "; ".join(view["data_gaps"]))
    if target == "coordinator":
        item = {"id": "coordinator", **view["coordinator"]}
    else:
        item = next((task for task in view["tasks"] if task["id"] == target), None)
        if item is None:
            raise hr.UserError(f"task {target} not in run {view['run_id']}")
    resolved = hr.resolve_focus_target(item)
    if not resolved["ok"]:
        raise hr.UserError(resolved["error"])
    try:
        herdr("agent", "focus", resolved["pane_id"])
    except hr.UserError as error:  # Herdr 0.9.3 has no focus-by-pane-id for panes without an agent.
        raise hr.UserError(f"{error} (Herdr focuses a pane by id only while it hosts an agent)") from error
    return f"focused {target} at {resolved['pane_id']}"


# --- Reconcile (event and startup hooks) ------------------------------------


def state_root() -> Path | None:
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    return Path(state) if state else None


def observation_path(state: Path, socket: str, run_id: str) -> Path:
    return state / hr.endpoint_key(socket) / f"{run_id}.json"


def read_observation(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != OBSERVATION_VERSION:
        return {}
    if not isinstance(data.get("bindings"), dict):
        data["bindings"] = {}
    labeled = data.get("labeled")
    data["labeled"] = [pane for pane in labeled if isinstance(pane, str)] if isinstance(labeled, list) else []
    return data


def event_targets(event: str, payload: str | None) -> tuple[set[str], set[str]] | None:
    """(pane ids, workspace ids) an event names; None means reconcile every run (startup, manual, unparseable)."""
    if event in ("startup", "manual"):
        return None
    try:
        data = json.loads(payload or "")["data"]
        panes = {data.get("pane_id"), data.get("previous_pane_id"), (data.get("pane") or {}).get("pane_id")}
        workspace = data.get("workspace_id") if event == "workspace.closed" else None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    targets = {pane for pane in panes if isinstance(pane, str)}, {workspace} if isinstance(workspace, str) else set()
    return targets if any(targets) else None


def run_targets(run: dict[str, Any] | None, observation: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Pane and workspace ids this run's bindings and last observation know about."""
    bindings = [run["coordinator"]["binding"], *(task["binding"] for task in run["tasks"])] if run else []
    seen = [item for item in (observation.get("bindings") or {}).values() if isinstance(item, dict)]
    panes = {binding["pane_id"] for binding in bindings if binding} | {item.get("pane_id") for item in seen}
    panes |= set(observation.get("labeled") or [])
    return panes - {None}, {item.get("workspace_id") for item in seen} - {None}


def observed_bindings(view: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    workspaces = {pane["pane_id"]: pane.get("workspace_id") for pane in snapshot["panes"]}
    observed = {}
    for role, item in [("coordinator", view["coordinator"]), *((task["id"], task) for task in view["tasks"])]:
        check = item.get("binding_check") or {}
        pane = check.get("observed_pane_id") or (item.get("binding") or {}).get("pane_id")
        observed[role] = {
            "status": check.get("status"),
            "pane_id": pane,
            "workspace_id": workspaces.get(pane),
            "agent_status": check.get("agent_status"),
        }
    return observed


def sync_labels(
    view: dict[str, Any], snapshot: dict[str, Any], enrolled: Collection[str]
) -> tuple[list[str], list[str], list[str]]:
    """Make our tokens match validated bindings, compared against live pane tokens so repeats are no-ops.

    Sets tokens on ok/moved panes where they differ, clearing our keys their role no longer uses; clears our
    keys from panes still carrying this run's `zstack_run` that no longer hold a validated binding. Panes labeled
    by another run in `enrolled` (this endpoint's run ids) are left alone; labels of unenrolled runs are replaced.
    Returns (labeled panes, actions, errors).
    """
    desired = label_tokens(view)
    live = {pane["pane_id"]: pane.get("tokens") or {} for pane in snapshot["panes"]}
    plan, shared = [], set()
    for pane, tokens in sorted(desired.items()):
        current = live.get(pane, {})
        if current.get("zstack_run") not in (None, view["run_id"]) and current["zstack_run"] in enrolled:
            shared.add(pane)  # another enrolled run labeled it first; overwriting would flap between runs.
            continue
        unused = clear_flags(current.keys() - tokens.keys())
        if unused or any(current.get(name) != value for name, value in tokens.items()):
            plan.append((pane, "set", metadata_argv(pane, tokens) + unused))
    plan += [
        (pane, "clear", ["pane", "report-metadata", pane, "--source", SOURCE, *clear_flags(tokens)])
        for pane, tokens in sorted(live.items())
        if pane not in desired and tokens.get("zstack_run") == view["run_id"]
    ]
    labeled, actions, errors = set(desired) - shared, [], []
    for pane, verb, argv in plan:
        error = try_herdr(argv)
        if error is None:
            actions.append(f"{verb} {pane}")
        else:
            errors.append(f"{verb} {pane}: {error}")
            labeled ^= {pane}  # a failed set leaves the pane unlabeled; a failed clear leaves it labeled.
    return sorted(labeled), actions, errors


def try_herdr(argv: list[str]) -> str | None:
    try:
        herdr(*argv)
    except hr.UserError as error:
        return str(error)
    return None


def reconcile_run(
    socket: str,
    entry: dict[str, Any],
    path: Path,
    snapshot: dict[str, Any] | None,
    error: str | None,
    trigger: dict[str, Any],
    enrolled: Collection[str],
) -> str:
    """Inspect one run against the shared snapshot and rewrite its observation; sources that fail keep last state."""
    old = read_observation(path)
    view = inspect_enrolled(entry, snapshot, error)
    failures = [
        f"{name}: {source.get('error') or '; '.join(view['data_gaps']) or 'read failed'}"
        for name, source in view["sources"].items()
        if not source["ok"]
    ]
    stamp = hr.now()
    observation = {
        "version": OBSERVATION_VERSION,
        "run_id": entry["run_id"],
        "endpoint": hr.endpoint_socket(socket),
        "reconciled_at": stamp,
        "trigger": trigger,
        "last_good_at": old.get("last_good_at"),
        "stale": "; ".join(failures) or None,
        "bindings": old.get("bindings") or {},
        "labeled": old.get("labeled") or [],
    }
    actions: list[str] = []
    if not failures:  # labels change only after every source read succeeded.
        labeled, actions, errors = sync_labels(view, snapshot, enrolled)
        observation |= {"last_good_at": stamp, "bindings": observed_bindings(view, snapshot), "labeled": labeled}
        observation["stale"] = "; ".join(errors) or None
    hr.atomic_write(path, observation)
    return f"{entry['run_id']}: {observation['stale'] or 'ok'}" + (f" ({', '.join(actions)})" if actions else "")


def reconcile(socket: str, root: Path, state: Path, event: str, payload: str | None = None) -> list[str]:
    """Hooks are triggers only: one snapshot plus inspect_run per affected enrolled run on this endpoint.

    Writes only plugin-owned observations and our own metadata tokens. Never writes run files, the
    registry, or orch stores; never prompts, starts, or resends to agents; never records acceptance.
    Events naming no known pane or workspace of an enrolled run cause no reads of Herdr and no writes.
    """
    targets = event_targets(event, payload)
    jobs, entries = [], hr.enrolled_runs(socket, root)
    for entry in entries:
        if not entry.get("run_file"):
            continue
        path = observation_path(state, socket, entry["run_id"])
        if targets is not None:
            panes, workspaces = run_targets(hr.read_run(Path(entry["run_file"]))[0], read_observation(path))
            if not (panes & targets[0] or workspaces & targets[1]):
                continue
        jobs.append((entry, path))
    if not jobs:
        return [f"{event}: no enrolled run affected"]
    trigger = {"event": event, "targets": sorted(set().union(*targets)) if targets else []}
    directory = state / hr.endpoint_key(socket)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".reconcile.lock").open("a") as lock:
        try:  # ponytail: skip-if-held; the next event or the board's 5 s refresh catches what this one misses.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return [f"{event}: skipped, another reconcile holds the lock"]
        snapshot, error = snapshot_or_error(socket)
        enrolled = {entry.get("run_id") for entry in entries}
        return [reconcile_run(socket, entry, path, snapshot, error, trigger, enrolled) for entry, path in jobs]


# --- Board rendering --------------------------------------------------------


def clock(stamp: str | None) -> str:
    return stamp[11:19] if stamp and len(stamp) >= 19 else "never"


def worker_line(task: dict[str, Any]) -> str:
    binding, check = task.get("binding") or {}, task.get("binding_check") or {}
    if not binding:
        return f"unbound ({check.get('status', 'unchecked')})"
    name = check.get("agent_name") or binding.get("agent_name")
    who = " ".join(part for part in (binding.get("agent") or "shell", f'"{name}"' if name else "") if part)
    pane = check.get("observed_pane_id") or binding["pane_id"]
    moved = f", moved from {binding['pane_id']}" if check.get("status") == "moved" else ""
    detail = f": {check['detail']}" if check.get("detail") else ""
    return f"{who} @ {pane} (binding {check.get('status', 'unchecked')}{moved}{detail})"


def report_line(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "none registered"
    present = sum(item["exists"] is True for item in reports)
    missing = [item["ref"] for item in reports if item["exists"] is False]
    remote = sum(item["exists"] is None for item in reports)
    text = f"{present}/{len(reports)} present"
    if remote:
        text += f", {remote} remote"
    if missing:
        text += " · missing " + ", ".join(missing)
    return text


def evidence_line(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "none recorded"
    latest = next((item["revision"] for item in reversed(evidence) if item.get("revision")), None)
    return f"{len(evidence)} · latest revision {latest[:12] if latest else 'not recorded'}"


def lifecycle_line(task: dict[str, Any]) -> str:
    lifecycle = task.get("lifecycle") or {}
    parts = [f"observed {lifecycle.get('observed') or 'unknown'}"]
    if "orch_state" in lifecycle:
        parts += [f"orch {lifecycle.get('orch_state') or '-'}", f"reported {lifecycle.get('reported_status') or '-'}"]
    return " · ".join(parts)


def select_key(index: int) -> str:
    return SELECT[index] if index < len(SELECT) else "-"


def render(
    view: dict[str, Any] | None,
    last_ok: dict[str, str],
    stale: str | None = None,
    message: str | None = None,
    choices: list[dict[str, Any]] | None = None,
    hook: dict[str, Any] | None = None,
) -> str:
    """Pure text board for one inspection view (or a choose-run / no-run screen)."""
    lines = [f"zstack board · {KEYS}"]
    if choices:
        lines += ["", f"{message}; choose one:" if message else "choose a run:"]
        lines += [f"  [{select_key(index)}] {item['run_id']}  {item['run_file']}" for index, item in enumerate(choices)]
        lines += ["", "Press an entry's key to choose; nothing is guessed."]
        return CONTROLS.sub("", "\n".join(lines) + "\n")
    if view is None:
        lines += ["", message or "no run selected"]
        if stale:
            lines.append(f"STALE: {stale}")
        return CONTROLS.sub("", "\n".join(lines) + "\n")
    sources = " · ".join(f"{name} {clock(last_ok.get(name))}" for name in view.get("sources", {}))
    lines.append(f"run {view.get('run_id')} · last good read (UTC): {sources}")
    if hook is not None:  # informational only; the board's own refresh never depends on hooks.
        trigger = (hook.get("trigger") or {}).get("event")
        last = f"{clock(hook.get('reconciled_at'))} via {trigger}" if hook else "none recorded"
        lines.append(f"hooks: last reconcile {last}" + (f" (stale: {hook['stale']})" if hook.get("stale") else ""))
    if stale:
        lines.append(f"STALE: {stale} — showing last good data")
    coordinator = view.get("coordinator") or {}
    lines.append(f"coordinator {coordinator.get('label') or '-'}: {worker_line(coordinator)}")
    lines += [f"run gap: {gap}" for gap in view.get("data_gaps", [])]
    for index, task in enumerate(view.get("tasks", [])):
        title = f" — {task['title']}" if task.get("title") else ""
        lines += [
            "",
            f"[{select_key(index)}] {task['id']}{title}",
            f"    worker      {worker_line(task)}",
            f"    worktree    {task.get('worktree') or task.get('repository') or 'not recorded'}",
            f"    lifecycle   {lifecycle_line(task)}",
            f"    acceptance  {task.get('acceptance') or 'not recorded'}",
            f"    evidence    {evidence_line(task.get('evidence') or [])}",
            f"    reports     {report_line(task.get('reports') or [])}",
        ]
        lines += [f"    gap         {gap}" for gap in task.get("data_gaps", [])]
    if not view.get("tasks"):
        lines += ["", "no tasks recorded"]
    if message:
        lines += ["", message]
    return CONTROLS.sub("", "\n".join(lines) + "\n")


# --- Board loop -------------------------------------------------------------


class Board:
    """One sequential refresh loop; state survives failed reads as a visibly stale view."""

    def __init__(self, socket: str, pane: str | None, root: Path, out: TextIO, state: Path | None = None) -> None:
        self.socket, self.pane, self.root, self.out, self.state = socket, pane, root, out, state
        self.hook: dict[str, Any] | None = None
        self.run_file: Path | None = None
        self.run_id: str | None = None
        self.choices: list[dict[str, Any]] = []
        self.view: dict[str, Any] | None = None
        self.last_ok: dict[str, str] = {}
        self.stale: str | None = None
        self.message: str | None = None  # run resolution / data state; refresh-owned.
        self.notice: str | None = None  # last key or label result; kept until the next key.

    def refresh(self) -> None:
        snapshot, error = snapshot_or_error(self.socket)
        if self.run_file is None:
            resolution = resolve_run(self.socket, self.pane, self.root, snapshot)
            if "run_file" not in resolution:
                self.choices, self.message, self.stale = resolution["choices"], resolution["error"], error
                return
            self.run_file, self.choices = Path(resolution["run_file"]), []
            self.run_id = resolution["run_id"]
            self.message = None
        view = inspect_enrolled(enrollment(self.socket, self.root, self.run_file, self.run_id), snapshot, error)
        if self.state is not None and self.run_id:
            self.hook = read_observation(observation_path(self.state, self.socket, self.run_id))
        failures = []
        for name, source in view["sources"].items():
            if source["ok"]:
                self.last_ok[name] = source["read_at"]
            else:
                failures.append(f"{name}: {source.get('error') or '; '.join(view['data_gaps']) or 'read failed'}")
        self.stale = "; ".join(failures) or None
        if failures:  # keep the last good view (if any) and mark it stale.
            if self.view is None:
                self.message = "no successful read yet"
            return
        self.view, self.message = view, None
        enrolled = {entry.get("run_id") for entry in hr.enrolled_runs(self.socket, self.root)}
        _, _, errors = sync_labels(view, snapshot, enrolled)
        if errors:
            self.notice = "; ".join(errors)

    def key(self, char: str) -> bool:
        """Handle one key; return False to exit."""
        self.notice = None
        if char in ("q", "Q", "\x04"):
            return False
        if char in ("r", "R"):
            self.refresh()
        elif char in SELECT and self.choices:
            index = SELECT.index(char)
            if index < len(self.choices):
                self.run_id = self.choices[index]["run_id"]
                self.run_file, self.choices, self.message = Path(self.choices[index]["run_file"]), [], None
                self.refresh()
        elif (char in SELECT or char in ("c", "C")) and self.run_file and self.view:
            tasks = self.view.get("tasks", [])
            target = "coordinator" if char in ("c", "C") else None
            if char in SELECT and SELECT.index(char) < len(tasks):
                target = tasks[SELECT.index(char)]["id"]
            if target:
                try:
                    self.notice = focus(self.socket, self.run_file, target, self.root, self.run_id)
                except hr.UserError as error:
                    self.notice = f"focus refused: {error}"
        return True

    def draw(self) -> None:
        message = " · ".join(text for text in (self.message, self.notice) if text) or None
        self.out.write("\x1b[H\x1b[2J" + render(self.view, self.last_ok, self.stale, message, self.choices, self.hook))
        self.out.flush()


def run_board(board: Board, stdin_fd: int, interval: float = REFRESH_SECONDS) -> int:
    board.refresh()
    board.draw()
    due = time.monotonic() + interval
    while True:
        ready, _, _ = select.select([stdin_fd], [], [], max(0.0, due - time.monotonic()))
        if ready:
            data = os.read(stdin_fd, 64)
            if not data:  # EOF: the pane's input is gone.
                return 0
            for char in data.decode(errors="ignore"):
                if not board.key(char):
                    return 0
            board.draw()
        if time.monotonic() >= due:
            board.refresh()  # sequential: the next refresh is scheduled only after this one returns.
            board.draw()
            due = time.monotonic() + interval


def command_board() -> int:
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))  # closing the pane ends the loop.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    board = Board(endpoint(), context_pane(), hr.registry_root(), sys.stdout, state_root())
    fd = sys.stdin.fileno()
    restore = None
    if os.isatty(fd):
        import termios
        import tty

        restore = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    try:
        return run_board(board, fd)
    except KeyboardInterrupt:
        return 0
    finally:
        if restore is not None:
            with contextlib.suppress(OSError):
                termios.tcsetattr(fd, termios.TCSADRAIN, restore)


# --- Actions ----------------------------------------------------------------


def notify(text: str) -> None:
    print(text)
    with contextlib.suppress(hr.UserError):
        herdr("notification", "show", "zstack", "--body", text, "--sound", "none")


def action_resolution() -> tuple[str, dict[str, Any]]:
    socket = endpoint()
    snapshot, _ = snapshot_or_error(socket)
    return socket, resolve_run(socket, context_pane(), hr.registry_root(), snapshot)


def command_open_board() -> int:
    socket, resolution = action_resolution()
    if "run_file" not in resolution and not resolution["choices"]:
        notify(f"{resolution['error']}; board not opened")
        return 1
    pane = context_pane()
    plugin = os.environ.get("HERDR_PLUGIN_ID") or "zstack.herdr"
    argv = ["plugin", "pane", "open", "--plugin", plugin, "--entrypoint", "board", "--placement", "split"]
    herdr(*argv, "--target-pane", str(pane), "--direction", "right", "--no-focus")
    print(f"board opened for pane {pane} on {socket}")
    return 0


def command_focus(role: str) -> int:
    socket, resolution = action_resolution()
    if "run_file" not in resolution:
        notify(resolution["error"] + ("; open the board to choose" if resolution["choices"] else ""))
        return 1
    run_file = Path(resolution["run_file"])
    if role == "coordinator":
        target = "coordinator"
    else:
        bound = [task["id"] for task in resolution["view"]["tasks"] if task.get("binding")]
        if len(bound) != 1:
            notify(
                f"run {resolution['run_id']} has {len(bound)} bound tasks; choose a worker with the board's number keys"
            )
            return 1
        target = bound[0]
    try:
        notify(focus(socket, run_file, target, run_id=resolution["run_id"]))
    except hr.UserError as error:
        notify(f"focus refused: {error}")
        return 1
    return 0


def command_reconcile() -> int:
    state = state_root()
    if state is None:
        raise hr.UserError("HERDR_PLUGIN_STATE_DIR is not set; run this from a Herdr plugin hook")
    event = os.environ.get("HERDR_PLUGIN_EVENT") or "manual"
    for line in reconcile(endpoint(), hr.registry_root(), state, event, os.environ.get("HERDR_PLUGIN_EVENT_JSON")):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plugin.py", description=__doc__)
    parser.add_argument("command", choices=("board", "open-board", "focus-coordinator", "focus-worker", "reconcile"))
    args = parser.parse_args(argv)
    try:
        if args.command == "board":
            return command_board()
        if args.command == "open-board":
            return command_open_board()
        if args.command == "reconcile":
            return command_reconcile()
        return command_focus("coordinator" if args.command == "focus-coordinator" else "worker")
    except hr.UserError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
