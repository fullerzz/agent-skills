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

try:  # only the board pane runs with rich (herdr-plugin.toml adds it there); hooks and actions do not need it.
    from rich import box
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.segment import Segment
    from rich.table import Table
    from rich.text import Text

    HAVE_RICH = True
except ImportError:
    HAVE_RICH = False

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator

    from rich.console import ConsoleOptions, RenderableType

sys.path.insert(0, str(Path(__file__).resolve().parent))  # works under `python -I` too.
import herdr_run as hr
from herdr_run import SOURCE, clear_flags, herdr

REFRESH_SECONDS = 5
FOCUSABLE = ("ok", "moved")
SELECT = "123456789abdefghijklmnopstuvwxyz"  # one key per entry; skips c, q, r. ASCII only.
CONTROLS = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")  # terminal controls from run/snapshot text.
OBSERVATION_VERSION = 1
DETAIL_GAPS = ("no report registered", "report file missing")  # inspector report fields already show these.
BIND_STYLE = {"ok": "green", "moved": "yellow", "unbound": "dim"}  # any other status is a broken binding: red.
ACCEPT_STYLE = {"accepted": "green", "rejected": "red"}
LIFE_STYLE = {"blocked": "bold red", "working": "cyan", "idle": "green", "done": "green"}
BOARD_PANE_ENV = "ZSTACK_BOARD_PANE"  # tab plugin panes take no target pane, so open-board passes the caller.


# --- Herdr calls ------------------------------------------------------------


def endpoint() -> str:
    socket = os.environ.get("HERDR_SOCKET_PATH")
    if not socket:
        raise hr.UserError("HERDR_SOCKET_PATH is not set; run this from a Herdr plugin entrypoint")
    return socket


def plugin_context() -> dict[str, Any]:
    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except ValueError:
        return {}
    return context if isinstance(context, dict) else {}


def context_pane() -> str | None:
    """The caller's pane: the pane open-board passed to its board tab, then plugin context, then HERDR_PANE_ID."""
    return os.environ.get(BOARD_PANE_ENV) or plugin_context().get("focused_pane_id") or os.environ.get("HERDR_PANE_ID")


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


def binding_cells(item: dict[str, Any]) -> tuple[str, str]:
    """(`agent "name" @ pane`, binding status) for one coordinator or task binding."""
    binding, check = item.get("binding") or {}, item.get("binding_check") or {}
    if not binding:
        return "-", "unbound"
    name = check.get("agent_name") or binding.get("agent_name")
    who = (binding.get("agent") or "shell") + (f' "{name}"' if name else "")
    return f"{who} @ {check.get('observed_pane_id') or binding['pane_id']}", check.get("status", "unchecked")


def worker_line(item: dict[str, Any]) -> str:
    """Binding and status, plus the moved-from pane and any check detail."""
    binding, check = item.get("binding") or {}, item.get("binding_check") or {}
    if not binding:
        return "unbound"
    who, status = binding_cells(item)
    text = f"{who} {status}" + (f" from {binding['pane_id']}" if status == "moved" else "")
    return text + (f": {check['detail']}" if check.get("detail") else "")


def task_notes(task: dict[str, Any]) -> list[str]:
    """Detail that does not fit a table row: binding problems, missing or remote reports, data gaps."""
    notes, check = [], task.get("binding_check") or {}
    if task.get("binding") and (check.get("status") == "moved" or check.get("detail")):
        notes.append(f"{task['id']}: {worker_line(task)}")
    reports = task.get("reports") or []
    notes += [f"{task['id']}: missing report {item['ref']}" for item in reports if item["exists"] is False]
    if remote := sum(item["exists"] is None for item in reports):
        notes.append(f"{task['id']}: {remote} remote report(s) not checked")
    return notes + [gap for gap in task.get("data_gaps", []) if not gap.endswith("report file missing")]


def select_key(index: int) -> str:
    return SELECT[index] if index < len(SELECT) else "-"


def text(value: object, style: str = "") -> Text:
    """Run and snapshot data as one literal line: no markup, no terminal controls, cut with an ellipsis."""
    return Text(CONTROLS.sub("", str(value)).replace("\n", " "), style=style, no_wrap=True, overflow="ellipsis")


def line(*parts: Text) -> Text:
    """Styled parts joined into one line, cut like text()."""
    return Text.assemble(*parts, no_wrap=True, overflow="ellipsis")


def task_table(tasks: list[dict[str, Any]], selected_task: str | None = None) -> Table:
    table = Table(box=box.SIMPLE_HEAD, show_edge=False, pad_edge=False, expand=True, header_style="bold")
    table.add_column("", width=2, no_wrap=True)
    table.add_column("Task / title", ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column("Lifecycle", width=9, no_wrap=True, overflow="ellipsis")
    table.add_column("Acceptance", width=10, no_wrap=True, overflow="ellipsis")
    for index, task in enumerate(tasks):
        life = (task.get("lifecycle") or {}).get("observed") or "-"
        acceptance = task.get("acceptance") or "not recorded"
        acceptance = "pending" if acceptance == "not recorded" else acceptance
        selected = task["id"] == selected_task
        table.add_row(
            text((">" if selected else "") + select_key(index), "bold"),
            text(f"{task['id']} · {task.get('title') or ''}", "bold" if selected else ""),
            text(life, LIFE_STYLE.get(life, "")),
            text(acceptance, ACCEPT_STYLE.get(acceptance, "dim")),
            style="on #26393f" if selected else None,
        )
    return table


def detail_text(value: object, style: str = "") -> Text:
    """Literal wrapped detail retains full titles, paths, and revisions."""
    return Text(CONTROLS.sub("", str(value)).replace("\n", " "), style=style, overflow="fold")


def detail_panel(task: dict[str, Any]) -> Panel:
    lifecycle = task.get("lifecycle") or {}
    fields = Table.grid(padding=(0, 1), expand=True)
    fields.add_column(style="bold", ratio=1)
    fields.add_column(ratio=3, overflow="fold")
    values = [
        ("Task ID", task["id"]),
        ("Title", task.get("title") or "not recorded"),
        ("Binding", worker_line(task)),
        ("Repository", task.get("repository") or "not recorded"),
        ("Worktree", task.get("worktree") or "not recorded"),
        ("Lifecycle", lifecycle.get("observed") or "not recorded"),
        ("Orchestrator state", lifecycle.get("orch_state") or "not recorded"),
        ("Reported status", lifecycle.get("reported_status") or "not recorded"),
        ("Acceptance", task.get("acceptance") or "not recorded"),
    ]
    binding = task.get("binding") or {}
    for key, label in (("terminal_id", "Terminal ID"), ("agent_session", "Agent session"), ("bound_at", "Bound at")):
        if binding.get(key) is not None:
            values.append((label, binding[key]))
    check = task.get("binding_check") or {}
    if check.get("detail") and not binding:
        values.append(("Binding detail", check["detail"]))
    reports = task.get("reports") or []
    if not reports:
        values.append(("Reports", "no report registered"))
    for report in reports:
        availability = {True: "available", False: "missing", None: "remote; not checked"}[report.get("exists")]
        values.append(("Report", f"{report['ref']} · {availability}"))
    evidence = task.get("evidence") or []
    if not evidence:
        values.append(("Evidence", "none registered"))
    for item in evidence:
        values.append(("Evidence", item["ref"]))
        if item.get("revision"):
            values.append(("Revision", item["revision"]))
    values.extend(("Data gap", gap) for gap in task.get("data_gaps") or [] if not gap.endswith(DETAIL_GAPS))
    styles = {
        "Binding": BIND_STYLE.get(binding_cells(task)[1], "red"),
        "Lifecycle": LIFE_STYLE.get(lifecycle.get("observed"), ""),
        "Acceptance": ACCEPT_STYLE.get(task.get("acceptance"), "dim"),
        "Data gap": "yellow",
    }
    for label, value in values:
        fields.add_row(detail_text(label), detail_text(value, styles.get(label, "")))
    return Panel(fields, title=text("Selected task", "bold cyan"), border_style="cyan")


class Frame:
    """Bounded header/footer around a scrollable Rich body."""

    def __init__(self, head: list[RenderableType], body: list[RenderableType], keys: str, offset: int = 0) -> None:
        self.head, self.body, self.keys = Group(*head), Group(*body), text(keys, "dim")
        self.offset = max(0, offset)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> Iterator[Segment]:
        def lines(renderable: RenderableType) -> list[list[Segment]]:
            return console.render_lines(renderable, options.update(height=None), pad=False)

        height = max(1, options.height if options.height is not None else console.height)
        head, body, keys = lines(self.head), lines(self.body), lines(self.keys)
        footer = keys[:1] if height > 1 else []
        head = head[: max(1, min(len(head), height - len(footer) - (1 if height > 2 else 0)))]
        room = max(0, height - len(head) - len(footer))
        body_room = room - 1 if len(body) > room and room > 1 else room
        self.offset = min(self.offset, max(0, len(body) - body_room)) if body_room else 0
        shown = body[self.offset : self.offset + body_room]
        if len(body) > room and room > 1:
            shown += lines(
                text(f"Lines {self.offset + 1}-{self.offset + len(shown)} of {len(body)} · +/- scroll", "dim")
            )[:1]
        for rendered_line in (*head, *shown, *footer):
            yield from rendered_line
            yield Segment.line()


def problem_notes(view: dict[str, Any]) -> list[str]:
    notes = list(view.get("data_gaps") or [])
    coordinator = view.get("coordinator") or {}
    if binding_cells(coordinator)[1] not in FOCUSABLE:
        notes.append(f"Coordinator: {worker_line(coordinator)}")
    for task in view.get("tasks", []):
        status = binding_cells(task)[1]
        if status not in (*FOCUSABLE, "unbound"):
            notes.append(f"{task['id']}: binding {status}")
        if task.get("acceptance") == "rejected":
            notes.append(f"{task['id']}: acceptance rejected")
        if (task.get("lifecycle") or {}).get("observed") == "blocked":
            notes.append(f"{task['id']}: lifecycle blocked")
        notes.extend(task_notes(task))
    return list(dict.fromkeys(notes))


class InspectorFrame(Frame):
    """Pinned run context and independently scrollable task and inspector regions."""

    def __init__(
        self,
        head: list[RenderableType],
        tasks: list[dict[str, Any]],
        notes: list[str],
        selected: dict[str, Any] | None,
        offset: int,
        inspector_offset: int,
        active_region: str,
        reveal_selection: bool,
    ) -> None:
        super().__init__(
            head,
            [],
            "↑/↓ select · Enter focus · Tab region · +/- scroll · Esc clear · c coord · r refresh · q quit",
            offset,
        )
        self.tasks, self.notes, self.selected = tasks, notes, selected
        self.inspector_offset = max(0, inspector_offset)
        self.active_region, self.reveal_selection = active_region, reveal_selection

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> Iterator[Segment]:  # noqa: C901 - bounded dual-region rendering.
        width = options.max_width
        height = max(1, options.height if options.height is not None else console.height)

        def lines(renderable: RenderableType, size: int) -> list[list[Segment]]:
            return console.render_lines(renderable, options.update(width=max(1, size), height=None), pad=False)

        head = lines(self.head, width)
        footer = lines(self.keys, width)[:1] if height > 1 else []
        head = head[: max(0, height - len(footer) - min(4, max(0, height - 2)))]
        room = max(0, height - len(head) - len(footer))
        wide = width >= 110
        left_width = (width - 1) * 55 // 100 if wide else width
        right_width = width - left_width - 1 if wide else width
        task_height = room if wide else room // 2
        inspector_height = room if wide else room - task_height
        task_body: list[RenderableType] = [
            task_table(self.tasks, self.selected["id"] if self.selected else None)
        ]
        if not self.tasks:
            task_body = [text("no tasks recorded", "dim")]
        if self.notes:
            task_body += [
                text("All problems / data gaps", "bold yellow"),
                *(detail_text(f"! {note}", "yellow") for note in self.notes),
            ]
        task_lines = lines(Group(*task_body), left_width)
        inspector = (
            detail_panel(self.selected).renderable
            if self.selected
            else detail_text("Select a task with its row key or ↑/↓ to inspect binding, reports and evidence.", "dim")
        )
        inspector_lines = lines(inspector, right_width)

        def region(
            content: list[list[Segment]], size: int, rows: int, name: str, offset: int
        ) -> tuple[list[list[Segment]], int]:
            if rows <= 0:
                return [], 0
            body_rows = max(0, rows - 2)
            offset = min(offset, max(0, len(content) - body_rows)) if body_rows else 0
            if name == "Tasks" and self.reveal_selection and self.selected and body_rows:
                key = ">" + select_key(
                    next(i for i, task in enumerate(self.tasks) if task["id"] == self.selected["id"])
                )
                selected_line = next(
                    (
                        i
                        for i, row in enumerate(content)
                        if "".join(segment.text for segment in row).lstrip().startswith(key)
                    ),
                    None,
                )
                if selected_line is not None and not offset <= selected_line < offset + body_rows:
                    offset = (
                        max(0, selected_line - body_rows + 1) if selected_line >= offset + body_rows else selected_line
                    )
            active = self.active_region == ("tasks" if name == "Tasks" else "inspector")
            title = text(f"{'▸ ' if active else ''}{name}", "bold cyan" if active else "bold")
            result = lines(title, size)[:1]
            result += content[offset : offset + body_rows]
            while len(result) < rows - 1:
                result.append([])
            if rows > 1:
                result += lines(
                    text(
                        f"{offset + 1 if content else 0}-{min(len(content), offset + body_rows)}/{len(content)}"
                        " · +/- scroll",
                        "dim",
                    ),
                    size,
                )[:1]
            return result[:rows], offset

        left, self.offset = region(task_lines, left_width, task_height, "Tasks", self.offset)
        right, self.inspector_offset = region(
            inspector_lines, right_width, inspector_height, "Inspector", self.inspector_offset
        )
        body = left + right
        if wide:
            body = []
            for lrow, rrow in zip(left, right, strict=True):
                body.append(
                    [
                        *Segment.adjust_line_length(lrow, left_width),
                        Segment("│", style=None),
                        *Segment.adjust_line_length(rrow, right_width),
                    ]
                )
        for row in (*head, *body, *footer):
            yield from row
            yield Segment.line()


def board_frame(
    view: dict[str, Any] | None,
    last_ok: dict[str, str],
    stale: str | None = None,
    message: str | None = None,
    choices: list[dict[str, Any]] | None = None,
    hook: dict[str, Any] | None = None,
    width: int = 80,
    selected_task: str | None = None,
    offset: int = 0,
    inspector_offset: int = 0,
    active_region: str = "tasks",
    reveal_selection: bool = False,
) -> Frame:
    """The board for one inspection view (or a choose-run / no-run screen): one table row per task."""
    title = text("zstack board", "bold")
    if choices:
        ask = f"{message}; choose one:" if message else "choose a run:"
        rows = [
            text(f"[{select_key(index)}] {item['run_id']}  {item['run_file']}") for index, item in enumerate(choices)
        ]
        return Frame(
            [title, text(ask, "bold yellow")], rows, "entry key choose · +/- scroll · r refresh · q quit", offset
        )
    if view is None:
        head = [title, text(message or "no run selected", "bold yellow")]
        return Frame(head + ([text(f"STALE: {stale}", "bold red")] if stale else []), [], "r refresh · q quit", offset)
    coordinator, tasks = view.get("coordinator") or {}, view.get("tasks", [])
    times = {name: clock(last_ok.get(name)) for name in view.get("sources", {})}
    read = " ".join(f"{name} {stamp}" for name, stamp in times.items())
    if times and len(set(times.values())) == 1:  # one refresh reads every source; differing times follow a failure.
        read = next(iter(times.values()))
    read = read or "never"
    label = f" · {coordinator['label']}" if coordinator.get("label") else ""
    head = [
        line(
            text("zstack ", "bold"),
            text(view.get("run_id"), "bold cyan"),
            text(f"{label} · "),
            text(f"read {read} UTC", "dim"),
        )
    ]
    status = binding_cells(coordinator)[1]
    coord = line(text("coord  ", "dim"), text(worker_line(coordinator), BIND_STYLE.get(status, "red")))
    if hook is not None:  # informational only; the board's own refresh never depends on hooks.
        trigger = (hook.get("trigger") or {}).get("event")
        last = f"{clock(hook.get('reconciled_at'))} via {trigger}" if hook else "none recorded"
        coord.append_text(text(f" · hooks {last}" + (f" (stale: {hook['stale']})" if hook.get("stale") else ""), "dim"))
    if stale:
        head.append(text(f"STALE: {stale} — showing last good data", "bold red"))
    if message:
        head.append(text(message, "bold yellow"))
    accepted = sum(task.get("acceptance") == "accepted" for task in tasks)
    rejected = sum(task.get("acceptance") == "rejected" for task in tasks)
    working = sum((task.get("lifecycle") or {}).get("observed") == "working" for task in tasks)
    blocked = sum((task.get("lifecycle") or {}).get("observed") == "blocked" for task in tasks)
    head.insert(
        1,
        line(
            text(f"{len(tasks)} tasks · ", "bold"),
            text(f"{accepted} accepted", "green"),
            text(f" · {rejected} rejected", "red"),
            text(f" · {len(tasks) - accepted - rejected} pending · "),
            text(f"{working} working", "cyan"),
            text(f" · {blocked} blocked", "bold red"),
        ),
    )
    head.insert(2, coord)
    notes = problem_notes(view)
    if notes:
        head.append(text(f"! {notes[0]} · {len(notes)} problems / data gaps; full list after tasks", "yellow"))
    selected = next((task for task in tasks if task["id"] == selected_task), None)
    return InspectorFrame(head, tasks, notes, selected, offset, inspector_offset, active_region, reveal_selection)


# --- Board loop -------------------------------------------------------------


class Board:
    """One sequential refresh loop; state survives failed reads as a visibly stale view."""

    def __init__(self, socket: str, pane: str | None, root: Path, out: TextIO, state: Path | None = None) -> None:
        self.socket, self.pane, self.root, self.state = socket, pane, root, state
        self.console, self.live = Console(file=out), None
        self.hook: dict[str, Any] | None = None
        self.run_file: Path | None = None
        self.run_id: str | None = None
        self.choices: list[dict[str, Any]] = []
        self.view: dict[str, Any] | None = None
        self.last_ok: dict[str, str] = {}
        self.stale: str | None = None
        self.message: str | None = None  # run resolution / data state; refresh-owned.
        self.notice: str | None = None  # last key or label result; kept until the next key.
        self.selected_task: str | None = None
        self.offset = 0
        self.inspector_offset = 0
        self.active_region = "tasks"
        self.reveal_selection = False

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
        self.reveal_selection |= [t["id"] for t in (self.view or {}).get("tasks", [])] != [
            t["id"] for t in view.get("tasks", [])
        ]
        self.view, self.message = view, None
        if self.selected_task and not any(task["id"] == self.selected_task for task in view.get("tasks", [])):
            self.notice = f"task {self.selected_task} is no longer in this run; selection cleared"
            self.selected_task, self.offset, self.inspector_offset = None, 0, 0
            self.active_region = "tasks"
        enrolled = {entry.get("run_id") for entry in hr.enrolled_runs(self.socket, self.root)}
        _, _, errors = sync_labels(view, snapshot, enrolled)
        if errors:
            self.notice = "; ".join(errors)

    def key(self, char: str) -> bool:  # noqa: C901 - keep explicit key dispatch and selection state together.
        """Handle one key; return False to exit."""
        self.notice = None
        if char in ("q", "Q", "\x04"):
            return False
        if char in ("r", "R"):
            self.refresh()
        elif char == "\x1b":
            self.selected_task, self.offset, self.inspector_offset = None, 0, 0
            self.active_region = "tasks"
        elif char == "\t" and self.view:
            self.active_region = "inspector" if self.active_region == "tasks" else "tasks"
        elif char in ("+", "-"):
            delta = 1 if char == "+" else -1
            if self.active_region == "inspector":
                self.inspector_offset = max(0, self.inspector_offset + delta)
            else:
                self.offset = max(0, self.offset + delta)
                self.reveal_selection = False
        elif char in SELECT and self.choices:
            index = SELECT.index(char)
            if index < len(self.choices):
                self.run_id = self.choices[index]["run_id"]
                self.run_file, self.choices, self.message = Path(self.choices[index]["run_file"]), [], None
                self.refresh()
        elif self.run_file and self.view:
            tasks = self.view.get("tasks", [])
            target = "coordinator" if char in ("c", "C") else None
            if char in ("[", "]", "up", "down") and tasks:
                forward = char in ("]", "down")
                start = -1 if forward else 0
                index = next((i for i, task in enumerate(tasks) if task["id"] == self.selected_task), start)
                index = (index + (1 if forward else -1)) % len(tasks)
                self.selected_task, self.inspector_offset = tasks[index]["id"], 0
                self.reveal_selection = True
            elif char in ("\r", "\n"):
                target = self.selected_task
            elif char in SELECT and SELECT.index(char) < len(tasks):
                self.selected_task, self.inspector_offset = tasks[SELECT.index(char)]["id"], 0
                self.reveal_selection = True
            if target:
                try:
                    self.notice = focus(self.socket, self.run_file, target, self.root, self.run_id)
                except hr.UserError as error:
                    self.notice = f"focus refused: {error}"
        return True

    def draw(self) -> None:
        message = " · ".join(part for part in (self.message, self.notice) if part) or None
        frame = board_frame(
            self.view,
            self.last_ok,
            self.stale,
            message,
            self.choices,
            self.hook,
            self.console.width,
            selected_task=self.selected_task,
            offset=self.offset,
            inspector_offset=self.inspector_offset,
            active_region=self.active_region,
            reveal_selection=self.reveal_selection,
        )
        if self.live is None:
            self.console.print(frame)
        else:
            self.live.update(frame, refresh=True)
        self.offset = frame.offset
        self.inspector_offset = getattr(frame, "inspector_offset", 0)
        self.reveal_selection = False


def run_board(board: Board, stdin_fd: int, interval: float = REFRESH_SECONDS) -> int:  # noqa: C901 - one input/refresh state machine.
    board.refresh()
    board.draw()
    due = time.monotonic() + interval
    escape = ""
    escape_due = 0.0
    while True:
        deadline = min(due, escape_due) if escape else due
        ready, _, _ = select.select([stdin_fd], [], [], max(0.0, deadline - time.monotonic()))
        if escape and time.monotonic() >= escape_due:
            standalone = escape == "\x1b"
            escape = ""
            if standalone:
                if not board.key("\x1b"):
                    return 0
                board.draw()
        if ready:
            data = os.read(stdin_fd, 64)
            if not data:  # EOF: the pane's input is gone.
                return 0
            for char in data.decode(errors="ignore"):
                if escape == "\x1b":
                    if char in "[O":  # CSI / SS3: consume the entire key, even across reads.
                        escape += char
                        escape_due = time.monotonic() + 0.1
                        continue
                    if not board.key("\x1b"):
                        return 0
                    escape = ""
                elif escape:
                    if "@" <= char <= "~":
                        if escape in ("\x1b[", "\x1bO") and char in "AB":
                            board.key("up" if char == "A" else "down")
                        escape = ""
                    else:
                        escape = (escape + char)[:32]
                        escape_due = time.monotonic() + 0.1
                    continue
                if char == "\x1b":
                    escape = char
                    escape_due = time.monotonic() + 0.05
                    continue
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
    if not HAVE_RICH:
        raise hr.UserError("the board needs rich; open it with the open-board action, whose pane command adds it")
    board = Board(endpoint(), context_pane(), hr.registry_root(), sys.stdout, state_root())
    fd = sys.stdin.fileno()
    restore = None
    if os.isatty(fd):
        import termios
        import tty

        restore = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    try:
        if not board.console.is_terminal:  # piped output: print each frame.
            return run_board(board, fd)
        # Full-screen redraws in the alternate screen; nothing refreshes between explicit draws.
        with Live(console=board.console, screen=True, auto_refresh=False) as live:
            board.live = live
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
    argv = ["plugin", "pane", "open", "--plugin", plugin, "--entrypoint", "board", "--placement", "tab"]
    if workspace := plugin_context().get("workspace_id") or os.environ.get("HERDR_WORKSPACE_ID"):
        argv += ["--workspace", str(workspace)]
    opened = herdr(*argv, "--env", f"{BOARD_PANE_ENV}={pane}", "--no-focus")
    tab = opened.get("result", {}).get("plugin_pane", {}).get("pane", {}).get("tab_id")
    if tab:
        try:
            herdr("tab", "rename", tab, "zstack status")
        except hr.UserError as error:
            print(f"board opened, but tab rename failed: {error}")
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
                f"run {resolution['run_id']} has {len(bound)} bound tasks; select a task in the board, then press Enter"
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
        if args.command == "board" and HAVE_RICH:
            Console(stderr=True).print(Panel(detail_text(error), title="Unable to open board", border_style="red"))
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
