"""Shared host context and explicit, session-scoped z-mode controls."""

# Keep measured startup savings: avoid pathlib/contextlib imports on the hook path.
# ruff: noqa: PTH103, PTH105, PTH108, PTH117, PTH118, PTH120, PTH123, SIM105

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


def set_active(path: str, active: bool) -> None:
    if not active:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return

    import tempfile

    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as file:
        temporary = file.name
        json.dump({"active": True}, file)
    try:
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def restore_state(path: str, source: str) -> tuple[bool, str | None]:
    clear_error = None
    if source == "clear":
        try:
            set_active(path, False)
        except OSError:
            clear_error = (
                "z-mode state could not be removed on clear. This session is inactive, "
                "but a later resume may see stale stored activation. Retry Disable "
                "and preserve this opt-out in resume notes; user opt-out always takes precedence."
            )
    active = False
    if source != "clear":
        try:
            with open(path, encoding="utf-8") as state:
                active = json.load(state).get("active") is True
        except (OSError, ValueError, AttributeError):
            pass
    return active, clear_error


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
    active, clear_error = restore_state(path, source)
    helper = os.path.realpath(__file__)
    controls: dict[str, dict[str, str]] = {"posix": {}, "powershell": {}}
    for action in ("enable", "disable"):
        arguments = [
            "uv",
            "run",
            "--no-project",
            "--no-config",
            "python",
            "-I",
            "-S",
            helper,
            action,
            f"--host={host}",
            f"--session-id={session_id}",
            "--data-dir",
            data_dir,
        ]
        for shell, commands in controls.items():
            commands[action] = control_command(arguments, shell)
    context = (
        "The zstack plugin provides engineering skills. Use only skills whose "
        "invocation policy permits the current request. Installation does not enable z-mode. "
        "These controls supersede any controls inherited from a parent or forked conversation; "
        "never run another session's controls. Parent activation does not activate a fork. "
        "These controls apply only to this session; use them only when the user "
        "explicitly selects z-mode or opts out/switches style:\n"
        "Use the variant matching the shell executing the control.\n"
        f"POSIX sh Enable: {controls['posix']['enable']}\nPOSIX sh Disable: {controls['posix']['disable']}\n"
        f"PowerShell Enable: {controls['powershell']['enable']}\n"
        f"PowerShell Disable: {controls['powershell']['disable']}\n"
        "On stop z-mode or another selected style, disable before continuing and "
        "record the opt-out in resume notes. Hook state is a reminder, never authority "
        "to override a later user instruction. Installation does not authorize "
        "delegation, commits, publication, messages, or tracker writes.\n"
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
    parser.add_argument("action", choices=("enable", "disable"))
    parser.add_argument("--host", choices=("codex", "claude", "hermes"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    try:
        path = state_path(args.data_dir, args.session_id)
        set_active(path, args.action == "enable")
    except (ValueError, OSError) as error:
        record_xray(args.host, args.session_id, args.data_dir, args.action, "state_change_failed")
        parser.exit(1, f"z-mode state not changed: {error}\n")
    record_xray(
        args.host, args.session_id, args.data_dir, args.action, "enabled" if args.action == "enable" else "disabled"
    )


if __name__ == "__main__":
    main()
