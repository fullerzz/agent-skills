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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

UNIT_FIELDS = ["id", "track", "state", "branch", "pr", "sha", "brief"]
LEDGER_FIELDS = ["pr", "sha", "verdict", "evidence", "verifier", "ts"]
POINTER_FIELDS = ["ts", "agent", "unit", "status", "report"]
VERDICTS = ("live-ui-verified", "unit-test-verified", "type-check-only", "verifier-blocked", "verifier-failed")
MAX_SAFE_INTEGER = 2**53 - 1


type PrState = Literal["OPEN", "MERGED", "CLOSED"]
PR_STATES: tuple[PrState, ...] = ("OPEN", "MERGED", "CLOSED")


class PullRequestRow(TypedDict):
    number: int
    state: PrState
    headRefName: str
    baseRefName: str
    isCrossRepository: bool
    createdAt: str


class FrontierPr(TypedDict):
    pr: int
    branches: str
    sha: str
    state: PrState


class Frontier(TypedDict):
    generation: int
    prs: list[FrontierPr]
    lowestUnmerged: int | None


class StandingOrder(TypedDict):
    number: int
    line: str


# Rows stored as TSV keep every cell a string, in *_FIELDS order.
class UnitRow(TypedDict):
    id: str
    track: str
    state: str
    branch: str
    pr: str
    sha: str
    brief: str


class LedgerRow(TypedDict):
    pr: str
    sha: str
    verdict: str
    evidence: str
    verifier: str
    ts: str


class InboxPointer(TypedDict):
    ts: str
    agent: str
    unit: str
    status: str
    report: str


class InboxReceipt(TypedDict):
    pointer: InboxPointer
    filename: str


class OpenGate(TypedDict):
    kind: Literal["open"]
    id: str
    question: str
    options: str
    defaultAnswer: str


class ResolvedGate(TypedDict):
    kind: Literal["resolved"]
    id: str
    question: str
    options: str
    defaultAnswer: str
    answer: str


type Gate = OpenGate | ResolvedGate


class StatusSummary(TypedDict):
    unitStates: dict[str, int]
    ledgerVerdicts: dict[str, int]
    frontierGeneration: int
    openGateIds: list[str]


class StatusReport(TypedDict):
    units: list[UnitRow]
    ledger: list[LedgerRow]
    frontier: Frontier
    gates: list[Gate]
    summary: StatusSummary
    changed: str


class UserError(Exception):
    pass


class NotFoundError(UserError):
    def __init__(self, message: str, output: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.output = output


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def unit_row(row: Mapping[str, str]) -> UnitRow:
    return {
        "id": row["id"],
        "track": row["track"],
        "state": row["state"],
        "branch": row["branch"],
        "pr": row["pr"],
        "sha": row["sha"],
        "brief": row["brief"],
    }


def ledger_row(row: Mapping[str, str]) -> LedgerRow:
    return {
        "pr": row["pr"],
        "sha": row["sha"],
        "verdict": row["verdict"],
        "evidence": row["evidence"],
        "verifier": row["verifier"],
        "ts": row["ts"],
    }


def inbox_pointer(row: Mapping[str, str]) -> InboxPointer:
    return {
        "ts": row["ts"],
        "agent": row["agent"],
        "unit": row["unit"],
        "status": row["status"],
        "report": row["report"],
    }


def row_cells(row: Mapping[str, object], fields: Sequence[str]) -> list[object]:
    return [row[key] for key in fields]


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


def command(argv: list[str], repo: Path) -> str:
    try:
        return subprocess.run(  # noqa: S603 - Fixed Git/gh argument vectors from local callers; no shell.
            argv,
            cwd=repo,
            # GH_REPO would point gh at another repository than the checkout at `repo`.
            env={**{k: v for k, v in os.environ.items() if k != "GH_REPO"}, "NO_COLOR": "1"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise UserError(f"{' '.join(argv)} failed: {error}") from error


def list_prs(repo: Path, flag: str, branch: str, state: str) -> list[PullRequestRow]:
    fields = "number,state,headRefName,baseRefName,isCrossRepository,createdAt"
    argv = ["gh", "pr", "list", flag, branch, "--state", state, "--limit", "1000", "--json", fields]
    label = " ".join(argv[:5])
    try:
        rows = json.loads(command(argv, repo))
    except json.JSONDecodeError:
        raise UserError(f"{label} output is not valid JSON") from None
    if not isinstance(rows, list):
        raise UserError(f"{label} output is not a JSON array")
    for row in rows:
        if not (
            isinstance(row, dict)
            and type(row.get("number")) is int
            and 0 < row["number"] <= MAX_SAFE_INTEGER
            and row.get("state") in PR_STATES
            and all(isinstance(row.get(k), str) and row[k] for k in ("headRefName", "baseRefName", "createdAt"))
            and type(row.get("isCrossRepository")) is bool
        ):
            raise UserError(f"{label} output has an invalid PR row")
    # A fork can reuse a stack branch name; stack links live in this repository.
    return [row for row in rows if not row["isCrossRepository"]]


def current_pr(rows: list[PullRequestRow], branch: str) -> PullRequestRow:
    if len(opened := [row for row in rows if row["state"] == "OPEN"]) > 1:
        raise UserError(
            f"branch {branch} has multiple open pull requests: {', '.join(f'#{r['number']}' for r in opened)}"
        )
    # A reused branch keeps its old PRs; the open one, else the newest, is the branch's current PR.
    return opened[0] if opened else max(rows, key=lambda row: row["createdAt"])


def branch_pr(repo: Path, branch: str) -> PullRequestRow:
    rows = list_prs(repo, "--head", branch, "all")
    if not rows:
        raise UserError(f"branch {branch} has no pull request; open one or resolve from a fully submitted branch")
    return current_pr(rows, branch)


def children_of(repo: Path, branch: str) -> list[PullRequestRow]:
    # A head that once targeted this branch is a child only if its current PR, from its full history, still does.
    heads = {row["headRefName"] for row in list_prs(repo, "--base", branch, "all")}
    return [pr for pr in (branch_pr(repo, head) for head in sorted(heads)) if pr["baseRefName"] == branch]


def has_live_descendant(repo: Path, branch: str, seen: set[str]) -> bool:
    for child in children_of(repo, branch):
        if child["state"] != "CLOSED":
            return True
        if child["headRefName"] not in seen:
            seen.add(child["headRefName"])
            if has_live_descendant(repo, child["headRefName"], seen):
                return True
    return False


def trunk_branch(repo: Path) -> str:
    argv = ["gh", "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"]
    trunk = command(argv, repo).strip()
    if not trunk:
        raise UserError("gh repo view returned no default branch")
    return trunk


def child_pr(repo: Path, branch: str) -> PullRequestRow | None:
    children = children_of(repo, branch)
    for closed in (pr for pr in children if pr["state"] == "CLOSED"):
        if has_live_descendant(repo, closed["headRefName"], {branch, closed["headRefName"]}):
            raise UserError(f"closed PR #{closed['number']} still has open or merged descendants; retarget them")
    # Merged children with live descendants are active paths, just like open children.
    rows = [
        pr
        for pr in children
        if pr["state"] == "OPEN"
        or (pr["state"] == "MERGED" and has_live_descendant(repo, pr["headRefName"], {branch, pr["headRefName"]}))
    ]
    if not rows:
        rows = [pr for pr in children if pr["state"] == "MERGED"]
    if len(rows) > 1:
        raise UserError(f"stack is not linear: {', '.join(r['headRefName'] for r in rows)} all target {branch}")
    return rows[0] if rows else None


def resolve_frontier(repo: Path) -> list[FrontierPr]:
    """Walk the PR base chain from the current branch down to trunk, then up through its children."""
    trunk = trunk_branch(repo)
    current = command(["git", "symbolic-ref", "--short", "HEAD"], repo).strip()
    if current == trunk:
        return []
    seen, bottom = {current}, branch_pr(repo, current)
    chain = [bottom]
    while bottom["baseRefName"] != trunk:
        if bottom["baseRefName"] in seen:
            raise UserError(f"pull request base chain loops at branch {bottom['baseRefName']}")
        seen.add(bottom["baseRefName"])
        bottom = branch_pr(repo, bottom["baseRefName"])
        child_pr(repo, bottom["headRefName"])  # Validate sibling paths even when starting above the fork.
        chain.insert(0, bottom)
    tip = current
    while child := child_pr(repo, tip):
        tip = child["headRefName"]
        if tip in seen:
            raise UserError(f"pull request base chain loops at branch {tip}")
        seen.add(tip)
        chain.append(child)
    if len({row["number"] for row in chain}) != len(chain):
        raise UserError("pull request base chain contains duplicate pull requests")
    result: list[FrontierPr] = []
    for row in chain:
        branch = row["headRefName"]
        if row["state"] == "CLOSED" and has_live_descendant(repo, branch, {branch}):
            raise UserError(f"closed PR #{row['number']} still has open or merged descendants; retarget them")
        sha = command(["git", "rev-parse", "--verify", f"refs/heads/{branch}"], repo).strip()
        if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
            raise UserError(f"git rev-parse {branch} returned an invalid SHA")
        result.append({"pr": row["number"], "branches": branch, "sha": sha, "state": row["state"]})
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


def has_frontier_shape(value: Mapping[str, object]) -> bool:
    generation, lowest = value.get("generation"), value.get("lowestUnmerged")
    return (
        isinstance(generation, int)
        and not isinstance(generation, bool)
        and 0 <= generation <= MAX_SAFE_INTEGER
        and isinstance(value.get("prs"), list)
        and "lowestUnmerged" in value
        and (
            lowest is None
            or (isinstance(lowest, int) and not isinstance(lowest, bool) and abs(lowest) <= MAX_SAFE_INTEGER)
        )
    )


def is_frontier_pr(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    pr, branches = row.get("pr"), row.get("branches")
    return (
        isinstance(pr, int)
        and not isinstance(pr, bool)
        and 0 < pr <= MAX_SAFE_INTEGER
        and isinstance(branches, str)
        and bool(branches)
        and isinstance(row.get("sha"), str)
        and row.get("state") in PR_STATES
    )


def is_frontier(value: Mapping[str, object]) -> TypeGuard[Frontier]:
    prs = value.get("prs")
    return has_frontier_shape(value) and isinstance(prs, list) and all(map(is_frontier_pr, prs))


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

    def save_tsv(self, name: str, fields: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
        atomic_write(
            self.path / name,
            "\t".join(fields)
            + "\n"
            + "".join("\t".join(map(clean_cell, row_cells(row, fields))) + "\n" for row in rows),
        )

    def unit_list(self, state: str | None = None, track: str | None = None) -> list[UnitRow]:
        state = required(state, "state") if state is not None else None
        track = required(track, "track") if track is not None else None
        return [
            unit_row(row)
            for row in self.read_tsv("units.tsv", UNIT_FIELDS)
            if (state is None or row["state"] == state) and (track is None or row["track"] == track)
        ]

    def unit_get(self, id: str) -> UnitRow:
        id = required(id, "unit id")
        for row in self.unit_list():
            if row["id"] == id:
                return row
        raise NotFoundError(f"unit {id} not found")

    def unit_add(self, id: str, track: str, brief: str | None = None) -> UnitRow:
        self.begin_write()
        row: UnitRow = {
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
    ) -> UnitRow:
        self.begin_write()
        old = self.unit_get(id)
        row: UnitRow = {**old, "state": required(state, "state")}
        if branch is not None:
            row["branch"] = required(branch, "branch")
        if sha is not None:
            row["sha"] = required(sha, "sha")
        if pr is not None:
            row["pr"] = str(positive(pr))
        self.save_tsv("units.tsv", UNIT_FIELDS, [row if item["id"] == old["id"] else item for item in self.unit_list()])
        return row

    def unit_counts(self) -> dict[str, int]:
        return counts(row["state"] for row in self.unit_list())

    def read_ledger(self) -> list[LedgerRow]:
        rows = [ledger_row(row) for row in self.read_tsv("ledger.tsv", LEDGER_FIELDS)]
        for row in rows:
            if row["verdict"] not in VERDICTS:
                raise UserError(f"ledger.tsv has invalid verdict {row['verdict']}")
        return rows

    def ledger_record(self, pr: int, sha: str, verdict: str, evidence: str, verifier: str | None = None) -> LedgerRow:
        self.begin_write()
        if verdict not in VERDICTS:
            raise UserError("verdict must be " + ", ".join(VERDICTS))
        row: LedgerRow = {
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

    def ledger_check(self, pr: int, sha: str) -> LedgerRow:
        pr_text, sha = str(positive(pr)), required(sha, "SHA")
        for row in self.read_ledger():
            if (row["pr"], row["sha"]) == (pr_text, sha):
                return row
        raise NotFoundError("NOT-VERIFIED", {"pr": pr_text, "sha": sha, "verdict": "NOT-VERIFIED"})

    def ledger_summary(self) -> dict[str, int]:
        return counts(row["verdict"] for row in self.read_ledger())

    def inbox_peek(self) -> list[InboxPointer]:
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
            rows.append(inbox_pointer(dict(zip(POINTER_FIELDS, cells, strict=True))))
        return rows

    def inbox_count(self) -> int:
        return len(self.inbox_peek())

    def inbox_push(self, agent: str, unit: str, status: str, report: str | None = None) -> InboxReceipt:
        self.begin_write()
        row: InboxPointer = {
            "ts": timestamp(),
            "agent": required(agent, "agent"),
            "unit": required(unit, "unit"),
            "status": required(status, "status"),
            "report": required(report, "report") if report is not None else "",
        }
        filename = re.sub(r"[:.]", "-", row["ts"]) + f"-{os.getpid()}-{uuid.uuid4()}.tsv"
        atomic_write(self.path / "inbox" / filename, "\t".join(map(clean_cell, row_cells(row, POINTER_FIELDS))) + "\n")
        return {"pointer": row, "filename": filename}

    def inbox_drain(self) -> list[InboxPointer]:
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

    def read_gates(self) -> list[Gate]:
        raw = self.read("gates.md").replace("\r", "").strip()
        if not raw:
            return []
        prefix = "# Gates\n\n## "
        if not raw.startswith(prefix):
            raise UserError("gates.md has an invalid heading")
        rows: list[Gate] = []
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
            question, options, default = fields["Question"], fields["Options"], fields["Default"]
            if fields["Status"] == "resolved" and "Answer" in fields:
                rows.append(
                    {
                        "kind": "resolved",
                        "id": id,
                        "question": question,
                        "options": options,
                        "defaultAnswer": default,
                        "answer": fields["Answer"],
                    }
                )
            elif fields["Status"] == "open":
                rows.append(
                    {"kind": "open", "id": id, "question": question, "options": options, "defaultAnswer": default}
                )
            else:
                raise UserError(f"gates.md has invalid status {fields['Status']}")
        if len({row["id"] for row in rows}) != len(rows):
            raise UserError("gates.md has duplicate gate ids")
        return rows

    def save_gates(self, rows: list[Gate]) -> None:
        blocks = [
            (
                f"## {r['id']}\n\n- Status: {r['kind']}\n- Question: {r['question']}\n"
                f"- Options: {r['options']}\n- Default: {r['defaultAnswer']}"
            )
            + (f"\n- Answer: {r['answer']}" if r["kind"] == "resolved" else "")
            for r in rows
        ]
        atomic_write(self.path / "gates.md", "# Gates\n\n" + "\n\n".join(blocks) + "\n" if blocks else "")

    def gate_park(self, id: str, question: str, options: str, default: str) -> OpenGate:
        self.begin_write()
        row: OpenGate = {
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

    def gate_list(self) -> list[OpenGate]:
        return [row for row in self.read_gates() if row["kind"] == "open"]

    def gate_resolve(self, id: str, answer: str) -> ResolvedGate:
        self.begin_write()
        id = required(id, "gate id", True)
        rows = self.read_gates()
        for index, old in enumerate(rows):
            if old["id"] == id:
                row: ResolvedGate = {**old, "kind": "resolved", "answer": required(answer, "answer", True)}
                rows[index] = row
                self.save_gates(rows)
                return row
        raise NotFoundError(f"gate {id} not found")

    def frontier_show(self) -> Frontier:
        try:
            value = json.loads(self.read("frontier.json"))
        except ValueError:
            raise UserError("frontier.json is not valid JSON") from None
        if not isinstance(value, dict):
            raise UserError("frontier.json must contain an object")
        if not value:
            return {"generation": 0, "prs": [], "lowestUnmerged": None}
        if not is_frontier(value):
            shape_ok = has_frontier_shape(value)
            raise UserError("frontier.json has an invalid PR row" if shape_ok else "frontier.json has an invalid shape")
        return value

    def frontier_set(self, repo: str | Path, prs: list[int] | None = None) -> Frontier:
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

            drift = ([f"missing from resolved chain: {join(missing)}"] if missing else []) + (
                [f"extra in resolved chain: {join(extra)}"] if extra else []
            )
            raise UserError(
                "frontier pin mismatch: "
                + ("; ".join(drift) or f"order differs: expected {join(prs)}; resolved {join(actual)}")
            )
        result: Frontier = {
            "generation": old["generation"] + 1,
            "prs": rows,
            "lowestUnmerged": next((row["pr"] for row in rows if row["state"] == "OPEN"), None),
        }
        atomic_write(self.path / "frontier.json", json.dumps(result, indent=2) + "\n")
        return result

    def standing_show(self) -> list[StandingOrder]:
        rows: list[StandingOrder] = []
        raw = self.read("preferences.md").replace("\r", "")
        if not raw.strip():
            return rows
        for line in filter(None, raw.split("\n")):
            match = re.fullmatch(r"([1-9]\d*)\. (.+)", line)
            if not match or int(match[1]) != len(rows) + 1:
                raise UserError("preferences.md has malformed numbering")
            rows.append({"number": int(match[1]), "line": match[2]})
        return rows

    def standing_add(self, line: str) -> StandingOrder:
        self.begin_write()
        rows = self.standing_show()
        row: StandingOrder = {"number": len(rows) + 1, "line": required(line, "standing order", True)}
        atomic_write(self.path / "preferences.md", "".join(f"{r['number']}. {r['line']}\n" for r in [*rows, row]))
        return row

    def status(self) -> StatusReport:
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
            ["ID", "Track", "State", "Branch", "PR", "SHA", "Brief"], [row_cells(r, UNIT_FIELDS) for r in units]
        )
        text += f"\n\n## Verification ledger\n\nVerdicts: {count_line(summary['ledgerVerdicts'])}\n\n"
        text += table(
            ["PR", "SHA", "Verdict", "Evidence", "Verifier", "Timestamp"],
            [row_cells(r, LEDGER_FIELDS) for r in ledger],
        )
        text += (
            f"\n\n## Frontier\n\nGeneration: {frontier['generation']}\n"
            f"Lowest unmerged: {frontier['lowestUnmerged'] or 'none'}\n\n"
        )
        text += table(
            ["Branch", "PR", "SHA", "State"],
            [row_cells(r, ("branches", "pr", "sha", "state")) for r in frontier["prs"]],
        )
        text += "\n\n## Gates\n\n" + table(
            ["ID", "Status", "Question", "Options", "Default", "Answer"],
            [[r["id"], r["kind"], r["question"], r["options"], r["defaultAnswer"], r.get("answer", "")] for r in gates],
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
