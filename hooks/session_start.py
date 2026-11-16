"""Shared host context and session-scoped mode and execution controls."""

# Keep measured startup savings: avoid pathlib/contextlib imports on the hook path.
# ruff: noqa: PTH103, PTH109, PTH111, PTH112, PTH116, PTH105, PTH108, PTH113, PTH117, PTH118, PTH120, PTH122, PTH123, SIM105

import json
import os
import re
import shlex
import sys
from typing import Any


def state_path(data_dir: str, session_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        raise ValueError("Invalid session id")
    if not os.path.isabs(data_dir):
        raise ValueError("Plugin data directory must be absolute")
    return os.path.join(data_dir, "z-mode", session_id + ".json")


def execution_path(path: str, legacy: str | None = None) -> str:
    # One atomic execution record stays separate from mode activation.
    return os.path.splitext(path)[0] + ("." + legacy if legacy else ".execution.json")


def load_mode(path: str) -> dict[str, object]:
    try:
        with open(path, encoding="utf-8") as file:
            state = json.load(file)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def read_execution(path: str) -> str | None:
    selection = execution_path(path)
    if os.path.lexists(selection):
        value = load_mode(selection).get("execution")
        # Corrupt explicit state must not re-enter automatic selection.
        return "herdr" if value == "herdr" else "native"
    if os.path.isfile(execution_path(path, "native")):
        return "native"
    if os.path.isfile(execution_path(path, "herdr")) or load_mode(path).get("execution") == "herdr":
        return "herdr"
    return None


def read_state(path: str) -> tuple[bool, str]:
    return load_mode(path).get("active") is True, read_execution(path) or "native"


def unlink(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def write_state(path: str, state: dict[str, object]) -> None:
    import tempfile

    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as file:
            temporary = file.name
            json.dump(state, file)
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
        open(execution_path(path, "herdr"), "a").close()
    if state.get("active") is True:
        write_state(path, {"active": True})
    else:
        unlink(path)


class StateLock:
    """Serialize short state mutations without leaving another preference file."""

    def __init__(self, path: str) -> None:
        self.directory = os.path.dirname(path)
        self.fd: int | None = None

    def __enter__(self) -> "StateLock":
        os.makedirs(self.directory, exist_ok=True)
        if os.name == "posix":
            import fcntl

            self.fd = os.open(self.directory, os.O_RDONLY)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX)
            except OSError:
                os.close(self.fd)
                self.fd = None
                raise
        return self

    def __exit__(self, *args: object) -> None:
        if self.fd is not None:
            os.close(self.fd)


def set_active(path: str, active: bool) -> None:
    # No directory creation is needed for an already absent Disable.
    if not active and not os.path.isdir(os.path.dirname(path)):
        return
    with StateLock(path):
        _set_active(path, active)


def _set_active(path: str, active: bool) -> None:
    # Re-selecting the mode preserves execution; stopping it clears both preferences.
    if not active:
        unlink(path)
        unlink(execution_path(path))
        unlink(execution_path(path, "herdr"))
        unlink(execution_path(path, "native"))
        return
    migrate_legacy(path)
    write_state(path, {"active": True})


def set_execution(path: str, execution: str) -> None:
    if execution not in ("herdr", "native"):
        raise ValueError("Invalid execution selection")
    with StateLock(path):
        migrate_legacy(path)
        write_state(execution_path(path), {"execution": execution})


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
                f"but a later resume may see stale stored activation. Stored state: {json.dumps(stored_state(path))}. "
                "Follow the host approval flow for Disable "
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


def bootstrap_root(host: str, metadata: object) -> str:
    """Locate the launcher; the companion owns full installation validation."""
    roots = set()
    if host == "codex" and isinstance(metadata, dict):
        base = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
        for entry in metadata["installed"]:
            if entry.get("name") == "herdr-zstack" and entry.get("installed") is True and entry.get("enabled") is True:
                market, version = entry["marketplaceName"], entry["version"]
                if not all(
                    isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", v) for v in (market, version)
                ):
                    raise ValueError("Invalid companion installation identity")
                roots.add(os.path.join(base, "plugins/cache", market, "herdr-zstack", version))
    elif host == "claude" and isinstance(metadata, list):
        for entry in metadata:
            if str(entry.get("id", "")).startswith("herdr-zstack@") and entry.get("enabled") is True:
                if (
                    entry.get("scope") in ("project", "local")
                    and os.path.realpath(entry.get("projectPath", "")) != os.getcwd()
                ):
                    continue
                roots.add(entry.get("readFromFolder") or entry["installPath"])
    else:
        raise ValueError("Invalid host plugin listing")
    root = next(iter(roots), None)
    if len(roots) != 1 or not isinstance(root, str) or not os.path.isabs(root):
        raise ValueError("Missing, ambiguous or non-absolute companion root")
    return os.path.realpath(root)


def validate_probe(report: object, code: int, root: str, terminal: str) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("Invalid preflight report")
    for key in ("session", "companion", "bootstrap", "probe"):
        if key in report and not isinstance(report[key], dict):
            raise ValueError(f"Invalid preflight {key} section")
    companion = report.get("companion", {})
    if companion.get("status") == "supported" and companion.get("path") != root:
        raise ValueError("Preflight companion path does not match the selected launcher")
    session = report.get("session", {}).get("status")
    if code == 0:
        if (
            session != "supported"
            or report.get("companion", {}).get("status") != "supported"
            or report.get("bootstrap", {}).get("status") != "supported"
            or report["companion"].get("path") != root
            or report["session"].get("terminalId") != terminal
        ):
            raise ValueError("Preflight did not verify this companion and caller")
    elif not ((code == 1 and session == "unavailable") or (code == 2 and session == "untested")):
        raise ValueError("Preflight exit status and report disagree")
    return report


def probe_companion(host: str) -> dict[str, Any]:
    """Capture host metadata and consume the companion's verified, read-only launcher."""
    import shutil
    import subprocess
    import tempfile

    unavailable = {"status": "unavailable", "reason": "No HC_TERMINAL_ID; caller absent"}
    if not os.environ.get("HC_TERMINAL_ID"):
        return {"session": unavailable}
    try:
        if host not in ("claude", "codex") or os.name != "posix":
            raise ValueError("Automatic companion bootstrap is supported on POSIX Claude and Codex only")
        cli, node = shutil.which(host), shutil.which("node")
        if not cli or not node:
            raise ValueError("Host CLI or Node is missing from PATH")
        listing = subprocess.run(  # noqa: S603 - Installed host CLI, fixed read-only argv.
            [cli, "plugin", "list", "--json"], capture_output=True, text=True, timeout=45, check=True
        )
        metadata = json.loads(listing.stdout)
        root = bootstrap_root(host, metadata)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as file:
            file.write(listing.stdout)
            file.flush()
            result = subprocess.run(  # noqa: S603 - Host-selected companion validates metadata before probing.
                [
                    "/bin/sh",
                    os.path.join(root, "scripts/preflight.sh"),
                    os.path.realpath(node),
                    "--host",
                    host,
                    "--metadata",
                    file.name,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        report = json.loads(result.stdout)
        return validate_probe(report, result.returncode, root, os.environ["HC_TERMINAL_ID"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        return {"bootstrap": {"status": "failed", "reason": str(error)[:300]}, "session": {"status": "untested"}}


def stored_state(path: str) -> dict[str, Any]:
    active, execution = read_state(path)
    return {"active": active, "execution": execution, "explicitNative": read_execution(path) == "native"}


def persistence_failure(path: str, error: OSError) -> dict[str, Any]:
    import errno

    return {
        "state": stored_state(path),
        "persistence": "failed",
        "reason": str(error),
        "approvalRequired": error.errno in (errno.EPERM, errno.EACCES, errno.EROFS),
    }


def select_automatically(path: str, host: str) -> dict[str, Any]:
    result: dict[str, Any] = {"state": stored_state(path), "persistence": "unchanged", "reason": None}
    if not result["state"]["active"] or read_execution(path) is not None:
        return result
    try:
        before = os.stat(path)
        report = probe_companion(host)
        result["preflight"] = report
        companion = report.get("companion", {})
        result["companion"] = companion.get("path")
        if companion.get("status") == "supported":
            result["guidance"] = os.path.join(companion["path"], "skills/hc-workflow/SKILL.md")
        if (
            report.get("session", {}).get("status") != "supported"
            or companion.get("status") != "supported"
            or report.get("bootstrap", {}).get("status") != "supported"
        ):
            result["reason"] = next(
                (
                    report[key]["reason"]
                    for key in ("bootstrap", "companion", "probe", "session")
                    if report.get(key, {}).get("reason")
                ),
                "Preflight did not verify selection",
            )
            result["state"] = stored_state(path)
            return result
        with StateLock(path):
            # Native, Disable, or a new activation during the probe supersedes its result.
            if (
                read_state(path)[0]
                and read_execution(path) is None
                and (os.stat(path).st_ino, os.stat(path).st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
            ):
                write_state(execution_path(path), {"execution": "herdr"})
                result["persistence"] = "persisted"
            else:
                result["reason"] = "Session preference changed during preflight; retained the newer state"
        result["state"] = stored_state(path)
    except OSError as error:
        result.update(persistence_failure(path, error))
    return result


def apply_control(path: str, host: str, action: str) -> dict[str, Any]:
    try:
        if action in ("enable", "disable"):
            set_active(path, action == "enable")
        else:
            set_execution(path, action)
        result = {"state": stored_state(path), "persistence": "persisted", "reason": None}
        if action == "enable":
            selection = select_automatically(path, host)
            result.update(selection)
            if selection["persistence"] == "unchanged":
                result["persistence"] = "persisted"
        return result
    except OSError as error:
        return persistence_failure(path, error)


def execution_context(path: str, host: str, active: bool, execution: str, selection: dict[str, Any] | None) -> str:
    context = ""
    if execution == "herdr":
        companion = (selection or {}).get("guidance") or companion_skill(host)
        context += "\nHerdr execution is selected for this session. "
        if companion:
            context += f"Read {companion} (herdr-zstack:hc-workflow) alongside the selected playbook. "
        else:
            context += (
                "Capability gap: herdr-zstack:hc-workflow is missing or ambiguous; "
                "resolve it through the host catalog. "
            )
        context += (
            "Keep file edits and quick checks (expected under about 30 seconds) direct. "
            "Run slower or unknown-duration commands (tests, builds, installs, CI watches, servers) with "
            "`hc run --bg` and `hc wait`, not host background shells, monitors or sleep/poll loops. "
            "When the playbook delegates, use hc instead of native agent tools for authorized workers. "
            "No legacy Herdr fallback. Native hc requires HC_TERMINAL_ID, a resolved caller and an answering core; "
            "HERDR_ENV alone is insufficient. Do not dispatch until the companion's read-only preflight passes. "
            "Never copy these controls into children. Later user instructions override stored state."
        )
    elif active and read_execution(path) != "native":
        context += "\nHerdr execution is not enabled. Automatic selection did not persist: "
        context += str((selection or {}).get("reason") or "preflight unavailable")[:300] + "."
        context += " Do not substitute conversational selection for stored state."
    else:
        context += "\nHerdr execution is not enabled."
        if read_execution(path) == "native":
            context += " Native was explicitly selected; do not auto-select Herdr."
    return context


def build_context(host: str, session_id: str, data_dir: str, source: str) -> tuple[str, str | None]:
    """Restore scoped state and render controls without emitting output."""
    if host not in ("codex", "claude", "hermes"):
        raise ValueError("Invalid host")
    if source not in ("startup", "resume", "clear", "compact", "fork"):
        raise ValueError("Invalid context source")
    path = state_path(data_dir, session_id)
    active, execution, clear_error = restore_state(path, source)
    selection = None
    if active and source != "clear":
        selection = select_automatically(path, host)
        active, execution = read_state(path)
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
        "Enable requires explicit z-mode activation; Disable clears both; "
        "Herdr selects execution; Native opts out of automatic Herdr. Preferences do not control processes. "
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
    context += execution_context(path, host, active, execution, selection)
    if selection and selection["persistence"] == "failed":
        clear_error = "Automatic selection state write failed; follow the control approval guidance above."
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
        result = apply_control(path, args.host, args.action)
    except ValueError as error:
        parser.exit(1, f"z-mode control failed: {error}\n")
    print(json.dumps(result))
    if result["persistence"] == "failed":
        remedy = "If a sandbox blocked this write, follow this session's z-mode guidance for blocked controls.\n"
        parser.exit(
            1,
            f"z-mode control failed; see actual stored state above: {result['reason']}\n"
            + (remedy if result.get("approvalRequired") else ""),
        )


if __name__ == "__main__":
    main()
