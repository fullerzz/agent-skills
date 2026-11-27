#!/usr/bin/env -S uv run --offline --no-python-downloads --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Record zstack papercuts in a private local store and export one as an editable issue draft.

Capture and export stay local: the only program this helper runs is a local secret scanner (BetterLeaks or
gitleaks) with live validation off. It opens no network connection or browser. Saved reports are private
evidence, so recording removes only the credentials the scanner finds plus auth headers and URL user info.
Exported drafts are meant to be shared, so export redacts aggressively and the user edits the result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
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
    for sibling in ("reports", "drafts"):
        if (root / sibling).is_symlink():
            raise PapercutError(f"{root / sibling} is a symbolic link; refusing to use the store")
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


# Credentials come from a secret scanner: BetterLeaks when installed, otherwise gitleaks. It runs locally on
# stdin with live validation off. The two rules below cover what both scanners miss in report text.
SCANNERS = ("betterleaks", "gitleaks")
# Both scanners read rules, allowlists, and live validation from their own variables (GITLEAKS_CONFIG,
# BETTERLEAKS_CONFIG_TOML, BETTERLEAKS_VALIDATE, ...). Dropping them all keeps the default rules.
SCANNER_ENV_PREFIXES = ("GITLEAKS_", "BETTERLEAKS_")
SCANNER_TIMEOUT = 60
# Both scanners accept these. --ignore-gitleaks-allow stops report text from silencing a finding. Decoding is
# pinned because older gitleaks releases default to none, which would let an encoded credential pass unseen.
SCANNER_FLAGS = (
    *("--no-banner", "--no-color", "--log-level", "error", "--exit-code", "0", "--ignore-gitleaks-allow"),
    *("--max-decode-depth", "5"),
    *("--report-format", "json", "--report-path", "-"),
)
AUTH_SCHEMES = (
    r"basic|bearer|digest|negotiate|token|apikey|api-key|key|sso-key|signature|hmac|hoba|mutual|vapid"
    r"|aws4-hmac-sha256|scram-sha-\d+"
)
# An Authorization value that starts with an auth scheme, or Cookie name=value pairs. The value ends at the
# quote that opened it, whether the quote wraps the value (JSON) or the whole header (a shell argument).
AUTH_HEADER = re.compile(
    rf"(?im)([\"']?)\b((?:proxy-)?authorization)([\"']?\s*[:=]\s*)([\"']?)((?:{AUTH_SCHEMES})\b[^\n]*)"
)
COOKIE_HEADER = re.compile(r"(?im)([\"']?)\b((?:set-)?cookie)([\"']?\s*:\s*)([\"']?)([^\s=;\"']+=[^\n]*)")
URL_USERINFO = re.compile(r"(?<=://)[^\s/?#@<>]+@")

# Export rules, applied word by word. Over-redaction is fine in a draft the user edits before filing.
PUBLIC_URL = re.compile(
    r"https://(?:github\.com/fullerzz/agent-skills|fullerzz\.github\.io/agent-skills)(?:/[^\s?#=]*)?(?:#[\w-]*)?"
)
PASSWORD_LINE = re.compile(r"(?i)\b([\w-]*(?:passw|pwd|secret|credential|private[_-]?key)[\w-]*)(\s*[:=]\s*)\S[^\n]*")
CREDENTIAL_KEY = re.compile(
    r"(?i)^-{0,2}[\w-]*(?:token|secret|passw|pwd|api[_-]?key|access[_-]?key|private[_-]?key|auth|cookie"
    r"|credential|session[_-]?id|sessionid|sid)[\w-]*$"
)
SESSION_LABEL = re.compile(r"(?i)^(?:session|thread|conversation|run)$")
SLASH_COMMAND = re.compile(r"^/[\w:-]+$")
FILE_REFERENCE = re.compile(r"^([\w.-]+?)(?::\d+(?::\d+)?)?$")
TIME = re.compile(r"^\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?$")
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
DOMAIN = re.compile(r"^(?:[A-Za-z0-9-]+\.)+([A-Za-z]{2,})$")
HOST_SUFFIXES = frozenset(
    {"com", "net", "org", "io", "dev", "app", "ai", "co", "corp", "internal", "local", "lan", "cloud"}
)
FILE_SUFFIXES = frozenset(
    {
        "md", "mdx", "py", "pyi", "js", "mjs", "cjs", "ts", "tsx", "jsx", "json", "jsonl", "yaml", "yml", "toml",
        "ini", "cfg", "conf", "sh", "bash", "zsh", "fish", "ps1", "txt", "log", "rs", "go", "rb", "java", "kt",
        "c", "h", "cc", "cpp", "hpp", "cs", "swift", "html", "css", "scss", "sql", "lock", "xml", "vue",
        "svelte", "tf", "nix", "lua", "csv", "pdf", "png", "xlsx", "docx",
    }
)  # fmt: skip
FILE_NAMES = frozenset(
    {"dockerfile", "containerfile", "makefile", "justfile", "gemfile", "rakefile", "procfile", "vagrantfile"}
    | {"license", "readme", "changelog"}
)
PUNCTUATION = "\"'`()[]{},;!?"
# The placeholders redaction writes. Any other <...> word, such as a Markdown autolink, is redacted inside.
PLACEHOLDERS = frozenset({"<redacted>", "<url>", "<email>", "<path>", "<id>", "<host>"})


def scanner() -> str:
    for name in SCANNERS:
        if path := shutil.which(name):
            return path
    raise PapercutError("needs a secret scanner on PATH: install betterleaks (brew install betterleaks) or gitleaks")


def scan(text: str) -> list[str]:
    """Return the secrets the scanner finds in text. Any scanner failure raises, so nothing passes unchecked."""
    if not text.strip():
        return []
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCANNER_ENV_PREFIXES)}
    # An empty working directory keeps any .gitleaksignore or target config out of the scan.
    with tempfile.TemporaryDirectory(prefix="papercut-scan-") as empty:
        try:
            result = subprocess.run(  # noqa: S603 - Fixed scanner argv; report text goes through stdin, no shell.
                [scanner(), "stdin", *SCANNER_FLAGS],
                input=text,
                cwd=empty,
                env=environment,
                capture_output=True,
                text=True,
                timeout=SCANNER_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PapercutError(f"secret scan did not run: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1:] or [f"exit {result.returncode}"]
        raise PapercutError(f"secret scan failed: {detail[0]}")
    # Both scanners print [] when they find nothing, so an empty report means the scan did not finish.
    try:
        findings = json.loads(result.stdout)
    except ValueError as error:
        raise PapercutError("secret scan returned unreadable output") from error
    if not isinstance(findings, list) or any(
        not isinstance(f, dict) or not isinstance(f.get("Secret"), str) or not f["Secret"] for f in findings
    ):
        raise PapercutError("secret scan returned an unsupported report format")
    return [f["Secret"] for f in findings]


def remove(text: str, found: list[str]) -> str:
    for secret in sorted(set(found), key=len, reverse=True):
        text = text.replace(secret, "<redacted>")
    return text


def redact_header(match: re.Match[str]) -> str:
    outer, name, separator, inner, value = match.groups()
    quote = inner or outer
    end = value.find(quote) if quote else -1
    return f"{outer}{name}{separator}{inner}<redacted>{value[end:] if end >= 0 else ''}"


def scrub_structure(text: str) -> str:
    """The two credential shapes the scanners miss: auth headers and URL user info."""
    text = AUTH_HEADER.sub(redact_header, text)
    text = COOKIE_HEADER.sub(redact_header, text)
    return URL_USERINFO.sub("<redacted>@", text)


def scrub_record(fields: dict[str, str]) -> dict[str, str]:
    """Remove credentials from saved text. Everything else stays as local evidence."""
    found = scan("\n".join(fields.values()))
    if not found:
        return {key: scrub_structure(value) for key, value in fields.items()}
    scrubbed = {key: remove(value, found) for key, value in fields.items()}
    # A scanner reports a decoded secret, such as one inside base64, by its decoded value, which the text does not
    # hold. Scan again, and refuse to save a credential that literal removal could not reach.
    if scan("\n".join(scrubbed.values())):
        raise PapercutError("the scanner found a credential that could not be removed, maybe an encoded one")
    return {key: scrub_structure(value) for key, value in scrubbed.items()}


def zstack_file(core: str) -> bool:
    relative = core.split(":", 1)[0]
    if relative.startswith(("/", "~", ".")) or "\\" in relative:
        return False
    return (INSTALL_ROOT / relative).is_file() or (INSTALL_ROOT / "skills" / relative).is_file()


def file_reference(core: str) -> bool:
    match = FILE_REFERENCE.fullmatch(core)
    if not match:
        return False
    name = match[1].lower()
    return name in FILE_NAMES or ("." in name and name.rsplit(".", 1)[1] in FILE_SUFFIXES)


def pathlike(core: str) -> bool:
    return ("/" in core or "\\" in core) and not SLASH_COMMAND.fullmatch(core) and not zstack_file(core)


def redact_path(path: str) -> str:
    # Keep the tail of a path into a file this install ships; it names the zstack component.
    posix = path.replace("\\", "/")
    tail = posix.rfind("/skills/")
    rest = posix[tail + 1 :].split(":", 1)[0] if tail >= 0 else ""
    return f"<path>/{posix[tail + 1 :]}" if rest and (INSTALL_ROOT / rest).is_file() else "<path>"


def hostlike(core: str) -> bool:
    if file_reference(core) or TIME.fullmatch(core) or SLASH_COMMAND.fullmatch(core):
        return False
    if ":" in core and (re.search(r":\d{1,5}$", core) or "::" in core or core.count(":") >= 3):
        return True
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", core):
        return True
    domain = DOMAIN.fullmatch(core)
    return domain is not None and (core.count(".") >= 2 or domain[1].lower() in HOST_SUFFIXES)


def secret_shaped(core: str) -> bool:
    mixed = any(c.islower() for c in core) and any(c.isupper() for c in core)
    return len(core) >= 16 and mixed and any(c.isdigit() for c in core)


def unwrap(core: str) -> str:
    """Strip angle brackets, such as a Markdown autolink's, until a placeholder or a bare word is left."""
    while core not in PLACEHOLDERS and (core.startswith("<") or core.endswith(">")):
        core = core.removeprefix("<").removesuffix(">")
    return core


def redact_word(core: str) -> str:
    """Return the placeholder for one word, or the word itself when it is safe to keep."""
    if not core or core in PLACEHOLDERS:
        return core
    if (inner := unwrap(core)) != core:
        kept = redact_word(inner)
        return core if kept == inner else kept
    if "://" in core:
        return core if PUBLIC_URL.fullmatch(core) else "<url>"
    if "@" in core:
        return "<email>" if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", core) else "<redacted>"
    if pathlike(core):
        return redact_path(core)
    if UUID.search(core):
        return "<id>"
    if "=" in core:
        key, _, value = core.partition("=")
        return f"{key}=<redacted>" if value and re.fullmatch(r"[-\w.]+", key) else "<redacted>"
    key, colon, value = core.partition(":")
    if colon and value.strip(PUNCTUATION) and CREDENTIAL_KEY.fullmatch(key.strip(PUNCTUATION)):
        return f"{key}:<redacted>"
    if hostlike(core):
        return "<host>"
    return "<redacted>" if secret_shaped(core) else core


def credential_follows(previous: list[str], core: str) -> bool:
    """Whether core is a credential: after key: or key=, after a credential --flag, or after a session ID label."""
    last = previous[-1] if previous else ""
    if last.endswith((":", "=")) and CREDENTIAL_KEY.fullmatch(last.rstrip(":=").strip(PUNCTUATION)):
        return True
    if last.startswith("-") and CREDENTIAL_KEY.fullmatch(last):
        return True
    # "session id alpha-bravo-charlie" is an ID; "the session ID handling" is prose.
    labeled = len(previous) > 1 and last.lower() == "id" and bool(SESSION_LABEL.fullmatch(previous[-2]))
    return labeled and any(c.isdigit() or c in "-_" for c in core)


def scrub_line(line: str) -> str:
    line = PASSWORD_LINE.sub(r"\1\2<redacted>", line)
    parts = re.split(r"(\s+)", line)
    words = parts[0::2]
    cores = [word.strip(PUNCTUATION) for word in words]
    replaced = [redact_word(core) for core in cores]
    for index, core in enumerate(cores):
        if core and core not in PLACEHOLDERS and replaced[index] == core and credential_follows(cores[:index], core):
            replaced[index] = "<redacted>"
    # A path with spaces splits into several words: redact the words between two path pieces, and a file name
    # right after a path piece, so folder and file names do not leak.
    piece = [value.startswith("<path>") for value in replaced]
    for index, core in enumerate(cores):
        between = any(piece[max(0, index - 4) : index]) and any(piece[index + 1 : index + 5])
        trailing_file = index > 0 and piece[index - 1] and re.search(r"\.\w{1,8}$", core) is not None
        if core and not piece[index] and (between or trailing_file):
            replaced[index] = "<path>"
    parts[0::2] = [
        word.replace(core, value, 1) if core else word for word, core, value in zip(words, cores, replaced, strict=True)
    ]
    return "".join(parts)


def scrub_draft(text: str) -> str:
    """Aggressive word-by-word redaction for drafts; credentials were already removed by the scanner."""
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "~")
    # A quoted path may hold spaces anywhere, so it goes whole.
    text = re.sub(r"([\"'`])((?:~/|/[^\"'`\n/ ]+/|[A-Za-z]:[\\/]|\\\\)[^\"'`\n]*)\1", r"\1<path>\1", text)
    return "\n".join(scrub_line(line) for line in text.split("\n"))


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
    return value


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
    host, kind = choice(report, "host", HOSTS), choice(report, "kind", KINDS)
    capture = choice(report, "capture", CAPTURES, "explicit")
    given = {key: text_field(report, key, required=key in REQUIRED_TEXT) for key in (*REQUIRED_TEXT, *OPTIONAL_TEXT)}
    scrubbed = scrub_record({key: value for key, value in given.items() if value is not None})
    fields = {key: scrubbed.get(key) for key in REQUIRED_TEXT}
    optional = {key: scrubbed.get(key) for key in OPTIONAL_TEXT}
    return {
        "schema": SCHEMA,
        "component": fields["component"],
        "host": host,
        "zstack_version": optional["zstack_version"] or zstack_version(),
        "kind": kind,
        "capture": capture,
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
        and all(isinstance(report.get(key), str) and report[key].strip() for key in ("created", *REQUIRED_TEXT))
        and all("\n" not in report[key] for key in ("created", *LIMITS))
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
    # iterdir raises when the directory cannot be read; glob would silently report an empty store.
    for path in sorted(p for p in directory.iterdir() if p.suffix == ".json" and not p.name.startswith(".")):
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


def clean(value: object, found: list[str]) -> str:
    # Drafts open with an HTML comment, so report text must not close it early.
    return scrub_draft(scrub_structure(remove(str(value), found))).replace("-->", "-- >").strip()


def render(report: dict[str, object]) -> str:
    keys = ("component", "summary", "zstack_version", *REQUIRED_TEXT[2:], *OPTIONAL_TEXT[:2])
    found = scan("\n".join(str(report[key]) for key in keys if report.get(key)))
    title = f"papercut({clean(report['component'], found)}): {clean(report['summary'], found)}"
    lines = [
        "<!--",
        f"Suggested title: {title}",
        "",
        "Review this draft before filing. A secret scanner removed the credentials it found, and",
        "word-by-word redaction replaced paths, URLs, hosts, emails, and session IDs. It can remove",
        "harmless text too. Restore what you want, and remove anything else sensitive.",
        "Nothing has been filed; copying the edited text into an issue is up to you.",
        "",
        f"Local papercut: {report['id']}",
        "-->",
        "",
        "## Context",
        "",
        f"- Component: {clean(report['component'], found)}",
        f"- Host: {report['host']}",
        f"- zstack version: {clean(report.get('zstack_version') or 'unknown', found)}",
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
            lines += ["", f"## {heading}", "", clean(report[key], found)]
    return "\n".join(lines) + "\n"


def export(report_id: str, output: str | None, force: bool) -> str:
    with store_lock():
        draft = render(load(report_id))
        # The finished draft gets one more scan; a finding means redaction missed something, so nothing is written.
        if leftover := scan(draft):
            raise PapercutError(f"the draft still holds {len(leftover)} secret(s) after redaction; not written")
        if output is None:
            directory, name = store_subdir("drafts"), f"{report_id}.md"
        else:
            target = Path(output).expanduser().resolve()
            directory, name = target.parent, target.name
            if target.is_relative_to(store_dir().resolve()) and not target.is_relative_to(
                store_subdir("drafts", create=False).resolve()
            ):
                raise PapercutError("--output must not point into the store outside drafts/; reports live there")
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
