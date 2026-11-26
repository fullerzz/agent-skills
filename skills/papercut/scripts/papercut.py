#!/usr/bin/env -S uv run --offline --no-python-downloads --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record zstack papercuts in a private local store and export one as an editable issue draft.

Capture and export stay local: this helper opens no network connection, browser, or subprocess.
Saved reports are private evidence, so recording removes only credentials with an exact format.
Exported drafts are meant to be shared, so export redacts aggressively and the user edits the result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Generator

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
STORED_FIELDS = {*FIELDS, "schema", "id", "created"}
MAX_INPUT = 64 * 1024
# The skill's real install root: <root>/skills/papercut/scripts/papercut.py.
INSTALL_ROOT = Path(__file__).resolve().parents[3]


class PapercutError(Exception):
    """A report was not saved or exported; the message says why."""


def inside_checkout(path: Path) -> bool:
    resolved = path.resolve()
    home = Path.home().resolve()
    # A dotfiles repository at or above home would otherwise rule out every default store.
    skip = {home, *home.parents}
    return any((parent / ".git").exists() for parent in (resolved, *resolved.parents) if parent not in skip)


def store_dir() -> Path:
    override = os.environ.get(STORE_ENV)
    local = os.environ.get("LOCALAPPDATA", "")
    state = os.environ.get("XDG_STATE_HOME", "")
    if override:
        path = Path(override).expanduser()
    elif os.name == "nt" and Path(local).is_absolute():
        path = Path(local) / "zstack" / "papercuts"
    else:
        base = Path(state) if Path(state).is_absolute() else Path.home() / ".local" / "state"
        path = base / "zstack" / "papercuts"
    if not path.is_absolute():
        raise PapercutError(f"{STORE_ENV} must be an absolute path")
    if inside_checkout(path):
        raise PapercutError(f"{path} is inside a Git checkout; set {STORE_ENV} to a private directory outside projects")
    if path.resolve().is_relative_to(INSTALL_ROOT):
        raise PapercutError("the papercut store must be outside the zstack install tree")
    return path


def private_dir(path: Path, *, allow_link: bool = False) -> Path:
    """Create a missing directory as owner-only. Existing directories keep their mode."""
    # POSIX modes only; on Windows the per-user %LOCALAPPDATA% ACL is what keeps the store private.
    if path.is_symlink() and not allow_link:
        raise PapercutError(f"{path} is a symbolic link; refusing to use it")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        if not path.is_dir():
            raise PapercutError(f"{path} is not a directory") from None
        return path
    path.chmod(0o700)
    return path


def store_subdir(name: str, *, create: bool = True) -> Path:
    """reports/ or drafts/ inside the store. Every command refuses a linked one, so none reaches outside."""
    root = store_dir()
    path = root / name
    if path.is_symlink():
        raise PapercutError(f"{path} is a symbolic link; refusing to use it")
    if create:
        private_dir(private_dir(root, allow_link=True) / name)
    return path


@contextmanager
def store_lock() -> Generator[None]:
    """Serialize export and delete, so neither leaves or removes a draft the other just handled."""
    descriptor = os.open(private_dir(store_dir(), allow_link=True) / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


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


# Recording: only credentials whose format is exact. Everything else stays as local evidence.
TOKEN_FORMATS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,})"),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"),
)
# A credential header loses its value: an auth scheme after Authorization, or name=value pairs after Cookie.
# A quoted value ends at its closing quote; an unquoted one runs to the end of the line.
AUTH_HEADER = re.compile(
    r"(?im)\b((?:proxy-)?authorization)([\"']?\s*[:=]\s*)([\"']?)"
    r"((?:basic|bearer|digest|negotiate|token|hoba|mutual|vapid|aws4-hmac-sha256|scram-sha-\d+)\b[^\n]*)"
)
COOKIE_HEADER = re.compile(r"(?im)\b((?:set-)?cookie)([\"']?\s*:\s*)([\"']?)([^\s=;\"']+=[^\n]*)")
URL_USERINFO = re.compile(r"(?<=://)[^\s/@<>]+@")

# Export: aggressive. Over-redaction is fine in a draft the user edits before filing.
PUBLIC_URL = re.compile(
    r"https://(?:github\.com/fullerzz/agent-skills|fullerzz\.github\.io/agent-skills)(?:[/#][^\s?]*)?"
)
URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://(?:<redacted>|\[[0-9A-Za-z:.%]+\]|[^\s<>\"'`)\]])*")
CREDENTIAL_NAME = (
    r"[\w-]*(?:token|secret|passw|pwd|api[_-]?key|access[_-]?key|private[_-]?key|auth|cookie|credential"
    r"|(?:session|thread|conversation|run|request|trace)[ _-]?id|sessionid)[\w-]*"
)
SECRET_KEY_VALUE = re.compile(
    rf"(?i)([\"']?)\b({CREDENTIAL_NAME})\1(\s*[:=]\s*)(\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|[^\s\"',;}}\]]+)"
)
# An unquoted password-like value can hold spaces, so it runs to the end of the line.
PASSWORD_LINE = re.compile(
    r"(?i)\b([\w-]*(?:passw|pwd|secret|credential|private[_-]?key)[\w-]*)(\s*[:=]\s*)(?![\"'])[^\n]+"
)
SCHEME_VALUE = re.compile(r"(?i)\b(bearer|basic|digest|negotiate)(\s+)([A-Za-z0-9+/=._~-]{4,})")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")
IPV6 = re.compile(r"(?i)(?<![\w:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])")
UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
HOST_SESSION = re.compile(r"\bsession_[A-Za-z0-9]{8,}\b")
SESSION_PROSE = re.compile(r"(?i)\b((?:session|thread|conversation|run)[ _-]?id)(\s+)(?=[\w.-]*\d)[\w.-]{6,}")
# A quoted path may hold spaces after its first segment; it needs two segments, so quoted slash commands such
# as `/baton catch docs/plan.md` survive.
QUOTED_PATH = re.compile(r"([\"'`])((?:~/|/[^\"'`\n/ ]+/|[A-Za-z]:\\|\\\\)[^\"'`\n]*)\1")
# Unquoted paths continue past a space into a capitalized word, a word with another segment, or a file name.
POSIX_CONTINUE = r"(?: (?:[A-Z][\w.@+-]*|[\w.@+-]+(?=/)|[\w@+-]+\.[A-Za-z0-9]{1,8}(?!\w))(?:/[\w.@+-]+)*)*"
WINDOWS_CONTINUE = r"(?: (?:[A-Z][^\s\"'`\\]*|[^\s\"'`\\]+(?=\\)|[\w@+-]+\.[A-Za-z0-9]{1,8}(?!\w))(?:\\[^\s\"'`\\]+)*)*"
POSIX_PATH = re.compile(rf"(?<![\w:/.~<>-])(?:~(?:/[\w.@+-]+)+|(?:/[\w.@+-]+){{2,}}){POSIX_CONTINUE}/?")
WINDOWS_PATH = re.compile(rf"(?:\b[A-Za-z]:|\\\\[\w.$-]+)(?:\\[^\s\"'`\\]+)+\\?{WINDOWS_CONTINUE}")
NAME_PORT = re.compile(r"(?<![\w.<>-])([A-Za-z][\w.-]*):(\d{2,5})\b")
FILE_SUFFIXES = frozenset(
    {
        "md",
        "mdx",
        "py",
        "pyi",
        "js",
        "mjs",
        "cjs",
        "ts",
        "tsx",
        "jsx",
        "json",
        "jsonl",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "conf",
        "sh",
        "bash",
        "zsh",
        "fish",
        "ps1",
        "txt",
        "log",
        "rs",
        "go",
        "rb",
        "java",
        "kt",
        "c",
        "h",
        "cc",
        "cpp",
        "hpp",
        "cs",
        "swift",
        "html",
        "css",
        "scss",
        "sql",
        "lock",
        "xml",
        "vue",
        "svelte",
        "tf",
        "nix",
        "lua",
    }
)
FILE_NAMES = frozenset(
    {
        "dockerfile",
        "containerfile",
        "makefile",
        "justfile",
        "gemfile",
        "rakefile",
        "procfile",
        "vagrantfile",
        "license",
        "readme",
    }
)
LONG_TOKEN = re.compile(r"[A-Za-z0-9_+/=-]{24,}")


def redact_header(match: re.Match[str]) -> str:
    name, separator, quote, value = match.groups()
    end = value.find(quote) if quote else -1
    rest = value[end:] if end >= 0 else ""
    return f"{name}{separator}{quote}<redacted>{rest}"


def scrub_record(text: str) -> str:
    """Remove credentials with an exact format. Saved reports keep everything else as local evidence."""
    for pattern in TOKEN_FORMATS:
        text = pattern.sub("<redacted>", text)
    text = AUTH_HEADER.sub(redact_header, text)
    text = COOKIE_HEADER.sub(redact_header, text)
    return URL_USERINFO.sub("<redacted>@", text)


def redact_key_value(match: re.Match[str]) -> str:
    key_quote, key, separator, value = match.groups()
    if value.strip("\"'") == "<redacted>":
        return match[0]
    quote = value[0] if value[0] in "\"'" else ""
    return f"{key_quote}{key}{key_quote}{separator}{quote}<redacted>{quote}"


def redact_scheme(match: re.Match[str]) -> str:
    scheme, space, value = match.groups()
    mixed = any(c.islower() for c in value) and any(c.isupper() for c in value)
    encoded = any(c.isdigit() or c in "+/=" for c in value) or (len(value) >= 16 and mixed)
    return f"{scheme}{space}<redacted>" if scheme.lower() == "bearer" or encoded else match[0]


def redact_ipv6(match: re.Match[str]) -> str:
    address = match[0]
    hexlike = "::" in address or (address.count(":") >= 4 and any(c.isalpha() for c in address))
    return "<host>" if hexlike else address


def redact_path(path: str) -> str:
    # Keep the tail of a path into a file this install ships; it names the zstack component.
    posix = path.replace("\\", "/")
    tail = posix.rfind("/skills/")
    if tail >= 0:
        rest = posix[tail + 1 :].rstrip("/")
        if (INSTALL_ROOT / rest).is_file():
            return f"<path>/{rest}"
    return "<path>"


def redact_name_port(match: re.Match[str]) -> str:
    name = match[1].lower()
    # Dockerfile:12 and SKILL.md:12 are file references; every other name:number is treated as a host.
    if name in FILE_NAMES or ("." in name and name.rsplit(".", 1)[1] in FILE_SUFFIXES):
        return match[0]
    return "<host>"


def redact_long_token(match: re.Match[str]) -> str:
    # Mixed case plus a digit: Git SHAs and UUIDs are lowercase and survive.
    token = match[0]
    mixed = any(c.islower() for c in token) and any(c.isupper() for c in token)
    return "<redacted>" if mixed and any(c.isdigit() for c in token) else token


def scrub_plain(text: str) -> str:
    text = PASSWORD_LINE.sub(r"\1\2<redacted>", text)
    text = SECRET_KEY_VALUE.sub(redact_key_value, text)
    text = SCHEME_VALUE.sub(redact_scheme, text)
    text = EMAIL.sub("<email>", text)
    text = IPV4.sub("<host>", text)
    text = IPV6.sub(redact_ipv6, text)
    text = UUID.sub("<id>", text)
    text = HOST_SESSION.sub("<id>", text)
    text = SESSION_PROSE.sub(r"\1\2<id>", text)
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "~")
    text = QUOTED_PATH.sub(lambda m: f"{m[1]}{redact_path(m[2])}{m[1]}", text)
    text = WINDOWS_PATH.sub(lambda m: redact_path(m[0]), text)
    text = POSIX_PATH.sub(lambda m: redact_path(m[0]), text)
    text = NAME_PORT.sub(redact_name_port, text)
    return LONG_TOKEN.sub(redact_long_token, text)


def scrub_export(text: str) -> str:
    """Best-effort removal of credentials, private URLs and paths, hosts, emails, and session IDs."""
    text = scrub_record(text)
    # URLs are settled first and kept whole: this repository's public links survive, and every other URL goes.
    parts, last = [], 0
    for match in URL.finditer(text):
        parts += [scrub_plain(text[last : match.start()]), match[0] if PUBLIC_URL.fullmatch(match[0]) else "<url>"]
        last = match.end()
    return "".join([*parts, scrub_plain(text[last:])])


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
    return scrub_record(value)


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


def well_formed(report: object, report_id: str) -> bool:
    if not isinstance(report, dict) or set(report) - STORED_FIELDS:
        return False
    return (
        type(report.get("schema")) is int
        and report["schema"] == SCHEMA
        and report.get("id") == report_id
        and all(isinstance(report.get(key), str) for key in ("created", *REQUIRED_TEXT))
        and all(report.get(key) is None or isinstance(report.get(key), str) for key in OPTIONAL_TEXT)
        and report.get("host") in HOSTS
        and report.get("kind") in KINDS
        and report.get("capture") in CAPTURES
        and isinstance(report.get("blocked"), bool)
    )


def write_file(directory: Path, name: str, content: str, *, replace: bool = False) -> Path:
    """Publish content as a private file in one step; without replace, never touch an existing file."""
    target = directory / name
    temp = directory / f".tmp-{secrets.token_hex(8)}"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            temp.replace(target)
        else:
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
    reports = store_subdir("reports")
    for _ in range(5):
        now = datetime.now(UTC)
        report_id = f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        body = {"id": report_id, "created": f"{now:%Y-%m-%dT%H:%M:%SZ}", **report}
        try:
            path = write_file(reports, f"{report_id}.json", json.dumps(body, indent=2) + "\n")
        except FileExistsError:
            continue
        return f"saved {report_id}: {path}"
    raise PapercutError("could not allocate a unique report ID")


def report_path(report_id: str) -> Path:
    if not ID.fullmatch(report_id):
        raise PapercutError(f"not a papercut ID: {report_id!r}")
    return store_subdir("reports", create=False) / f"{report_id}.json"


def load(report_id: str) -> dict[str, object]:
    path = report_path(report_id)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PapercutError(f"no papercut {report_id}") from error
    except ValueError as error:
        raise PapercutError(f"papercut {report_id} is not valid JSON") from error
    if not well_formed(report, report_id):
        raise PapercutError(f"papercut {report_id} is malformed or uses an unsupported schema")
    return dict(report)


def all_reports() -> list[dict[str, object]]:
    directory = store_subdir("reports", create=False)
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


def delete_one(report_id: str) -> str:
    path = report_path(report_id)
    draft = store_subdir("drafts", create=False) / f"{report_id}.md"
    # The draft goes first, so a retry after a partial failure still finds the report and finishes.
    had_draft = draft.exists()
    draft.unlink(missing_ok=True)
    try:
        path.unlink()
    except FileNotFoundError as error:
        if not had_draft:
            raise PapercutError(f"no papercut {report_id}") from error
        return f"deleted leftover draft {report_id}"
    return f"deleted {report_id}"


def delete(report_ids: list[str]) -> str:
    # Each ID stands alone: one missing or failing ID does not stop the rest, and a rerun finishes the job.
    done, failed = [], []
    with store_lock():
        for report_id in report_ids:
            try:
                done.append(delete_one(report_id))
            except (PapercutError, OSError) as error:
                failed.append(str(error))
    if failed:
        if done:
            print("\n".join(done))
        raise PapercutError("; ".join(failed))
    return "\n".join(done)


def clean(value: object) -> str:
    # Drafts open with an HTML comment, so report text must not close it early.
    return scrub_export(str(value)).replace("-->", "-- >").strip()


def render(report: dict[str, object]) -> str:
    title = f"papercut({clean(report['component'])}): {clean(report['summary'])}"
    lines = [
        "<!--",
        f"Suggested title: {title}",
        "",
        "Review this draft before filing. Redaction is aggressive and still best-effort: it replaces",
        "credential, private URL, path, host, email, and session-ID patterns, and can remove harmless",
        "text too. Restore what you want, and remove anything else sensitive, such as project names.",
        "Nothing has been filed; copying the edited text into an issue is up to you.",
        "",
        f"Local papercut: {report['id']}",
        "-->",
        "",
        "## Context",
        "",
        f"- Component: {clean(report['component'])}",
        f"- Host: {report['host']}",
        f"- zstack version: {clean(report.get('zstack_version') or 'unknown')}",
        f"- Kind: {report['kind']}",
        f"- Blocked progress: {'yes' if report['blocked'] else 'no'}",
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
    with store_lock():
        draft = render(load(report_id))
        if output is None:
            directory, name = store_subdir("drafts"), f"{report_id}.md"
        else:
            target = Path(output).expanduser().resolve()
            directory, name = target.parent, target.name
        try:
            path = write_file(directory, name, draft, replace=force)
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
