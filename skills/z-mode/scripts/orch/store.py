"""Plain-file orchestration bookkeeping, compatible with the original Bun store."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

UNIT_FIELDS = ["id", "track", "state", "branch", "pr", "sha", "brief"]
LEDGER_FIELDS = ["pr", "sha", "verdict", "evidence", "verifier", "ts"]
POINTER_FIELDS = ["ts", "agent", "unit", "status", "report"]
VERDICTS = ("live-ui-verified", "unit-test-verified", "type-check-only", "verifier-blocked", "verifier-failed")
MAX_SAFE_INTEGER = 2**53 - 1


class StatusSummary(TypedDict):
    unitStates: dict[str, int]
    ledgerVerdicts: dict[str, int]
    frontierGeneration: int
    openGateIds: list[str]


class UserError(Exception):
    pass


class NotFoundError(UserError):
    def __init__(self, message: str, output: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.output = output


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def clean_cell(value: object) -> str:
    value = re.sub(r"[\t\n\r]", " ", str(value))
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


def required(value: str, label: str, line: bool = False) -> str:
    value = re.sub(r"[\r\n]", " ", value).strip() if line else clean_cell(value)
    if not value.strip():
        raise UserError(f"{label} must not be empty")
    return value


def positive(value: object) -> int:
    if type(value) is not int or not 0 < value <= MAX_SAFE_INTEGER:
        raise UserError("PR must be a positive integer")
    return value


def atomic_write(path: Path, contents: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            stream.write(contents)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def count_line(value: dict[str, int]) -> str:
    return ", ".join(f"{key}={count}" for key, count in value.items()) or "none"


def table(headers: Sequence[str], rows: list[list[object]]) -> str:
    if not rows:
        return "(none)"

    def escape(value: object) -> str:
        return str(value).replace("\\", "\\\\").replace("|", "\\|")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        + ["| " + " | ".join(map(escape, row)) + " |" for row in rows]
    )


OPEN_GT_STATUSES = {
    "Trunk branch locked",
    "Changes requested",
    "Waiting on PRs in this stack to merge",
    "Waiting on downstack merge state",
    "Draft",
    "Required checks failed",
    "Undergoing failure detection",
    "Merge queue failed on current head commit",
    "Handed off to merge queue...",
    "Waiting on downstack",
    "Merge conflicts",
    "Needs reviewers",
    "Needs approvals",
    "Needs restack",
    "Queued to merge...",
    "Ready to merge",
    "Ready to merge as stack",
    "Rebasing...",
    "Waiting on CI...",
    "Stale, needs rebase onto trunk",
    "Unresolved comments",
    "Waiting on required CI",
    "Waiting to merge...",
}


def command(argv: list[str], repo: Path) -> str:
    try:
        return subprocess.run(  # noqa: S603 - Fixed Git/gh/gt argument vectors from local callers; no shell.
            argv,
            cwd=repo,
            env={**os.environ, "NO_COLOR": "1"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise UserError(f"{' '.join(argv)} failed: {error}") from error


def parse_gt_branches(raw: str) -> list[str]:
    branches = []
    for index, line in enumerate(raw.replace("\r", "").split("\n"), 1):
        if not line:
            continue
        match = re.fullmatch(r"(?:│ )*[◯◉] +([^\s]+)((?: \([^()\r\n]*\))*)", line)
        if not match:
            raise UserError(f"gt log short output has an unparseable line {index}: {json.dumps(line)}")
        branch = match[1]
        if branch in branches:
            raise UserError(f"gt log short output contains duplicate branch {branch}")
        branches.append(branch)
    if not branches:
        raise UserError("gt log short output did not contain a stack")
    return branches


def resolve_frontier(repo: Path) -> list[dict[str, Any]]:
    raw = command(["gt", "--no-interactive", "log", "short", "--stack", "--reverse"], repo)
    branches = parse_gt_branches(raw)
    result = []
    for branch in branches[1:]:
        info = command(["gt", "--no-interactive", "info", branch], repo)
        rows = [line for line in info.splitlines() if line.startswith(("PR #", "[origin] PR #"))]
        if not rows:
            raise UserError(
                f"gt info output branch {branch} has no pull request; "
                "resolve the frontier from the stacker clone or after gt sync"
            )
        if len(rows) != 1:
            raise UserError(f"gt info output contains multiple PRs for branch {branch}")
        match = re.fullmatch(r"(?:\[origin\] )?PR #([1-9]\d*)(?: \(([^)\r\n]+)\))?(?: .+)?", rows[0])
        if not match:
            raise UserError(f"gt info output has an invalid PR row for branch {branch}: {rows[0]}")
        status = match[2]
        if status not in {None, "Merged", "Closed"} | OPEN_GT_STATUSES:
            raise UserError(f"gt info output has an unknown PR state for branch {branch}: {status}")
        sha = command(["git", "rev-parse", "--verify", branch], repo).strip()
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            raise UserError(f"git rev-parse {branch} returned an invalid SHA")
        result.append(
            {
                "pr": positive(int(match[1])),
                "branches": branch,
                "sha": sha,
                "state": {"Merged": "MERGED", "Closed": "CLOSED"}.get(status, "OPEN"),
            }
        )
    if len({row["pr"] for row in result}) != len(result):
        raise UserError("gt info output contains duplicate pull requests")
    return result


def previous_summary(path: Path) -> StatusSummary | None:
    before = None
    if path.exists():
        match = re.search(r"<!-- orch-summary (.+) -->", path.read_text(encoding="utf-8"))
        if match:
            try:
                candidate = json.loads(match[1])
                valid = isinstance(candidate, dict) and all(
                    isinstance(candidate.get(key), dict)
                    and all(type(n) is int and 0 <= n <= MAX_SAFE_INTEGER for n in candidate[key].values())
                    for key in ("unitStates", "ledgerVerdicts")
                )
                if (
                    valid
                    and type(candidate.get("frontierGeneration")) is int
                    and isinstance(candidate.get("openGateIds"), list)
                    and all(isinstance(x, str) for x in candidate["openGateIds"])
                ):
                    before = candidate
            except ValueError:
                pass
    return before


class Store:
    def __init__(self, directory: str | Path, force: bool = False) -> None:
        self.path = Path(directory).absolute()
        self.force = force
        self.closed = False
        self.locked = False
        self.lock_identity: tuple[int, int] | None = None

    def ensure_open(self) -> None:
        if self.closed:
            raise UserError("store is closed")

    def read(self, name: str) -> str:
        self.ensure_open()
        try:
            return (self.path / name).read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise UserError(f"store is not initialized at {self.path}; run orch init") from error

    def begin_write(self) -> None:
        self.ensure_open()
        if self.locked:
            return
        if not self.path.exists():
            raise UserError(f"store is not initialized at {self.path}; run orch init")
        lock = self.path / ".orch.lock"
        try:
            stream = lock.open("x", encoding="utf-8")
        except FileExistsError:
            holder = lock.read_text().strip() or "unknown"
            dead = False
            if re.fullmatch(r"[1-9]\d*", holder):
                try:
                    os.kill(int(holder), 0)
                except ProcessLookupError:
                    dead = True
                except (PermissionError, OverflowError):
                    pass
            if not (dead or self.force):
                raise UserError(f"store lock held by pid {holder}") from None
            print(
                f"replacing stale store lock (pid {holder} is dead)"
                if dead
                else f"stealing store lock held by pid {holder}",
                file=sys.stderr,
            )
            lock.unlink()
            try:
                stream = lock.open("x", encoding="utf-8")
            except FileExistsError:
                raise UserError(f"store lock held by pid {lock.read_text().strip()}") from None
        with stream:
            stream.write(f"{os.getpid()}\n")
            stat = os.fstat(stream.fileno())
            self.lock_identity = (stat.st_dev, stat.st_ino)
        self.locked = True

    def close(self) -> None:
        if self.locked:
            lock = self.path / ".orch.lock"
            try:
                stat = lock.stat()
                if (stat.st_dev, stat.st_ino) == self.lock_identity and lock.read_text().strip() == str(os.getpid()):
                    lock.unlink()
            except FileNotFoundError:
                pass
        self.closed = True
        self.locked = False

    def init(self) -> dict[str, str]:
        self.ensure_open()
        self.path.mkdir(parents=True, exist_ok=True)
        self.begin_write()
        for name, text in {
            "units.tsv": "\t".join(UNIT_FIELDS) + "\n",
            "ledger.tsv": "\t".join(LEDGER_FIELDS) + "\n",
            "gates.md": "",
            "preferences.md": "",
            "frontier.json": "{}\n",
        }.items():
            if not (self.path / name).exists():
                atomic_write(self.path / name, text)
        (self.path / "inbox").mkdir(exist_ok=True)
        return {"store": str(self.path)}

    def read_tsv(self, name: str, fields: Sequence[str]) -> list[dict[str, str]]:
        lines = self.read(name).replace("\r", "").split("\n")
        if lines.pop(0) != "\t".join(fields):
            raise UserError(f"{name} has an invalid header")
        result = []
        for line in filter(None, lines):
            cells = line.split("\t")
            if len(cells) != len(fields):
                raise UserError(f"{name} has a malformed row")
            result.append(dict(zip(fields, cells, strict=True)))
        return result

    def save_tsv(self, name: str, fields: Sequence[str], rows: list[dict[str, str]]) -> None:
        atomic_write(
            self.path / name,
            "\t".join(fields)
            + "\n"
            + "".join("\t".join(clean_cell(row[key]) for key in fields) + "\n" for row in rows),
        )

    def unit_list(self, state: str | None = None, track: str | None = None) -> list[dict[str, str]]:
        state = required(state, "state") if state is not None else None
        track = required(track, "track") if track is not None else None
        return [
            row
            for row in self.read_tsv("units.tsv", UNIT_FIELDS)
            if (state is None or row["state"] == state) and (track is None or row["track"] == track)
        ]

    def unit_get(self, id: str) -> dict[str, str]:
        id = required(id, "unit id")
        for row in self.unit_list():
            if row["id"] == id:
                return row
        raise NotFoundError(f"unit {id} not found")

    def unit_add(self, id: str, track: str, brief: str | None = None) -> dict[str, str]:
        self.begin_write()
        row = {
            "id": required(id, "unit id"),
            "track": required(track, "track"),
            "state": "pending",
            "branch": "",
            "pr": "",
            "sha": "",
            "brief": required(brief, "brief") if brief is not None else "",
        }
        rows = self.unit_list()
        if any(old["id"] == row["id"] for old in rows):
            raise UserError(f"unit {row['id']} already exists")
        self.save_tsv("units.tsv", UNIT_FIELDS, [*rows, row])
        return row

    def unit_set(
        self, id: str, state: str, branch: str | None = None, pr: int | None = None, sha: str | None = None
    ) -> dict[str, str]:
        self.begin_write()
        old = self.unit_get(id)
        row = {**old, "state": required(state, "state")}
        for key, value in [("branch", branch), ("sha", sha)]:
            if value is not None:
                row[key] = required(value, key)
        if pr is not None:
            row["pr"] = str(positive(pr))
        self.save_tsv("units.tsv", UNIT_FIELDS, [row if item["id"] == old["id"] else item for item in self.unit_list()])
        return row

    def unit_counts(self) -> dict[str, int]:
        return counts(row["state"] for row in self.unit_list())

    def read_ledger(self) -> list[dict[str, str]]:
        rows = self.read_tsv("ledger.tsv", LEDGER_FIELDS)
        for row in rows:
            if row["verdict"] not in VERDICTS:
                raise UserError(f"ledger.tsv has invalid verdict {row['verdict']}")
        return rows

    def ledger_record(
        self, pr: int, sha: str, verdict: str, evidence: str, verifier: str | None = None
    ) -> dict[str, str]:
        self.begin_write()
        if verdict not in VERDICTS:
            raise UserError("verdict must be " + ", ".join(VERDICTS))
        row = {
            "pr": str(positive(pr)),
            "sha": required(sha, "SHA"),
            "verdict": verdict,
            "evidence": required(evidence, "evidence"),
            "verifier": required(verifier, "verifier") if verifier is not None else "",
            "ts": timestamp(),
        }
        rows = self.read_ledger()
        for index, old in enumerate(rows):
            if (old["pr"], old["sha"]) == (row["pr"], row["sha"]):
                rows[index] = row
                break
        else:
            rows.append(row)
        self.save_tsv("ledger.tsv", LEDGER_FIELDS, rows)
        return row

    def ledger_check(self, pr: int, sha: str) -> dict[str, str]:
        pr_text, sha = str(positive(pr)), required(sha, "SHA")
        for row in self.read_ledger():
            if (row["pr"], row["sha"]) == (pr_text, sha):
                return row
        raise NotFoundError("NOT-VERIFIED", {"pr": pr_text, "sha": sha, "verdict": "NOT-VERIFIED"})

    def ledger_summary(self) -> dict[str, int]:
        return counts(row["verdict"] for row in self.read_ledger())

    def inbox_peek(self) -> list[dict[str, str]]:
        self.ensure_open()
        inbox = self.path / "inbox"
        if not inbox.is_dir():
            raise UserError(f"store is not initialized at {self.path}; run orch init")
        rows = []
        for path in sorted(inbox.iterdir()):
            if path.suffix != ".tsv" or not path.is_file() or path.is_symlink():
                continue
            raw = re.sub(r"\r?\n$", "", path.read_text(encoding="utf-8"))
            cells = raw.split("\t")
            if "\r" in raw or "\n" in raw or len(cells) != 5:
                raise UserError(f"inbox pointer {path.name} is malformed")
            rows.append(dict(zip(POINTER_FIELDS, cells, strict=True)))
        return rows

    def inbox_count(self) -> int:
        return len(self.inbox_peek())

    def inbox_push(self, agent: str, unit: str, status: str, report: str | None = None) -> dict[str, Any]:
        self.begin_write()
        row = {
            "ts": timestamp(),
            "agent": required(agent, "agent"),
            "unit": required(unit, "unit"),
            "status": required(status, "status"),
            "report": required(report, "report") if report is not None else "",
        }
        filename = re.sub(r"[:.]", "-", row["ts"]) + f"-{os.getpid()}-{uuid.uuid4()}.tsv"
        atomic_write(self.path / "inbox" / filename, "\t".join(clean_cell(row[key]) for key in POINTER_FIELDS) + "\n")
        return {"pointer": row, "filename": filename}

    def inbox_drain(self) -> list[dict[str, str]]:
        self.begin_write()
        rows = self.inbox_peek()
        inbox = self.path / "inbox"
        drained = self.path / f".inbox-drain-{os.getpid()}-{uuid.uuid4()}"
        inbox.rename(drained)
        try:
            inbox.mkdir()
        except OSError:
            drained.rename(inbox)
            raise
        shutil.rmtree(drained)
        return rows

    def read_gates(self) -> list[dict[str, str]]:
        raw = self.read("gates.md").replace("\r", "").strip()
        if not raw:
            return []
        prefix = "# Gates\n\n## "
        if not raw.startswith(prefix):
            raise UserError("gates.md has an invalid heading")
        rows = []
        for block in raw[len(prefix) :].split("\n\n## "):
            lines = list(filter(None, block.split("\n")))
            id = lines.pop(0)
            fields = {}
            for line in lines:
                match = re.fullmatch(r"- ([^:]+): (.*)", line)
                if not match:
                    raise UserError(f"gates.md has a malformed gate {id}")
                fields[match[1]] = match[2]
            if not id or not {"Status", "Question", "Options", "Default"} <= fields.keys():
                raise UserError(f"gates.md has a malformed gate {id}")
            row = {
                "kind": fields["Status"],
                "id": id,
                "question": fields["Question"],
                "options": fields["Options"],
                "defaultAnswer": fields["Default"],
            }
            if row["kind"] == "resolved" and "Answer" in fields:
                row["answer"] = fields["Answer"]
            elif row["kind"] != "open":
                raise UserError(f"gates.md has invalid status {row['kind']}")
            rows.append(row)
        if len({row["id"] for row in rows}) != len(rows):
            raise UserError("gates.md has duplicate gate ids")
        return rows

    def save_gates(self, rows: list[dict[str, str]]) -> None:
        blocks = [
            (
                f"## {r['id']}\n\n- Status: {r['kind']}\n- Question: {r['question']}\n"
                f"- Options: {r['options']}\n- Default: {r['defaultAnswer']}"
            )
            + (f"\n- Answer: {r['answer']}" if r["kind"] == "resolved" else "")
            for r in rows
        ]
        atomic_write(self.path / "gates.md", "# Gates\n\n" + "\n\n".join(blocks) + "\n" if blocks else "")

    def gate_park(self, id: str, question: str, options: str, default: str) -> dict[str, str]:
        self.begin_write()
        row = {
            "kind": "open",
            "id": required(id, "gate id", True),
            "question": required(question, "question", True),
            "options": required(options, "options", True),
            "defaultAnswer": required(default, "default", True),
        }
        rows = self.read_gates()
        for index, old in enumerate(rows):
            if old["id"] == row["id"]:
                rows[index] = row
                break
        else:
            rows.append(row)
        self.save_gates(rows)
        return row

    def gate_list(self) -> list[dict[str, str]]:
        return [row for row in self.read_gates() if row["kind"] == "open"]

    def gate_resolve(self, id: str, answer: str) -> dict[str, str]:
        self.begin_write()
        id = required(id, "gate id", True)
        rows = self.read_gates()
        for index, old in enumerate(rows):
            if old["id"] == id:
                row = {**old, "kind": "resolved", "answer": required(answer, "answer", True)}
                rows[index] = row
                self.save_gates(rows)
                return row
        raise NotFoundError(f"gate {id} not found")

    def frontier_show(self) -> dict[str, Any]:
        try:
            value = json.loads(self.read("frontier.json"))
        except ValueError:
            raise UserError("frontier.json is not valid JSON") from None
        if not isinstance(value, dict):
            raise UserError("frontier.json must contain an object")
        if not value:
            return {"generation": 0, "prs": [], "lowestUnmerged": None}
        if (
            type(value.get("generation")) is not int
            or not 0 <= value["generation"] <= MAX_SAFE_INTEGER
            or not isinstance(value.get("prs"), list)
            or "lowestUnmerged" not in value
            or (
                value["lowestUnmerged"] is not None
                and (type(value["lowestUnmerged"]) is not int or abs(value["lowestUnmerged"]) > MAX_SAFE_INTEGER)
            )
        ):
            raise UserError("frontier.json has an invalid shape")
        for row in value["prs"]:
            if (
                not isinstance(row, dict)
                or type(row.get("pr")) is not int
                or not 0 < row["pr"] <= MAX_SAFE_INTEGER
                or not isinstance(row.get("branches"), str)
                or not row["branches"]
                or not isinstance(row.get("sha"), str)
                or row.get("state") not in ("OPEN", "MERGED", "CLOSED")
            ):
                raise UserError("frontier.json has an invalid PR row")
        return value

    def frontier_set(self, repo: str | Path, prs: list[int] | None = None) -> dict[str, Any]:
        self.begin_write()
        if prs is not None:
            prs = [positive(pr) for pr in prs]
            if len(set(prs)) != len(prs):
                raise UserError("--prs must not contain duplicates")
        old = self.frontier_show()
        rows = resolve_frontier(Path(required(str(repo), "repo directory", True)).absolute())
        actual = [row["pr"] for row in rows]
        if prs is not None and actual != prs:
            missing, extra = [pr for pr in prs if pr not in actual], [pr for pr in actual if pr not in prs]

            def join(values: list[int]) -> str:
                return ",".join(map(str, values))

            drift = ([f"missing from gt: {join(missing)}"] if missing else []) + (
                [f"extra in gt: {join(extra)}"] if extra else []
            )
            raise UserError(
                "frontier pin mismatch: "
                + ("; ".join(drift) or f"order differs: expected {join(prs)}; gt {join(actual)}")
            )
        result = {
            "generation": old["generation"] + 1,
            "prs": rows,
            "lowestUnmerged": next((row["pr"] for row in rows if row["state"] == "OPEN"), None),
        }
        atomic_write(self.path / "frontier.json", json.dumps(result, indent=2) + "\n")
        return result

    def standing_show(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        raw = self.read("preferences.md").replace("\r", "")
        if not raw.strip():
            return rows
        for line in filter(None, raw.split("\n")):
            match = re.fullmatch(r"([1-9]\d*)\. (.+)", line)
            if not match or int(match[1]) != len(rows) + 1:
                raise UserError("preferences.md has malformed numbering")
            rows.append({"number": int(match[1]), "line": match[2]})
        return rows

    def standing_add(self, line: str) -> dict[str, Any]:
        self.begin_write()
        rows = self.standing_show()
        row = {"number": len(rows) + 1, "line": required(line, "standing order", True)}
        atomic_write(self.path / "preferences.md", "".join(f"{r['number']}. {r['line']}\n" for r in [*rows, row]))
        return row

    def status(self) -> dict[str, Any]:
        self.begin_write()
        units, ledger, frontier, gates = self.unit_list(), self.read_ledger(), self.frontier_show(), self.read_gates()
        summary: StatusSummary = {
            "unitStates": counts(r["state"] for r in units),
            "ledgerVerdicts": counts(r["verdict"] for r in ledger),
            "frontierGeneration": frontier["generation"],
            "openGateIds": sorted(r["id"] for r in gates if r["kind"] == "open"),
        }
        path = self.path / "status.md"
        before = previous_summary(path)
        changes = []
        if before is not None:
            for label, old_counts, new_counts in [
                ("units", before["unitStates"], summary["unitStates"]),
                ("ledger", before["ledgerVerdicts"], summary["ledgerVerdicts"]),
            ]:
                for name in sorted(old_counts.keys() | new_counts.keys()):
                    a, b = old_counts.get(name, 0), new_counts.get(name, 0)
                    if a != b:
                        changes.append(f"{label} {name} {a}->{b}")
            if before["frontierGeneration"] != summary["frontierGeneration"]:
                changes.append(f"frontier generation {before['frontierGeneration']}->{summary['frontierGeneration']}")
            if before["openGateIds"] != summary["openGateIds"]:
                changes.append(f"open gates {len(before['openGateIds'])}->{len(summary['openGateIds'])}")
        change = "first render" if before is None else "; ".join(changes) or "no derived changes"
        text = (
            f"# Orchestrate status\n\nGenerated: {timestamp()}\n\n## Units\n\n"
            f"States: {count_line(summary['unitStates'])}\n\n"
        )
        text += table(
            ["ID", "Track", "State", "Branch", "PR", "SHA", "Brief"], [[r[k] for k in UNIT_FIELDS] for r in units]
        )
        text += f"\n\n## Verification ledger\n\nVerdicts: {count_line(summary['ledgerVerdicts'])}\n\n"
        text += table(
            ["PR", "SHA", "Verdict", "Evidence", "Verifier", "Timestamp"],
            [[r[k] for k in LEDGER_FIELDS] for r in ledger],
        )
        text += (
            f"\n\n## Frontier\n\nGeneration: {frontier['generation']}\n"
            f"Lowest unmerged: {frontier['lowestUnmerged'] or 'none'}\n\n"
        )
        text += table(
            ["Branch", "PR", "SHA", "State"],
            [[r[k] for k in ("branches", "pr", "sha", "state")] for r in frontier["prs"]],
        )
        text += "\n\n## Gates\n\n" + table(
            ["ID", "Status", "Question", "Options", "Default", "Answer"],
            [[r.get(k, "") for k in ("id", "kind", "question", "options", "defaultAnswer", "answer")] for r in gates],
        )
        text += "\n\n<!-- orch-summary " + json.dumps(summary, separators=(",", ":")) + " -->\n"
        atomic_write(path, text)
        return {
            "units": units,
            "ledger": ledger,
            "frontier": frontier,
            "gates": gates,
            "summary": summary,
            "changed": change,
        }
