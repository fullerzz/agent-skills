#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Coordinator records and read-only inspection for Herdr-enrolled zstack runs.

This helper is the coordinator's tool. Workers supply reports or report pointers;
they never record acceptance, rejection, or verification evidence. Commands that
change acceptance or evidence refuse to run from a pane bound to one of the run's
tasks. `inspect` never writes coordinator files, the registry, or orch stores.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

ORCH_DIR = Path(__file__).resolve().parents[2] / "skills/z-mode/scripts/orch"
VERSION = 1
ACCEPTANCE = ("not recorded", "accepted", "rejected")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")  # Herdr token values are capped at 80 characters.
TASK_ID_RULE = "task id must match " + SAFE_ID.pattern + "; 'coordinator' is reserved"
SNAPSHOT_TIMEOUT = 5
RUN_KEYS = {"version", "run_id", "coordinator", "endpoint", "updated_at", "orch_store", "tasks"}
TASK_KEYS = {"id", "title", "binding", "repository", "worktree", "reports", "acceptance", "evidence"}
ORCH_OWNED = {"reports", "acceptance", "evidence"}
BINDING_KEYS = {"pane_id", "terminal_id", "agent", "agent_name", "agent_session", "bound_at"}
REGISTRY_KEYS = {"version", "run_id", "endpoint", "run_file", "enrolled_at"}


class UserError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path = Path(os.path.realpath(path))  # replace a symlink's target, not the link.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(data, indent=2) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


# --- Schema -----------------------------------------------------------------


def text(value: object, nullable: bool = False) -> bool:
    return (nullable and value is None) or (isinstance(value, str) and bool(value.strip()))


def endpoint_socket(socket: str | os.PathLike[str]) -> str:
    return os.path.realpath(Path(socket).expanduser())


def valid_task_id(value: object) -> bool:
    return isinstance(value, str) and value != "coordinator" and SAFE_ID.fullmatch(value) is not None


def validate_binding(value: object, where: str, gaps: list[str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        gaps.append(f"{where}: binding must be an object or null")
        return None
    bad = [key for key in value if key not in BINDING_KEYS]
    if bad or not text(value.get("pane_id")):
        gaps.append(f"{where}: binding needs pane_id and only {sorted(BINDING_KEYS)}")
        return None
    for key in BINDING_KEYS - {"pane_id"}:
        if not text(value.get(key), nullable=True):
            gaps.append(f"{where}: binding {key} must be a nonempty string or null")
            return None
    return {key: value.get(key) for key in sorted(BINDING_KEYS)}


def validate_task(value: object, index: int, orch: bool) -> dict[str, Any]:  # noqa: C901 - flat field checks.
    gaps: list[str] = []
    if not isinstance(value, dict) or not valid_task_id(value.get("id")):
        return {"id": f"#{index}", "binding": None, "data_gaps": [f"task #{index}: {TASK_ID_RULE}"]}
    task: dict[str, Any] = {"id": value["id"], "data_gaps": gaps}
    where = f"task {task['id']}"
    for key in value:
        if key not in TASK_KEYS:
            gaps.append(f"{where}: unknown field {key}")
        elif orch and key in ORCH_OWNED:
            gaps.append(f"{where}: {key} belongs to the orch store, ignored here")
    for key in ("title", "repository", "worktree"):
        task[key] = value.get(key) if text(value.get(key), nullable=True) else None
        if task[key] is None and value.get(key) is not None:
            gaps.append(f"{where}: {key} must be a nonempty string")
    task["binding"] = validate_binding(value.get("binding"), where, gaps)
    if orch:
        return task
    acceptance = value.get("acceptance", "not recorded")
    if acceptance not in ACCEPTANCE:
        gaps.append(f"{where}: invalid acceptance {json.dumps(acceptance)}; shown as not recorded")
        acceptance = "not recorded"
    task["acceptance"] = acceptance
    reports = value.get("reports", [])
    if not isinstance(reports, list) or not all(text(item) for item in reports):
        gaps.append(f"{where}: reports must be a list of nonempty strings")
        reports = []
    task["reports"] = reports
    evidence = value.get("evidence", [])
    valid = isinstance(evidence, list) and all(
        isinstance(item, dict)
        and set(item) <= {"ref", "revision"}
        and text(item.get("ref"))
        and text(item.get("revision"), nullable=True)
        for item in evidence
    )
    if not valid:
        gaps.append(f"{where}: evidence must be a list of {{ref, revision}} objects")
    task["evidence"] = [{"ref": item["ref"], "revision": item.get("revision")} for item in evidence] if valid else []
    return task


def validate_run(data: object) -> tuple[dict[str, Any] | None, list[str]]:  # noqa: C901 - flat field checks.
    """Return (run, gaps). A None run means the whole record is unusable."""
    if not isinstance(data, dict):
        return None, ["run record must be a JSON object"]
    gaps = [f"unknown run field {key}" for key in data if key not in RUN_KEYS]
    if data.get("version") != VERSION:
        return None, [f"unsupported run record version {json.dumps(data.get('version'))}"]
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not SAFE_ID.fullmatch(run_id):
        return None, ["run_id missing or invalid"]
    endpoint = data.get("endpoint")
    if (
        not isinstance(endpoint, dict)
        or set(endpoint) - {"socket", "session"}
        or not text(endpoint.get("socket"))
        or not text(endpoint.get("session"), nullable=True)
    ):
        return None, ["endpoint must be {socket, session}"]
    if not text(data.get("updated_at")):
        return None, ["updated_at missing"]
    orch_store = data.get("orch_store")
    if not text(orch_store, nullable=True):
        return None, ["orch_store must be a nonempty string or null"]
    coordinator = data.get("coordinator")
    if not isinstance(coordinator, dict) or set(coordinator) - {"label", "binding"}:
        return None, ["coordinator must be {label, binding}"]
    if not isinstance(data.get("tasks"), list):
        return None, ["tasks must be a list"]
    tasks = [validate_task(item, index, orch_store is not None) for index, item in enumerate(data["tasks"])]
    seen: set[str] = set()
    for task in tasks:
        if task["id"] in seen:
            task["data_gaps"].append(f"task {task['id']}: duplicate id")
        seen.add(task["id"])
    run = {
        "version": VERSION,
        "run_id": run_id,
        "endpoint": {"socket": endpoint["socket"], "session": endpoint.get("session")},
        "updated_at": data["updated_at"],
        "orch_store": orch_store,
        "coordinator": {
            "label": coordinator.get("label") if text(coordinator.get("label")) else None,
            "binding": validate_binding(coordinator.get("binding"), "coordinator", gaps),
        },
        "tasks": tasks,
    }
    return run, gaps


def read_run(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"run record {path} not found"]
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return None, [f"run record {path} unreadable: {error}"]
    return validate_run(data)


def stored(run: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for task in run["tasks"]:
        keys = ["id", "title", "binding", "repository", "worktree"]
        if run["orch_store"] is None:
            keys += ["reports", "acceptance", "evidence"]
        tasks.append({key: task[key] for key in keys})
    return {**run, "updated_at": now(), "tasks": tasks}


# --- Registry ---------------------------------------------------------------


def registry_root(override: str | os.PathLike[str] | None = None) -> Path:
    # ponytail: one per-user path both shells and plugin processes can compute; plugin state dir isn't discoverable.
    if override:
        return Path(override).expanduser().absolute()
    if os.environ.get("ZSTACK_HERDR_REGISTRY"):
        return Path(os.environ["ZSTACK_HERDR_REGISTRY"]).expanduser().absolute()
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state"
    return Path(base).expanduser().absolute() / "zstack/herdr/runs"


def endpoint_key(socket: str) -> str:
    return hashlib.sha256(endpoint_socket(socket).encode()).hexdigest()[:16]


def registry_path(root: Path, socket: str, run_id: str) -> Path:
    return root / endpoint_key(socket) / f"{run_id}.json"


def enroll(run_file: Path, root: Path, replace: bool = False) -> dict[str, Any]:
    run_file = run_file.absolute()
    run, gaps = read_run(run_file)
    if run is None or gaps or any(task["data_gaps"] for task in run["tasks"]):
        raise UserError("cannot enroll invalid run record: " + "; ".join(gaps or ["task data gaps"]))
    path = registry_path(root, run["endpoint"]["socket"], run["run_id"])
    entry = {
        "version": VERSION,
        "run_id": run["run_id"],
        "endpoint": run["endpoint"],
        "run_file": str(run_file),
        "enrolled_at": now(),
    }
    with update_lock(path):  # concurrent enrollments of one run id must not both pass the conflict check.
        if path.exists() and not replace:
            try:
                old = json.loads(path.read_text(encoding="utf-8")).get("run_file")
            except (OSError, ValueError, AttributeError):
                old = None
            if old != str(run_file):
                raise UserError(f"run {run['run_id']} already enrolled on this endpoint for {old}; pass --replace")
        atomic_write(path, entry)
    return {"registry_entry": str(path), **entry}


def enrolled_runs(socket: str, root: Path) -> list[dict[str, Any]]:
    """List registry entries for one endpoint; never reads other endpoints' runs."""
    directory = root / endpoint_key(socket)
    if not directory.is_dir():
        return []
    entries = []
    for path in sorted(directory.glob("*.json")):
        gaps: list[str] = []
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            entries.append({"registry_entry": str(path), "data_gaps": [f"unreadable registry entry: {error}"]})
            continue
        if (
            not isinstance(entry, dict)
            or set(entry) != REGISTRY_KEYS
            or entry.get("version") != VERSION
            or not isinstance(entry.get("run_id"), str)
            or f"{entry['run_id']}.json" != path.name
            or not isinstance(entry.get("endpoint"), dict)
            or not text(entry["endpoint"].get("socket"))
            or endpoint_socket(entry["endpoint"]["socket"]) != endpoint_socket(socket)
            or not text(entry.get("run_file"))
        ):
            entries.append({"registry_entry": str(path), "data_gaps": ["malformed registry entry"]})
            continue
        run, _ = read_run(Path(entry["run_file"]))
        if run is None:
            gaps.append(f"run record {entry['run_file']} unavailable or invalid")
        elif run["run_id"] != entry["run_id"] or endpoint_socket(run["endpoint"]["socket"]) != endpoint_socket(socket):
            gaps.append("run record no longer matches its registry entry")
        entries.append({"registry_entry": str(path), **entry, "data_gaps": gaps})
    return entries


# --- Herdr snapshot ---------------------------------------------------------


def normalize_snapshot(raw: object, socket: str, read_at: str | None = None) -> dict[str, Any]:
    """Turn `herdr api snapshot` JSON into {endpoint, read_at, panes, agents} or raise UserError."""
    if isinstance(raw, dict) and "error" in raw:
        raise UserError(f"herdr snapshot failed: {raw['error']}")
    snapshot = raw
    if isinstance(raw, dict) and "result" in raw:
        snapshot = raw["result"].get("snapshot") if isinstance(raw["result"], dict) else None
    if not isinstance(snapshot, dict):
        raise UserError("herdr snapshot has no snapshot object")
    panes, agents = snapshot.get("panes"), snapshot.get("agents", [])
    if not isinstance(panes, list) or not isinstance(agents, list):
        raise UserError("herdr snapshot panes/agents must be lists")
    for item in [*panes, *agents]:
        if not isinstance(item, dict) or not text(item.get("pane_id")):
            raise UserError("herdr snapshot contains an entry without pane_id")
    return {"endpoint": endpoint_socket(socket), "read_at": read_at or now(), "panes": panes, "agents": agents}


def live_snapshot(socket: str) -> dict[str, Any]:
    herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only herdr argv; no shell.
            [herdr, "api", "snapshot"],
            env={**os.environ, "HERDR_SOCKET_PATH": socket},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=SNAPSHOT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UserError(f"herdr snapshot failed: {error}") from error
    try:
        raw = json.loads(result.stdout or result.stderr)
    except ValueError as error:
        detail = " ".join((result.stderr or result.stdout).split())[:200] or str(error)
        raise UserError(f"herdr snapshot failed (exit {result.returncode}): {detail}") from error
    return normalize_snapshot(raw, socket)


def occupant(snapshot: dict[str, Any], pane_id: str) -> dict[str, Any] | None:
    return next((agent for agent in snapshot["agents"] if agent["pane_id"] == pane_id), None)


def session_value(agent: dict[str, Any] | None) -> str | None:
    session = (agent or {}).get("agent_session")
    return session.get("value") if isinstance(session, dict) else None


def capture_binding(snapshot: dict[str, Any], pane_id: str) -> dict[str, Any]:
    pane = next((pane for pane in snapshot["panes"] if pane["pane_id"] == pane_id), None)
    if pane is None:
        raise UserError(f"pane {pane_id} not found on {snapshot['endpoint']}")
    if not text(pane.get("terminal_id")):
        raise UserError(f"pane {pane_id} exposes no terminal_id; cannot bind durably")
    agent = occupant(snapshot, pane_id)
    return {
        "agent": (agent or {}).get("agent"),
        "agent_name": (agent or {}).get("name"),
        "agent_session": session_value(agent),
        "bound_at": now(),
        "pane_id": pane_id,
        "terminal_id": pane["terminal_id"],
    }


CARRIED_SESSION = "Herdr reported the previous terminal's agent session for this pane; recorded no session"


def rebind(old: dict[str, Any] | None, snapshot: dict[str, Any], pane_id: str) -> tuple[dict[str, Any], list[str]]:
    """Capture a new binding, refusing a session carried over from the binding's previous terminal.

    Herdr 0.9.3 reapplies a restored pane's pre-restart session to the fresh agent it hosts, so a new
    terminal reporting the old session is not evidence of that session.
    """
    new = capture_binding(snapshot, pane_id)
    old = old or {}
    if (
        new["agent_session"]
        and new["agent_session"] == old.get("agent_session")
        and new["terminal_id"] != old.get("terminal_id")
    ):
        return {**new, "agent_session": None}, [CARRIED_SESSION]
    return new, []


def check_binding(binding: dict[str, Any] | None, snapshot: dict[str, Any] | None, socket: str) -> dict[str, Any]:
    """Classify a binding against a live snapshot. Agent names are aliases, never identity."""
    if snapshot is None:
        return {"status": "snapshot unavailable"}
    if snapshot["endpoint"] != endpoint_socket(socket):
        return {"status": "stale endpoint", "detail": f"snapshot is from {snapshot['endpoint']}"}
    if binding is None:
        return {"status": "unbound"}
    if not binding.get("terminal_id"):
        return {"status": "ambiguous", "detail": "binding records no terminal_id"}
    hits = [pane for pane in snapshot["panes"] if pane.get("terminal_id") == binding["terminal_id"]]
    if len(hits) > 1:
        return {"status": "ambiguous", "detail": "terminal_id appears in several panes"}
    if not hits:
        if any(pane["pane_id"] == binding["pane_id"] for pane in snapshot["panes"]):
            return {"status": "occupant changed", "detail": "pane now hosts a different terminal"}
        return {"status": "pane missing"}
    pane = hits[0]
    agent = occupant(snapshot, pane["pane_id"])
    if binding.get("agent_session") and session_value(agent) != binding["agent_session"]:
        return {"status": "occupant changed", "detail": "agent session differs", "observed_pane_id": pane["pane_id"]}
    if binding.get("agent") and (agent or {}).get("agent") != binding["agent"]:
        return {"status": "occupant changed", "detail": "agent kind differs", "observed_pane_id": pane["pane_id"]}
    return {
        "status": "ok" if pane["pane_id"] == binding["pane_id"] else "moved",
        "observed_pane_id": pane["pane_id"],
        "agent_status": (agent or pane).get("agent_status"),
        "agent_name": (agent or {}).get("name"),
    }


def resolve_focus_target(task: dict[str, Any]) -> dict[str, Any]:
    """Return {ok, pane_id} for an `ok` or `moved` binding; anything else is an error.

    `moved` passes because check_binding only reports it when the bound terminal_id (and the recorded
    agent session and kind, if any) still match: Herdr keeps the terminal when a pane moves. Callers
    should check against a snapshot taken immediately before focusing.
    """
    check = task.get("binding_check") or {}
    if check.get("status") in ("ok", "moved") and text(check.get("observed_pane_id")):
        return {"ok": True, "pane_id": check["observed_pane_id"]}
    return {"ok": False, "error": f"task {task.get('id')} binding is {check.get('status', 'unchecked')}; rebind first"}


# --- Orchestration store ----------------------------------------------------


def orch_view(directory: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read units, ledger, and inbox pointers without locks or writes."""
    if str(ORCH_DIR) not in sys.path:
        sys.path.insert(0, str(ORCH_DIR))
    try:
        from store import Store
        from store import UserError as StoreError
    except ImportError as error:
        return {}, [f"orch store {directory} unavailable: {error}"]

    store = Store(directory)  # ponytail: read-only methods only; never status(), inbox_drain(), or begin_write().
    try:
        units, ledger, pointers = store.unit_list(), store.read_ledger(), store.inbox_peek()
    except (StoreError, OSError, UnicodeDecodeError) as error:
        return {}, [f"orch store {directory} unreadable: {error}"]
    invalid = [unit["id"] for unit in units if not valid_task_id(unit["id"])]
    if invalid:
        return {}, [f"orch task {task_id}: {TASK_ID_RULE}" for task_id in invalid]
    view = {}
    for unit in units:
        mine = [row for row in pointers if row["unit"] == unit["id"]]
        view[unit["id"]] = {
            "title": unit["brief"] or None,
            "orch_state": unit["state"],
            "reported_status": mine[-1]["status"] if mine else None,
            "reports": [row["report"] for row in mine if row["report"]],
            "evidence": [
                {"ref": row["evidence"], "revision": row["sha"], "verdict": row["verdict"], "source": "orch ledger"}
                for row in ledger
                if unit["pr"] and unit["sha"] and (row["pr"], row["sha"]) == (unit["pr"], unit["sha"])
            ],
            "branch": unit["branch"] or None,
        }
    return view, []


# --- Inspection -------------------------------------------------------------


def report_exists(ref: str, base: Path) -> bool | None:
    if "://" in ref:
        return None
    try:
        return (base / Path(ref).expanduser()).exists()
    except RuntimeError:  # `~unknownuser/...` has no home directory: show it as a missing report.
        return False


def inspect_run(run_file: Path, snapshot: dict[str, Any] | None, snapshot_error: str | None = None) -> dict[str, Any]:
    """Build the read-only task view for one run. Never writes anything."""
    run_file = run_file.absolute()
    run, gaps = read_run(run_file)
    sources: dict[str, Any] = {
        "run_file": {"path": str(run_file), "ok": run is not None, "read_at": now()},
        "herdr": {"ok": snapshot is not None, "read_at": (snapshot or {}).get("read_at"), "error": snapshot_error},
    }
    if run is None:
        return {"run_id": None, "sources": sources, "data_gaps": gaps, "tasks": []}
    socket = run["endpoint"]["socket"]
    base = run_file.parent
    orch: dict[str, dict[str, Any]] = {}
    if run["orch_store"] is not None:
        orch_dir = (base / run["orch_store"]).absolute()
        orch, orch_gaps = orch_view(orch_dir)
        gaps += orch_gaps
        sources["orch_store"] = {"path": str(orch_dir), "ok": not orch_gaps, "read_at": now()}
    tasks = []
    records = {task["id"]: task for task in run["tasks"]}
    for task_id in [*records, *(unit for unit in orch if unit not in records)]:
        record = records.get(task_id, {"id": task_id, "binding": None, "data_gaps": []})
        view = {
            "id": task_id,
            "title": record.get("title"),
            "repository": record.get("repository"),
            "worktree": record.get("worktree"),
            "binding": record.get("binding"),
            "binding_check": check_binding(record.get("binding"), snapshot, socket),
            "data_gaps": list(record["data_gaps"]),
        }
        if run["orch_store"] is None:
            reports, evidence = record.get("reports", []), record.get("evidence", [])
            view["acceptance"] = record.get("acceptance", "not recorded")
            view["lifecycle"] = {"observed": view["binding_check"].get("agent_status")}
        else:
            unit = orch.get(task_id)
            if unit is None:
                view["data_gaps"].append(f"task {task_id}: no matching orch unit")
                unit = {"reports": [], "evidence": []}
            view["title"] = view["title"] or unit.get("title")
            reports, evidence = unit["reports"], unit["evidence"]
            view["acceptance"] = "not recorded"  # orch has no acceptance field to map.
            view["lifecycle"] = {
                "observed": view["binding_check"].get("agent_status"),
                "orch_state": unit.get("orch_state"),
                "reported_status": unit.get("reported_status"),
            }
        view["reports"] = [{"ref": ref, "exists": report_exists(ref, base)} for ref in reports]
        view["evidence"] = evidence
        if not reports:
            view["data_gaps"].append(f"task {task_id}: no report registered")
        elif any(item["exists"] is False for item in view["reports"]):
            view["data_gaps"].append(f"task {task_id}: report file missing")
        tasks.append(view)
    coordinator = {
        **run["coordinator"],
        "binding_check": check_binding(run["coordinator"]["binding"], snapshot, socket),
    }
    return {
        "run_id": run["run_id"],
        "endpoint": run["endpoint"],
        "updated_at": run["updated_at"],
        "orch_store": run["orch_store"],
        "coordinator": coordinator,
        "sources": sources,
        "data_gaps": gaps,
        "tasks": tasks,
    }


# --- CLI --------------------------------------------------------------------


def all_gaps(run: dict[str, Any] | None, gaps: list[str]) -> list[str]:
    return gaps + [gap for task in (run or {}).get("tasks", []) for gap in task["data_gaps"]]


def load_for_update(path: Path) -> dict[str, Any]:
    run, gaps = read_run(path)
    gaps = all_gaps(run, gaps)
    if run is None or gaps:
        raise UserError("refusing to update invalid run record: " + "; ".join(gaps))
    return run


def checked(run: dict[str, Any]) -> dict[str, Any]:
    """Return the record to store; refuse anything load_for_update would later reject."""
    record = stored(run)
    valid, gaps = validate_run(record)
    gaps = all_gaps(valid, gaps)
    if valid is None or gaps:
        raise UserError("refusing to write invalid run record: " + "; ".join(gaps))
    return record


@contextlib.contextmanager
def update_lock(path: Path) -> Iterator[None]:
    """Serialize read-modify-write of one run record. Inspection and the plugin never take this lock."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    with real.with_name(f".{real.name}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def find_task(run: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in run["tasks"]:
        if task["id"] == task_id:
            return task
    raise UserError(f"task {task_id} not found")


def caller_terminal(socket: str, pane: str) -> str | None:
    """Resolve a pane id to its terminal; a moved pane's launch-time id stays a Herdr alias. None if unknown."""
    herdr = os.environ.get("HERDR_BIN_PATH") or "herdr"
    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only herdr argv; no shell.
            [herdr, "pane", "get", pane],
            env={**os.environ, "HERDR_SOCKET_PATH": socket},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=SNAPSHOT_TIMEOUT,
            check=False,
        )
        terminal = json.loads(result.stdout)["result"]["pane"]["terminal_id"]
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return None
    return terminal if result.returncode == 0 and text(terminal) else None


def require_coordinator(run: dict[str, Any], action: str) -> None:
    if run["orch_store"] is not None:
        raise UserError(f"{action} for orch-backed runs belongs in the orch store, not herdr-run.json")
    pane = os.environ.get("HERDR_PANE_ID")
    if not pane:
        return
    terminal = caller_terminal(run["endpoint"]["socket"], pane)

    def occupies(binding: dict[str, Any]) -> bool:
        return binding["terminal_id"] == terminal if terminal and binding["terminal_id"] else binding["pane_id"] == pane

    if any(occupies(task["binding"]) for task in run["tasks"] if task["binding"]):
        raise UserError(f"{action} is coordinator-only; this pane is bound to a worker task")
    coordinator = run["coordinator"]["binding"]
    # ponytail: an unbound coordinator can't be verified, so only known workers are refused.
    if coordinator and not occupies(coordinator):
        raise UserError(
            f"{action} is coordinator-only; this pane is not the bound coordinator"
            " (after a restart, run `coordinator bind` from the coordinator pane)"
        )


def snapshot_for(socket: str, snapshot_file: str | None) -> dict[str, Any]:
    if snapshot_file:
        return normalize_snapshot(json.loads(Path(snapshot_file).read_text(encoding="utf-8")), socket)
    return live_snapshot(socket)


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.run_file).absolute()
    if not SAFE_ID.fullmatch(args.run_id):
        raise UserError("run id must match " + SAFE_ID.pattern)
    socket = args.socket or os.environ.get("HERDR_SOCKET_PATH")
    if not socket:
        raise UserError("pass --socket or run inside Herdr (HERDR_SOCKET_PATH)")
    pane = args.coordinator_pane or os.environ.get("HERDR_PANE_ID")
    binding = capture_binding(snapshot_for(socket, args.snapshot), pane) if pane else None
    run = {
        "version": VERSION,
        "run_id": args.run_id,
        "endpoint": {"socket": endpoint_socket(socket), "session": args.session},
        "updated_at": now(),
        "orch_store": args.orch_store,
        "coordinator": {"label": args.label, "binding": binding},
        "tasks": [],
    }
    record = checked(run)
    with update_lock(path):
        if path.exists():
            raise UserError(f"{path} already exists; use enroll to register it")
        atomic_write(path, record)
    return {"run_file": str(path), **enroll(path, registry_root(args.registry))}


def command_coordinator(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.run_file).absolute()
    with update_lock(path):
        run = load_for_update(path)
        coordinator = run["coordinator"]
        snapshot = snapshot_for(run["endpoint"]["socket"], args.snapshot)
        coordinator["binding"], warnings = rebind(coordinator["binding"], snapshot, args.pane)
        atomic_write(path, checked(run))
    return {**coordinator, "warnings": warnings} if warnings else coordinator


def command_task(args: argparse.Namespace) -> dict[str, Any]:  # noqa: C901 - one flat branch per task action.
    path = Path(args.run_file).absolute()
    with update_lock(path):
        run = load_for_update(path)
        if args.action == "add":
            if not valid_task_id(args.id):
                raise UserError(TASK_ID_RULE)
            if any(task["id"] == args.id for task in run["tasks"]):
                raise UserError(f"task {args.id} already exists")
            task: dict[str, Any] = {"id": args.id, "title": args.title, "binding": None, "repository": args.repository}
            task |= {"worktree": args.worktree, "reports": [], "acceptance": "not recorded", "evidence": []}
            run["tasks"].append(task)
        else:
            task = find_task(run, args.id)
        warnings: list[str] = []
        if args.action == "bind":
            snapshot = snapshot_for(run["endpoint"]["socket"], args.snapshot)
            task["binding"], warnings = rebind(task["binding"], snapshot, args.pane)
        elif args.action == "report":
            if run["orch_store"] is not None:
                raise UserError("orch-backed runs take reports through `orch inbox push`")
            if args.ref not in task["reports"]:
                task["reports"].append(args.ref)
        elif args.action in ("accept", "reject"):
            require_coordinator(run, args.action)
            task["acceptance"] = "accepted" if args.action == "accept" else "rejected"
        elif args.action == "evidence":
            require_coordinator(run, args.action)
            item = {"ref": args.ref, "revision": args.revision}
            if item not in task["evidence"]:
                task["evidence"].append(item)
        record = checked(run)
        atomic_write(path, record)
    result = find_task(record, args.id)
    return {**result, "warnings": warnings} if warnings else result


def command_inspect(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.run_file).absolute()
    run, _ = read_run(path)
    snapshot, error = None, None
    if run is not None:
        try:
            snapshot = snapshot_for(run["endpoint"]["socket"], args.snapshot)
        except (UserError, OSError, ValueError) as caught:
            error = str(caught)
    return inspect_run(path, snapshot, error)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="herdr_run.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Registry: --registry, else $ZSTACK_HERDR_REGISTRY, else $XDG_STATE_HOME/zstack/herdr/runs "
        "(default ~/.local/state/zstack/herdr/runs). Entries hold pointers only.",
    )
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create herdr-run.json and enroll it")
    init.add_argument("run_file")
    init.add_argument("--run-id", required=True)
    init.add_argument("--socket", help="Herdr endpoint socket (default $HERDR_SOCKET_PATH)")
    init.add_argument("--session", help="named Herdr session label")
    init.add_argument("--coordinator-pane", help="coordinator pane (default $HERDR_PANE_ID)")
    init.add_argument("--label", help="coordinator label")
    init.add_argument("--orch-store", help="orch store directory, relative to the run file")
    init.add_argument("--snapshot", help="read Herdr snapshot JSON from a file instead of `herdr api snapshot`")
    init.add_argument("--registry")
    enroll_parser = commands.add_parser("enroll", help="register an existing run record")
    enroll_parser.add_argument("run_file")
    enroll_parser.add_argument("--registry")
    enroll_parser.add_argument("--replace", action="store_true", help="replace another file's same-ID enrollment")
    runs = commands.add_parser("runs", help="list runs enrolled on an endpoint")
    runs.add_argument("--socket", help="default $HERDR_SOCKET_PATH")
    runs.add_argument("--registry")
    coordinator = commands.add_parser("coordinator", help="coordinator binding updates")
    coordinator_actions = coordinator.add_subparsers(dest="action", required=True)
    bind = coordinator_actions.add_parser("bind", help="bind the coordinator to a live pane")
    bind.add_argument("run_file")
    bind.add_argument("--pane", required=True)
    bind.add_argument("--snapshot")
    task = commands.add_parser("task", help="coordinator task updates (workers never accept, reject, or add evidence)")
    actions = task.add_subparsers(dest="action", required=True)
    specs = {
        "add": "add a task",
        "bind": "bind a task to a live pane",
        "report": "register a report path",
        "accept": "record acceptance (coordinator only)",
        "reject": "record rejection (coordinator only)",
        "evidence": "add a verification evidence ref (coordinator only)",
    }
    for name, summary in specs.items():
        leaf = actions.add_parser(name, help=summary, description=summary)
        leaf.add_argument("run_file")
        leaf.add_argument("id")
        if name == "add":
            leaf.add_argument("--title")
            leaf.add_argument("--repository")
            leaf.add_argument("--worktree")
        if name == "bind":
            leaf.add_argument("--pane", required=True)
            leaf.add_argument("--snapshot")
        if name in ("report", "evidence"):
            leaf.add_argument("ref")
        if name == "evidence":
            leaf.add_argument("--revision", help="tested revision")
    inspect = commands.add_parser("inspect", help="print the read-only task view as JSON")
    inspect.add_argument("run_file")
    inspect.add_argument("--snapshot")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result: Any = command_init(args)
        elif args.command == "enroll":
            result = enroll(Path(args.run_file), registry_root(args.registry), args.replace)
        elif args.command == "runs":
            socket = args.socket or os.environ.get("HERDR_SOCKET_PATH")
            if not socket:
                raise UserError("pass --socket or run inside Herdr (HERDR_SOCKET_PATH)")
            result = enrolled_runs(socket, registry_root(args.registry))
        elif args.command == "coordinator":
            result = command_coordinator(args)
        elif args.command == "task":
            result = command_task(args)
        else:
            result = command_inspect(args)
    except (UserError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
