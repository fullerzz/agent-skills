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


def directory_companion_root(source: dict[str, object]) -> str | None:
    root = source.get("path")
    if source.get("source") != "directory" or not isinstance(root, str) or not os.path.isabs(root):
        return None
    plugins = load_mode(os.path.join(root, ".claude-plugin/marketplace.json")).get("plugins")
    if not isinstance(plugins, list):
        return None
    for plugin in plugins:
        if isinstance(plugin, dict) and plugin.get("name") == "herdr-zstack":
            relative = plugin.get("source")
            if isinstance(relative, str) and relative.startswith("./") and ".." not in relative.split("/"):
                return os.path.join(root, relative)
    return None


def companion_skill(host: str) -> str | None:
    """Resolve one installed hc companion; never guess between cached versions."""
    from pathlib import Path

    home = Path.home()
    candidates: list[Path] = []
    if host == "codex":
        base = Path(os.environ.get("CODEX_HOME") or home / ".codex")
        candidates = list(base.glob("plugins/cache/*/herdr-zstack/*/skills/hc-workflow/SKILL.md"))
        candidates.append(home / ".agents/skills/hc-workflow/SKILL.md")
    elif host == "claude":
        base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
        candidates.append(base / "skills/hc-workflow/SKILL.md")
        installed = load_mode(str(base / "plugins/installed_plugins.json")).get("plugins", {})
        markets = load_mode(str(base / "plugins/known_marketplaces.json"))
        if isinstance(installed, dict):
            for name, entries in installed.items():
                if not name.startswith("herdr-zstack@") or not isinstance(entries, list):
                    continue
                market = markets.get(name.split("@", 1)[1], {})
                source = market.get("source", {}) if isinstance(market, dict) else {}
                if not isinstance(source, dict):
                    source = {}
                local_root = directory_companion_root(source)
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    root = local_root or entry.get("installPath")
                    if isinstance(root, str) and os.path.isabs(root):
                        candidates.append(Path(root) / "skills/hc-workflow/SKILL.md")
    paths = {str(path.resolve()) for path in candidates if path.is_file()}
    return paths.pop() if len(paths) == 1 else None


def build_context(host: str, session_id: str, data_dir: str, source: str) -> tuple[str, str | None]:
    """Restore scoped state and render controls without emitting output."""
    if host not in ("codex", "claude", "hermes"):
        raise ValueError("Invalid host")
    if source not in ("startup", "resume", "clear", "compact", "fork"):
        raise ValueError("Invalid context source")
    path = state_path(data_dir, session_id)
    active, execution, clear_error = restore_state(path, source)
    helper = os.path.realpath(__file__)
    # A control may rerun outside a sandbox, so emit the base interpreter fixed at hook start: a working-directory
    # .venv that uv chose (symlinked or copied) stays writable by sandboxed commands. This also skips blocked shims.
    # A .venv already present at hook start has run this hook unsandboxed, so it gains nothing new here.
    interpreter = getattr(sys, "_base_executable", None) or sys.executable
    if not interpreter:
        raise ValueError("Python executable unavailable")
    # One template per shell keeps the context inside Codex's 4000-character limit with real paths.
    arguments = [
        os.path.realpath(interpreter),
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
        # Claude Code's Bash sandbox write-protects plugin data under ~/.claude, and allowWrite cannot reopen it.
        "If a sandbox blocks a control (Operation not permitted, Permission denied, or Read-only file system), "
        "request one unsandboxed rerun through the host's permission flow. If refused or unavailable, stop retrying "
        "controls this session and give the user the command to run "
        f"{'with the ! prefix or outside Claude Code' if host == 'claude' else 'outside the agent'}. "
        "Until then the selection is conversational only; a blocked Disable leaves stored activation that resume "
        "restores, so keep the opt-out in resume notes.\n"
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
        companion = companion_skill(host)
        context += "\nHerdr execution was explicitly enabled for this session. "
        if companion:
            context += f"Read {companion} (herdr-zstack:hc-workflow) alongside the selected playbook. "
        else:
            context += (
                "Capability gap: herdr-zstack:hc-workflow is missing or ambiguous; "
                "resolve it through the host catalog. "
            )
        context += (
            "No legacy Herdr fallback. Native hc requires HC_TERMINAL_ID, a resolved caller and an answering core; "
            "HERDR_ENV alone is insufficient. Do not dispatch until the companion's read-only preflight passes. "
            "Never copy these controls into children. Later user instructions override stored state."
        )
    else:
        context += "\nHerdr execution is not enabled."
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
        import errno

        # The remedy lives only in trusted hook context; tool output must not instruct a sandbox bypass.
        blocked = isinstance(error, OSError) and error.errno in (errno.EPERM, errno.EACCES, errno.EROFS)
        remedy = "If a sandbox blocked this write, follow this session's z-mode guidance for blocked controls.\n"
        parser.exit(1, f"z-mode state not changed: {error}\n{remedy if blocked else ''}")


if __name__ == "__main__":
    main()
