"""Shared host context and session-scoped mode and execution controls."""

# Keep measured startup savings: avoid pathlib/contextlib imports on the hook path.
# ruff: noqa: PTH103, PTH105, PTH108, PTH113, PTH117, PTH118, PTH120, PTH122, PTH123, SIM105

import json
import os
import re
import shlex
import sys


def state_path(data_dir: str, session_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("Invalid session id")
    if not os.path.isabs(data_dir):
        raise ValueError("Plugin data directory must be absolute")
    return os.path.join(data_dir, "z-mode", session_id + ".json")


def execution_path(path: str) -> str:
    # A separate marker keeps each control a single-file write, so parallel controls cannot drop each other.
    return os.path.splitext(path)[0] + ".herdr"


def load_mode(path: str) -> dict[str, object]:
    try:
        with open(path, encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def read_state(path: str) -> tuple[bool, str]:
    state = load_mode(path)
    # Earlier releases stored execution in the mode JSON; honor it until a control migrates it.
    herdr = state.get("execution") == "herdr" or os.path.isfile(execution_path(path))
    return state.get("active") is True, "herdr" if herdr else "native"


def unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def write_active(path: str) -> None:
    import tempfile

    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as file:
            temporary = file.name
            json.dump({"active": True}, file)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            unlink(temporary)


def migrate_legacy(path: str) -> None:
    # Move a legacy execution field into the marker first, so an interrupted migration still reads as Herdr.
    state = load_mode(path)
    if "execution" not in state:
        return
    if state["execution"] == "herdr":
        open(execution_path(path), "a").close()
    if state.get("active") is True:
        write_active(path)
    else:
        unlink(path)


def set_active(path: str, active: bool) -> None:
    # Re-selecting the mode preserves execution; stopping it clears both preferences.
    if not active:
        unlink(path)
        unlink(execution_path(path))
        return
    migrate_legacy(path)
    write_active(path)


def set_execution(path: str, execution: str) -> None:
    if execution not in ("herdr", "native"):
        raise ValueError("Invalid execution selection")
    migrate_legacy(path)
    if execution == "native":
        unlink(execution_path(path))
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(execution_path(path), "a").close()


def restore_state(path: str, source: str) -> tuple[bool, str, str | None]:
    if source != "clear":
        return (*read_state(path), None)
    try:
        set_active(path, False)
    except OSError:
        return (
            False,
            "native",
            (
                "z-mode state could not be removed on clear. Mode and Herdr execution are inactive, "
                "but a later resume may see stale stored activation. Retry Disable "
                "and preserve this opt-out in resume notes; user opt-out always takes precedence."
            ),
        )
    return False, "native", None


def control_command(arguments: list[str], shell: str) -> str:
    if shell == "powershell":
        return "& " + " ".join(
            "'" + re.sub("['\u2018\u2019]", lambda match: match[0] * 2, argument) + "'" for argument in arguments
        )
    return shlex.join(arguments)


def record_xray(
    host: str | None, session_id: str, data_dir: str, action: str, outcome: str, *, source: str | None = None
) -> None:
    if host is None or os.environ.get("ZSTACK_XRAY") != "1":
        return
    try:
        import runpy

        recorder = runpy.run_path(os.path.join(os.path.dirname(os.path.realpath(__file__)), "xray.py"))
        if source is None:
            recorder["record_internal"](host, session_id, data_dir, action, outcome)
        else:
            recorder["record_internal"](host, session_id, data_dir, action, outcome, source=source)
    except Exception:  # noqa: BLE001 - Optional recorder failures must never alter host execution.
        print("zstack xray: metadata capture unavailable; continuing", file=sys.stderr)


def xray_context(host: str, session_id: str, data_dir: str, helper: str, budget: int) -> str:
    read_arguments = [
        "uv",
        "run",
        "--no-project",
        "--no-config",
        "python",
        "-I",
        "-S",
        os.path.join(os.path.dirname(helper), "xray.py"),
        "--read",
        f"--host={host}",
        f"--session-id={session_id}",
        "--data-dir",
        data_dir,
    ]
    recording_context = (
        f"\nOptional xray recording is enabled for host {host}, session {session_id}, "
        f"plugin data {data_dir}. It does not activate z-mode. Read this session's metadata only "
        "when requested, using the command matching your shell:\n"
        f"POSIX sh Read xray: {control_command(read_arguments, 'posix')}\n"
        f"PowerShell Read xray: {control_command(read_arguments, 'powershell')}"
    )
    if len(recording_context) > budget:
        recording_context = (
            f"\nOptional xray recording is enabled for host {host}, session {session_id}; "
            "it does not activate z-mode. On an explicit xray-session request, use the skill's "
            "recorded-events reference. The data directory and session ID are the same as the "
            "controls above; the read helper is their sibling xray.py."
        )
    return recording_context if len(recording_context) <= budget else ""


def build_context(host: str, session_id: str, data_dir: str, source: str) -> tuple[str, str | None]:
    """Restore scoped state and render controls without emitting output or recording."""
    if host not in ("codex", "claude", "hermes"):
        raise ValueError("Invalid host")
    if source not in ("startup", "resume", "clear", "compact", "fork"):
        raise ValueError("Invalid context source")
    path = state_path(data_dir, session_id)
    active, execution, clear_error = restore_state(path, source)
    helper = os.path.realpath(__file__)
    # One template per shell keeps the context inside Codex's 4000-character limit with real paths.
    arguments = [
        "uv",
        "run",
        "--no-project",
        "--no-config",
        "python",
        "-I",
        "-S",
        helper,
        f"--host={host}",
        f"--session-id={session_id}",
        "--data-dir",
        data_dir,
        "ACTION",
    ]
    context = (
        "zstack provides engineering skills; respect invocation policy. "
        "Installation activates neither z-mode nor Herdr. "
        "These controls supersede any controls inherited from a parent or forked conversation; "
        "never run another session's controls. Parent activation does not activate a fork. "
        "Only explicit selection/opt-out permits controls: Enable selects z-mode; Disable clears both; "
        "Herdr selects execution only; Native clears execution only. Preferences do not control processes. "
        "In the executing shell's control, replace only the final argument ACTION with enable, disable, herdr, "
        "or native; leave all other arguments unchanged, including ACTION inside paths or session IDs:\n"
        f"POSIX sh control: {control_command(arguments, 'posix')}\n"
        f"PowerShell control: {control_command(arguments, 'powershell')}\n"
        "When active z-mode stops or yields to another style, run Disable and record opt-out in resume notes; "
        "Herdr selected without z-mode stays until Native. Later user instructions override stored state. "
        "No added authority for delegation, commits, publication, messages, or tracker writes.\n"
    )
    if active:
        skill = os.path.join(os.path.dirname(os.path.dirname(helper)), "skills/z-mode/SKILL.md")
        context += (
            f"z-mode was explicitly enabled for this session. Read {skill} and "
            "continue its engineering style unless a later user instruction opts out."
        )
    elif clear_error:
        context += "z-mode is inactive for this cleared context."
    else:
        context += "No stored z-mode activation exists for this session."
    if execution == "herdr":
        skill = os.path.join(os.path.dirname(os.path.dirname(helper)), "skills/herdr-workflow/SKILL.md")
        context += (
            f"\nHerdr execution was explicitly enabled for this session. Read {skill}; "
            "apply it alongside the selected playbook. Later user instructions override stored state."
        )
    else:
        context += "\nHerdr execution is not enabled."
    if os.environ.get("ZSTACK_XRAY") == "1":
        context += xray_context(host, session_id, data_dir, helper, 4000 - len(context) - len(clear_error or "") - 1)
    if clear_error:
        context += "\n" + clear_error
    return context, clear_error


def session_start(host: str) -> None:
    try:
        event = json.loads(sys.stdin.read(65536))
        if event.get("hook_event_name") != "SessionStart":
            return
        session_id = event["session_id"]
        data_dir = os.environ["CLAUDE_PLUGIN_DATA" if host == "claude" else "PLUGIN_DATA"]
        context, clear_error = build_context(host, session_id, data_dir, event["source"])
    except (ValueError, TypeError, AttributeError, KeyError):
        return
    hook_output = {"hookEventName": "SessionStart", "additionalContext": context}
    output: dict[str, object] = {"hookSpecificOutput": hook_output}
    if clear_error:
        output["systemMessage"] = clear_error
    print(json.dumps(output))
    record_xray(
        host,
        session_id,
        data_dir,
        "session_start",
        "clear_state_failed" if clear_error else "context_emitted",
        source=event["source"],
    )


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("--host=codex", "--host=claude"):
        session_start(sys.argv[1].split("=", 1)[1])
        return
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable", "herdr", "native"))
    parser.add_argument("--host", choices=("codex", "claude", "hermes"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    try:
        path = state_path(args.data_dir, args.session_id)
        if args.action in ("enable", "disable"):
            set_active(path, args.action == "enable")
        else:
            set_execution(path, args.action)
    except (ValueError, OSError) as error:
        record_xray(args.host, args.session_id, args.data_dir, args.action, "state_change_failed")
        parser.exit(1, f"z-mode state not changed: {error}\n")
    record_xray(
        args.host,
        args.session_id,
        args.data_dir,
        args.action,
        "enabled" if args.action in ("enable", "herdr") else "disabled",
    )


if __name__ == "__main__":
    main()
