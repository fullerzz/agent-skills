"""Optional metadata-only hook recorder. Capture times are not execution order."""

# Low-level paths preserve lexical ancestor checks and O_NOFOLLOW; resolve would hide symlinks.
# ruff: noqa: PTH100, PTH102, PTH105, PTH108, PTH110, PTH114, PTH117, PTH118, PTH206, PTH208

import contextlib
import datetime
import json
import os
import re
import stat
import sys
import uuid

SCHEMA_VERSION = 1
MAX_INPUT = 262144
MAX_EVENTS = 10000
MAX_EVENT_BYTES = 4096
ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
KINDS = {
    "SessionStart",
    "SessionEnd",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "UserPromptExpansion",
    "PreCompact",
    "PostCompact",
}
LIMITS = [
    "The 10,000-event soft cap may be exceeded by simultaneous hooks; capped captures stop and warn.",
    "User-only file modes are requested; Windows permissions depend on host ACLs.",
    "Only enabled hook invocations are observed; missing hooks and disabled periods are unknown.",
    "Capture timestamps do not establish execution ordering.",
    "No prompts, tool inputs, results, commands, paths, or transcript content are collected.",
    "Unpaired tool events may reflect missing observations; coverage is never complete.",
    "Paired tool IDs lacking actor or turn IDs are ambiguous; their identities remain unresolved.",
]


def warn() -> None:
    print("zstack xray: metadata capture unavailable; continuing", file=sys.stderr)


def identifier(value: object) -> str | None:
    return value if isinstance(value, str) and ID.fullmatch(value) else None


def directory(data_dir: str, host: str, session_id: str, create: bool = False) -> str:
    if host not in ("codex", "claude") or not identifier(session_id):
        raise ValueError("invalid scope")
    if not isinstance(data_dir, str) or not os.path.isabs(data_dir):
        raise ValueError("invalid directory")
    path = os.path.abspath(data_dir)
    # Check every ancestor as well as our descendants; never follow symlinks.
    drive, tail = os.path.splitdrive(path)
    components = [*tail.split(os.sep)[1:], "xray", host, session_id, "events"]
    current = drive + os.sep
    for part in components:
        current = os.path.join(current, part)
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if not create:
                continue
            with contextlib.suppress(FileExistsError):
                os.mkdir(current, 0o700)
            mode = os.lstat(current).st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("symlink directory")
        if not stat.S_ISDIR(mode):
            raise ValueError("not directory")
    return current


def base(host: str, session_id: str, kind: str, status: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": host,
        "session_id": session_id,
        "kind": kind,
        "status": status,
    }


def write_record(data_dir: str, record: dict[str, object]) -> None:
    events = directory(data_dir, record["host"], record["session_id"], True)
    # Soft admission cap: simultaneous hooks may exceed it by their concurrency.
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if len([name for name in os.listdir(events) if name.endswith(".json")]) >= MAX_EVENTS:
        marker_path = os.path.join(events, ".cap-reached")
        if os.path.islink(marker_path):
            raise ValueError("symlink marker")
        marker = os.open(marker_path, os.O_WRONLY | os.O_CREAT | nofollow, 0o600)
        os.close(marker)
        raise ValueError("capture cap")
    encoded = json.dumps(record, separators=(",", ":")).encode()
    if len(encoded) > MAX_EVENT_BYTES:
        raise ValueError("event too large")
    temporary = os.path.join(events, "." + record["event_id"] + ".tmp")
    final = os.path.join(events, record["event_id"] + ".json")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
        if os.path.lexists(final):
            raise ValueError("existing event")
        os.replace(temporary, final)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def normalize(event: object, host: str) -> dict[str, object]:  # noqa: C901 - Exhaustive metadata allowlist.
    if not isinstance(event, dict) or not identifier(event.get("session_id")):
        raise ValueError("invalid event")
    kind = event.get("hook_event_name")
    if kind not in KINDS:
        raise ValueError("unsupported event")
    status = {"PreToolUse": "started", "PostToolUse": "returned", "PostToolUseFailure": "failed"}.get(kind, "unknown")
    record = base(host, event["session_id"], kind, status)
    for key in ("agent_id", "turn_id", "tool_use_id"):
        if identifier(event.get(key)):
            record[key] = event[key]
    if kind in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        tool = event.get("tool_name")
        if isinstance(tool, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", tool):
            record["tool_name"] = tool
        record["attribution"] = "unknown"
        inputs = event.get("tool_input")
        if tool == "Skill" and isinstance(inputs, dict):
            skill = inputs.get("skill")
            if isinstance(skill, str) and re.fullmatch(r"zstack:[A-Za-z0-9_-]{1,64}", skill):
                record["attribution"] = "zstack"
                record["skill_name"] = skill
    if kind == "UserPromptExpansion" and event.get("command_source") == "plugin":
        command = event.get("command_name")
        if isinstance(command, str) and re.fullmatch(r"zstack:[A-Za-z0-9_-]{1,64}", command):
            record["attribution"] = "zstack"
            record["skill_name"] = command
    return record


def record_internal(
    host: str, session_id: str, data_dir: str, action: str, outcome: str, *, source: str | None = None
) -> bool:
    """Fail-open API for session_start and explicit enable/disable controls."""
    if os.environ.get("ZSTACK_XRAY") != "1":
        return False
    try:
        statuses = {
            "context_emitted": "returned",
            "clear_state_failed": "failed",
            "enabled": "returned",
            "disabled": "returned",
            "state_change_failed": "failed",
            "started": "started",
            "returned": "returned",
            "failed": "failed",
            "unknown": "unknown",
        }
        if action not in ("session_start", "enable", "disable") or outcome not in statuses:
            raise ValueError("invalid internal event")
        record = base(host, session_id, action, statuses[outcome])
        record["attribution"] = "zstack"
        record["outcome"] = outcome
        if action == "session_start" and source in {"startup", "resume", "clear", "compact", "fork"}:
            record["source"] = source
        write_record(data_dir, record)
        return True
    except Exception:  # noqa: BLE001 - Optional hooks must fail open at this boundary.
        warn()
        return False


def read_records(host: str, session_id: str, data_dir: str) -> dict[str, object]:  # noqa: C901 - Validate each allowed schema field.
    events = directory(data_dir, host, session_id)
    records, invalid = [], 0
    capped = False
    interrupted = 0
    try:
        names = sorted(os.listdir(events))
    except FileNotFoundError:
        names = []
    if names:
        capped = ".cap-reached" in names
        interrupted = sum(name.endswith(".tmp") for name in names)
        for name in names:
            if not name.endswith(".json"):
                continue
            try:
                if not re.fullmatch(r"[0-9a-f-]{36}\.json", name):
                    raise ValueError("filename")
                record_path = os.path.join(events, name)
                if os.path.islink(record_path):
                    raise ValueError("symlink file")
                fd = os.open(record_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as stream:
                    raw = stream.read(MAX_EVENT_BYTES + 1)
                if len(raw) > MAX_EVENT_BYTES:
                    raise ValueError("size")
                record = json.loads(raw)
                allowed = {
                    "schema_version",
                    "event_id",
                    "captured_at",
                    "host",
                    "session_id",
                    "kind",
                    "status",
                    "agent_id",
                    "turn_id",
                    "tool_use_id",
                    "tool_name",
                    "attribution",
                    "skill_name",
                    "outcome",
                    "source",
                }
                if (
                    not isinstance(record, dict)
                    or set(record) - allowed
                    or record.get("schema_version") != 1
                    or record.get("host") != host
                    or record.get("session_id") != session_id
                    or record.get("event_id") + ".json" != name
                ):
                    raise ValueError("schema")
                # Rebuild from known metadata to keep manually corrupted data private.
                normalized = (
                    normalize({"hook_event_name": record["kind"], **record}, host)
                    if record["kind"] in KINDS
                    else base(host, session_id, record["kind"], "unknown")
                )
                if record["kind"] not in KINDS | {"session_start", "enable", "disable"} or record["status"] not in {
                    "started",
                    "returned",
                    "failed",
                    "unknown",
                }:
                    raise ValueError("kind/status")
                normalized.update({key: record[key] for key in ("event_id", "captured_at", "status")})
                datetime.datetime.fromisoformat(record["captured_at"])
                if record.get("attribution") == "zstack":
                    normalized["attribution"] = "zstack"
                if isinstance(record.get("skill_name"), str) and re.fullmatch(
                    r"zstack:[A-Za-z0-9_-]{1,64}", record["skill_name"]
                ):
                    normalized["skill_name"] = record["skill_name"]
                if record.get("outcome") in {
                    "context_emitted",
                    "clear_state_failed",
                    "enabled",
                    "disabled",
                    "state_change_failed",
                    "started",
                    "returned",
                    "failed",
                    "unknown",
                }:
                    normalized["outcome"] = record["outcome"]
                if record["kind"] == "session_start" and record.get("source") in {
                    "startup",
                    "resume",
                    "clear",
                    "compact",
                    "fork",
                }:
                    normalized["source"] = record["source"]
                records.append(normalized)
            except (OSError, ValueError, TypeError, KeyError):
                invalid += 1
    pairs = {}
    for record in records:
        if record.get("tool_use_id"):
            pair = (record.get("agent_id"), record.get("turn_id"), record["tool_use_id"])
            pairs.setdefault(pair, set()).add(record["status"])
    # A shared absent identity is not evidence of a shared actor or turn.
    ambiguous = sum(
        (actor is None or turn is None) and "started" in statuses and bool(statuses & {"returned", "failed"})
        for (actor, turn, _tool_id), statuses in pairs.items()
    )
    unpaired = sum(
        not ("started" in statuses and bool(statuses & {"returned", "failed"})) for statuses in pairs.values()
    )
    return {
        "schema_version": 1,
        "host": host,
        "session_id": session_id,
        "records": sorted(records, key=lambda item: (item["captured_at"], item["event_id"])),
        "coverage": {
            "complete": False,
            "limits": LIMITS,
            "invalid_files": invalid,
            "interrupted_files": interrupted,
            "cap_reached": capped,
            "unpaired_tool_ids": unpaired,
            "ambiguous_tool_ids": ambiguous,
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=("codex", "claude"))
    parser.add_argument("--read", action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    try:
        if args.read:
            print(json.dumps(read_records(args.host, args.session_id, args.data_dir)))
        elif os.environ.get("ZSTACK_XRAY") == "1":
            raw = sys.stdin.buffer.read(MAX_INPUT + 1)
            if len(raw) > MAX_INPUT:
                raise ValueError("input cap")
            event = json.loads(raw)
            data = os.environ["CLAUDE_PLUGIN_DATA" if args.host == "claude" else "PLUGIN_DATA"]
            write_record(data, normalize(event, args.host))
    except Exception:  # noqa: BLE001 - Optional hooks must fail open at this boundary.
        warn()
        if args.read:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "records": [],
                        "coverage": {"complete": False, "unavailable": True, "limits": LIMITS},
                    }
                )
            )


if __name__ == "__main__":
    main()
