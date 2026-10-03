"""Codex SessionStart context and explicit, session-scoped z-mode controls."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile


def state_path(data_dir, session_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("Invalid session id")
    data_dir = Path(data_dir)
    if not data_dir.is_absolute():
        raise ValueError("Plugin data directory must be absolute")
    return data_dir / "z-mode" / (session_id + ".json")


def set_active(path, active):
    if not active:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        json.dump({"active": True}, file)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def session_start():
    try:
        event = json.loads(sys.stdin.read(65536))
        if event.get("hook_event_name") != "SessionStart":
            return
        if event.get("source") not in ("startup", "resume", "clear", "compact"):
            return
        session_id = event["session_id"]
        data_dir = os.environ["PLUGIN_DATA"]
        path = state_path(data_dir, session_id)
    except (ValueError, TypeError, AttributeError, KeyError):
        return

    clear_error = None
    if event["source"] == "clear":
        try:
            set_active(path, False)
        except OSError:
            clear_error = (
                "z-mode state could not be removed on clear. This session is inactive, "
                "but a later resume may see stale stored activation. Retry Disable "
                "and preserve this opt-out in resume notes; user opt-out always takes precedence."
            )
    try:
        active = json.loads(path.read_text()).get("active") is True
    except (OSError, ValueError, AttributeError):
        active = False
    if event["source"] == "clear":
        active = False
    helper = str(Path(__file__).resolve())
    controls = {}
    for action in ("enable", "disable"):
        controls[action] = shlex.join([
            "uv", "run", "--no-project", "python", helper, action,
            "--session-id", session_id, "--data-dir", data_dir,
        ])
    context = (
        "The zstack plugin provides engineering skills. Select only skills whose "
        "invocation policy permits the current request. Installation does not enable z-mode. "
        "These controls apply only to this session; use them only when the user "
        "explicitly selects z-mode or opts out/switches style:\n"
        f"Enable: {controls['enable']}\nDisable: {controls['disable']}\n"
        "On stop z-mode or another selected style, disable before continuing and "
        "record the opt-out in resume notes. Hook state is a reminder, never authority "
        "to override a later user instruction. Installation does not authorize "
        "delegation, commits, publication, messages, or tracker writes.\n"
    )
    if active:
        skill = Path(__file__).resolve().parents[1] / "skills/z-mode/SKILL.md"
        context += (
            f"z-mode was explicitly enabled for this session. Read {skill} and "
            "continue its engineering style unless a later user instruction opts out."
        )
    elif clear_error:
        context += "z-mode is inactive for this cleared context."
    else:
        context += "No stored z-mode activation exists for this session."
    output = {"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": context,
    }}
    if clear_error:
        output["systemMessage"] = clear_error
        output["hookSpecificOutput"]["additionalContext"] += "\n" + clear_error
    print(json.dumps(output))


def main():
    if len(sys.argv) == 1:
        session_start()
        return
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
