"""Codex and Claude Code SessionStart context and explicit, session-scoped z-mode controls."""

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


def session_start(host: str) -> None:
    try:
        event = json.loads(sys.stdin.read(65536))
        if event.get("hook_event_name") != "SessionStart":
            return
        if event.get("source") not in ("startup", "resume", "clear", "compact", "fork"):
            return
        session_id = event["session_id"]
        data_dir = os.environ["CLAUDE_PLUGIN_DATA" if host == "claude" else "PLUGIN_DATA"]
        path = state_path(data_dir, session_id)
    except (ValueError, TypeError, AttributeError, KeyError):
        return

    active, clear_error = restore_state(path, event["source"])
    helper = os.path.realpath(__file__)
    controls = {"posix": {}, "powershell": {}}
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
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    if clear_error:
        output["systemMessage"] = clear_error
        output["hookSpecificOutput"]["additionalContext"] += "\n" + clear_error
    print(json.dumps(output))


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("--host=codex", "--host=claude"):
        session_start(sys.argv[1].split("=", 1)[1])
        return
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    try:
        path = state_path(args.data_dir, args.session_id)
        set_active(path, args.action == "enable")
    except (ValueError, OSError) as error:
        parser.exit(1, f"z-mode state not changed: {error}\n")


if __name__ == "__main__":
    main()
