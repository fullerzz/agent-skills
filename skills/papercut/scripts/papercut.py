#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record zstack papercuts in a private local store and export one as an editable issue draft.

Capture and export stay local: this helper opens no network connection, browser, or subprocess.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

SCHEMA = 1
STORE_ENV = "ZSTACK_PAPERCUT_DIR"
ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
HOSTS = ("claude-code", "codex", "hermes", "other")
KINDS = ("bad-instruction", "missing-prerequisite", "silent-failure", "tool-error", "other")
CAPTURES = ("explicit", "opt-in")
# Short caps keep reports to observations; pasted transcripts and raw logs do not fit.
LIMITS = {"component": 80, "summary": 120}
TEXT_LIMIT, TEXT_LINES = 1000, 12
REQUIRED_TEXT = ("component", "summary", "tried", "expected", "actual")
OPTIONAL_TEXT = ("workaround", "suspected_fix", "zstack_version")
FIELDS = {*REQUIRED_TEXT, *OPTIONAL_TEXT, "host", "kind", "blocked", "capture"}
MAX_INPUT = 64 * 1024
# The skill's real install root: <root>/skills/papercut/scripts/papercut.py.
INSTALL_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_URL = re.compile(
    r"https://(?:github\.com/fullerzz/agent-skills|fullerzz\.github\.io/agent-skills)(?:[/#][^\s?]*)?"
)


class PapercutError(Exception):
    """A report was not saved or exported; the message says why."""


def store_dir() -> Path:
    override = os.environ.get(STORE_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise PapercutError(f"{STORE_ENV} must be an absolute path")
        if any((parent / ".git").exists() for parent in (path.resolve(), *path.resolve().parents)):
            raise PapercutError(f"{STORE_ENV} is inside a Git checkout; choose a private directory outside projects")
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        path = Path(os.environ["LOCALAPPDATA"]) / "zstack" / "papercuts"
    else:
        state = os.environ.get("XDG_STATE_HOME", "")
        base = Path(state) if Path(state).is_absolute() else Path.home() / ".local" / "state"
        path = base / "zstack" / "papercuts"
    if path.resolve().is_relative_to(INSTALL_ROOT):
        raise PapercutError("the papercut store must be outside the zstack install tree")
    return path


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def zstack_version() -> str | None:
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        try:
            version = json.loads((INSTALL_ROOT / manifest).read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(version, str):
            return version
    try:
        match = re.search(
            r"^version:\s*[\"']?([\w.+-]+)", (INSTALL_ROOT / "plugin.yaml").read_text(encoding="utf-8"), re.M
        )
    except OSError:
        return None
    return match[1] if match else None


SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,})"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[\w.~+/=-]{8,}"),
)
KEY_VALUE_SECRET = re.compile(
    r"(?i)\b([\w-]*(?:token|secret|password|passwd|api[_-]?key|authorization|cookie)[\w-]*)(\s*[:=]\s*)[\"']?"
    # A value needs a digit or some length, so prose such as "authorization: steps" survives.
    r"(?=[^\s\"',;]*\d|[^\s\"',;]{12})[^\s\"',;]+"
)
URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\"'`)\]]+")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
SESSION = re.compile(r"(?i)\b(session|thread|conversation|run)([ _-]?id\s*[:=]?\s*)(?=[\w.-]*\d)[\w.-]{6,}")
HOST_SESSION = re.compile(r"\bsession_[A-Za-z0-9]{8,}\b")
IP_ADDRESS = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")
# A dotless name with a port is a host (localhost:8080, nas:3035); file.py:12 line references survive.
HOST_PORT = re.compile(r"(?<![\w.-])[A-Za-z][\w-]*:\d{2,5}\b")
WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s\"'`]+")
POSIX_PATH = re.compile(r"(?<![\w:/.~<>-])(?:~(?:/[\w.@+-]+)+|(?:/[\w.@+-]+){2,})/?")
LONG_TOKEN = re.compile(r"[A-Za-z0-9_+=-]{32,}")


def scrub_path(match: re.Match[str]) -> str:
    path = match[0]
    # Keep the zstack-relative tail of an installed or checked-out skill path; it names the component.
    tail = path.rfind("/skills/")
    return f"<path>/{path[tail + 1 :]}" if tail >= 0 else "<path>"


def scrub_token(match: re.Match[str]) -> str:
    token = match[0]
    mixed = any(c.isdigit() for c in token) and any(c.islower() for c in token) and any(c.isupper() for c in token)
    return "<redacted>" if mixed else token


def scrub_secrets(text: str) -> str:
    """Best-effort removal of credentials. Saved reports keep paths and hosts as local evidence."""
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("<redacted>", text)
    text = KEY_VALUE_SECRET.sub(r"\1\2<redacted>", text)
    return LONG_TOKEN.sub(scrub_token, text)


def scrub(text: str) -> str:
    """Best-effort removal of credentials, private URLs and paths, hosts, emails, and session IDs."""
    text = scrub_secrets(text)
    text = URL.sub(lambda m: m[0] if PUBLIC_URL.fullmatch(m[0]) else "<url>", text)
    text = EMAIL.sub("<email>", text)
    text = IP_ADDRESS.sub("<host>", text)
    text = HOST_PORT.sub("<host>", text)
    text = UUID.sub("<id>", text)
    text = HOST_SESSION.sub("<id>", text)
    text = SESSION.sub(r"\1\2<id>", text)
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "~")
    text = WINDOWS_PATH.sub("<path>", text)
    return POSIX_PATH.sub(scrub_path, text)


def text_field(report: dict[str, object], key: str, *, required: bool) -> str | None:
    value = report.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PapercutError(f"{key}: need a nonempty string")
    value = value.strip()
    limit = LIMITS.get(key, TEXT_LIMIT)
    single_line = key in LIMITS or key == "zstack_version"
    if len(value) > limit or (single_line and "\n" in value) or value.count("\n") >= TEXT_LINES:
        shape = "one line" if single_line else f"{TEXT_LINES} lines"
        raise PapercutError(f"{key}: keep it to {limit} characters and {shape}; summarize instead of pasting logs")
    return scrub_secrets(value)


def choice(report: dict[str, object], key: str, options: tuple[str, ...], default: str | None = None) -> str:
    value = report.get(key, default)
    if value not in options:
        raise PapercutError(f"{key}: need one of {', '.join(options)}")
    return str(value)


def validate(report: object) -> dict[str, object]:
    if not isinstance(report, dict):
        raise PapercutError("input must be one JSON object")
    if unknown := sorted(set(report) - FIELDS):
        raise PapercutError(f"unknown fields: {', '.join(unknown)}")
    if not isinstance(report.get("blocked"), bool):
        raise PapercutError("blocked: need true or false")
    fields = {key: text_field(report, key, required=True) for key in REQUIRED_TEXT}
    optional = {key: text_field(report, key, required=False) for key in OPTIONAL_TEXT}
    return {
        "schema": SCHEMA,
        "component": fields["component"],
        "host": choice(report, "host", HOSTS),
        "zstack_version": optional["zstack_version"] or zstack_version(),
        "kind": choice(report, "kind", KINDS),
        "capture": choice(report, "capture", CAPTURES, "explicit"),
        "summary": fields["summary"],
        "tried": fields["tried"],
        "expected": fields["expected"],
        "actual": fields["actual"],
        "blocked": report["blocked"],
        "workaround": optional["workaround"],
        "suspected_fix": optional["suspected_fix"],
    }


def write_new(directory: Path, name: str, content: str) -> Path:
    """Write content to a new private file, never replacing one that exists."""
    target = directory / name
    temp = directory / f".tmp-{secrets.token_hex(8)}"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        target.hardlink_to(temp)
    finally:
        temp.unlink(missing_ok=True)
    return target


def record(stdin: str) -> str:
    if len(stdin) > MAX_INPUT:
        raise PapercutError("input is too large; record a short structured report, not a transcript or log")
    try:
        report = validate(json.loads(stdin))
    except json.JSONDecodeError as error:
        raise PapercutError(f"input is not JSON: {error.msg}") from error
    reports = private_dir(private_dir(store_dir()) / "reports")
    for _ in range(5):
        now = datetime.now(UTC)
        report_id = f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        body = {"id": report_id, "created": f"{now:%Y-%m-%dT%H:%M:%SZ}", **report}
        try:
            path = write_new(reports, f"{report_id}.json", json.dumps(body, indent=2) + "\n")
        except FileExistsError:
            continue
        return f"saved {report_id}: {path}"
    raise PapercutError("could not allocate a unique report ID")


def report_path(report_id: str) -> Path:
    if not ID.fullmatch(report_id):
        raise PapercutError(f"not a papercut ID: {report_id!r}")
    return store_dir() / "reports" / f"{report_id}.json"


def load(report_id: str) -> dict[str, object]:
    path = report_path(report_id)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PapercutError(f"no papercut {report_id}") from error
    except ValueError as error:
        raise PapercutError(f"papercut {report_id} is not valid JSON") from error
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise PapercutError(f"papercut {report_id} has an unsupported schema")
    return report


def all_reports() -> list[dict[str, object]]:
    directory = store_dir() / "reports"
    if not directory.is_dir():
        return []
    found: list[dict[str, object]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            found.append(load(path.stem))
        except PapercutError as error:
            print(f"papercut: skipped {path.name}: {error}", file=sys.stderr)
    return found


def list_reports(component: str | None, as_json: bool) -> str:
    reports = [r for r in all_reports() if component is None or r.get("component") == component]
    if as_json:
        return json.dumps(reports, indent=2)
    if not reports:
        return "No papercuts recorded."
    rows = [
        f"{r['id']}  {r['component']}  {r['kind']}  {'blocked' if r['blocked'] else 'not-blocked'}  {r['summary']}"
        for r in reports
    ]
    return "\n".join(rows)


def delete(report_ids: list[str]) -> str:
    lines = []
    for report_id in report_ids:
        path = report_path(report_id)
        try:
            path.unlink()
        except FileNotFoundError as error:
            raise PapercutError(f"no papercut {report_id}") from error
        (store_dir() / "drafts" / f"{report_id}.md").unlink(missing_ok=True)
        lines.append(f"deleted {report_id}")
    return "\n".join(lines)


def clean(value: object) -> str:
    # Drafts open with an HTML comment, so report text must not close it early.
    return scrub(str(value)).replace("-->", "-- >").strip()


def render(report: dict[str, object]) -> str:
    title = f"papercut({clean(report.get('component', 'zstack'))}): {clean(report.get('summary', 'untitled'))}"
    lines = [
        "<!--",
        f"Suggested title: {title}",
        "",
        "Review this draft before filing. Automatic redaction is best-effort: it replaces known",
        "credential, private URL, path, host, email, and session-ID patterns. Remove anything else",
        "sensitive, such as project names or proprietary details. Nothing has been filed;",
        "copying the edited text into an issue is up to you.",
        "",
        f"Local papercut: {clean(report.get('id', 'unknown'))}",
        "-->",
        "",
        "## Context",
        "",
        f"- Component: {clean(report.get('component', 'unknown'))}",
        f"- Host: {clean(report.get('host', 'unknown'))}",
        f"- zstack version: {clean(report.get('zstack_version') or 'unknown')}",
        f"- Kind: {clean(report.get('kind', 'unknown'))}",
        f"- Blocked progress: {'yes' if report.get('blocked') is True else 'no'}",
    ]
    sections = [
        ("What was tried", "tried"),
        ("Expected", "expected"),
        ("Actual", "actual"),
        ("Workaround", "workaround"),
        ("Suspected fix (unverified)", "suspected_fix"),
    ]
    for heading, key in sections:
        if report.get(key):
            lines += ["", f"## {heading}", "", clean(report[key])]
    return "\n".join(lines) + "\n"


def export(report_id: str, output: str | None, force: bool) -> str:
    draft = render(load(report_id))
    if output is None:
        directory, name = private_dir(private_dir(store_dir()) / "drafts"), f"{report_id}.md"
    else:
        target = Path(output).expanduser().resolve()
        directory, name = target.parent, target.name
    if force:
        (directory / name).unlink(missing_ok=True)
    try:
        path = write_new(directory, name, draft)
    except FileExistsError as error:
        raise PapercutError(f"{directory / name} exists; edit it, or pass --force to replace it") from error
    return f"exported {report_id}: {path}"


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="papercut.py",
        description=f"Local zstack papercut reports. Store: {STORE_ENV}, else $XDG_STATE_HOME or "
        "~/.local/state, under zstack/papercuts (%%LOCALAPPDATA%%\\zstack\\papercuts on Windows).",
    )
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("record", help="save one report read as a JSON object from stdin")
    listing = commands.add_parser("list", help="list reports, oldest first")
    listing.add_argument("--component", help="only reports for this component")
    listing.add_argument("--json", action="store_true", help="print full reports as JSON")
    commands.add_parser("show", help="print one report").add_argument("id")
    commands.add_parser("delete", help="delete reports and their drafts").add_argument("id", nargs="+")
    drafting = commands.add_parser("export", help="write one report as a Markdown issue draft")
    drafting.add_argument("id")
    drafting.add_argument("--output", help="draft path; default <store>/drafts/<id>.md")
    drafting.add_argument("--force", action="store_true", help="replace an existing draft")
    commands.add_parser("path", help="print the store directory")
    return cli


def fail(message: str, code: int) -> NoReturn:
    print(f"papercut: {message}", file=sys.stderr)
    sys.exit(code)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        match args.command:
            case "record":
                output = record(sys.stdin.read(MAX_INPUT + 1))
            case "list":
                output = list_reports(args.component, args.json)
            case "show":
                output = json.dumps(load(args.id), indent=2)
            case "delete":
                output = delete(args.id)
            case "export":
                output = export(args.id, args.output, args.force)
            case _:
                output = str(store_dir())
    except PapercutError as error:
        fail(f"{'not saved' if args.command == 'record' else 'failed'}: {error}", 2)
    except OSError as error:
        fail(f"{'not saved' if args.command == 'record' else 'failed'}: {error}", 1)
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
