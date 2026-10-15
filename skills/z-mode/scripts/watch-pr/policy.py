"""Deterministic PR readiness decisions and bounded polling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict, assert_never

from github import QueryError, Reader

if TYPE_CHECKING:
    from collections.abc import Callable

    from schema import (
        Blocker,
        BlockerVerdict,
        Check,
        Ci,
        CiBase,
        Context,
        Contribution,
        Event,
        FailingChecks,
        Failure,
        GateReason,
        GitHubMerge,
        Header,
        MergeConflicts,
        MergedPr,
        MergeGate,
        MergeState,
        Mode,
        PendingChecks,
        QueuedStackTimeout,
        ReviewThreads,
        RollupState,
        SinglePr,
        Snapshot,
        StackPrs,
        TimeoutReason,
        TimeoutVerdict,
        Verdict,
        WaitReason,
    )

type Stamp = Callable[[], Header]
type Emit = Callable[[Event], None]


@dataclass(frozen=True, kw_only=True)
class Options:
    interval: float
    sweep_interval: float
    timeout: float
    max_query_errors: int
    allow_draft: bool


class BlockerDecision(TypedDict):
    kind: Literal["blocker"]
    blocker: Blocker


class WaitingDecision(TypedDict):
    kind: Literal["waiting"]
    frontier: Context
    pending: list[Check]


class ClearDecision(TypedDict):
    kind: Literal["clear"]
    prs: list[Contribution]


type Decision = BlockerDecision | WaitingDecision | ClearDecision


@dataclass(frozen=True)
class Terminal:
    verdict: Verdict


@dataclass(frozen=True)
class Sleep:
    seconds: float
    reason: TimeoutReason


@dataclass(frozen=True)
class Continue:
    pass


type StepResult = Terminal | Sleep | Continue


class WatchClock(Protocol):
    def now(self) -> float: ...
    def observed_at(self) -> str: ...
    def sleep(self, seconds: float) -> None: ...


class Clock:
    def now(self) -> float:
        return time.monotonic()

    def observed_at(self) -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True)
class Deadline:
    """A --timeout budget; zero means unbounded."""

    clock: WatchClock
    started: float
    timeout: float

    def expired(self) -> bool:
        return self.timeout > 0 and self.clock.now() - self.started >= self.timeout

    def clamp(self, seconds: float) -> float:
        return max(0, min(seconds, self.started + self.timeout - self.clock.now())) if self.timeout > 0 else seconds


def assess_github_merge(state: MergeState, rollup: RollupState | None, owner_gate: bool = False) -> GitHubMerge:
    # GitHub counts an owner-approval gate awaiting action as a failing rollup; that block waits on a human.
    if state == "BLOCKED" and rollup in ("ERROR", "FAILURE"):
        # shortcut: a failure missing from the enumerated checks is indistinguishable from the gate here;
        # GitHub still blocks the merge until the owner approves, and landing re-checks current-head CI.
        if not owner_gate:
            return {"mergeStateStatus": state, "headRollupState": rollup, "kind": "refused"}
        basis: Literal["owner-gate", "rollup", "merge-state"] = "owner-gate"
    else:
        basis = "rollup" if state == "BLOCKED" else "merge-state"
    return {"mergeStateStatus": state, "headRollupState": rollup, "kind": "allowed", "basis": basis}


def read_snapshot(reader: Reader, context: Context, pending_history: str = "include") -> Snapshot:
    facts = reader.pull_request(context)
    if facts["state"] == "MERGED" or facts["mergedAt"] is not None:
        return {"kind": "merged", "context": context, "facts": facts}
    if facts["state"] == "CLOSED":
        return {"kind": "closed", "context": context, "facts": facts}
    threads, checks = reader.review_threads(context), reader.checks(context)
    failed = [c for c in checks["checks"] if c["kind"] == "failed"]
    pending = [c for c in checks["checks"] if c["kind"] == "pending"]
    base: CiBase = {
        "source": checks["source"],
        "all": checks["checks"],
        "failed": failed,
        "pending": pending,
        "hadPreviousPassingCi": False,
    }
    ci: Ci
    if not failed and pending and pending_history == "omit":
        ci = {**base, "kind": "ci-pending"}
    else:
        commits = reader.commit_rollups(context)
        head = next((c["state"] for c in commits if c["oid"] == facts["headRefOid"]), None)
        owner_gate = any(
            c["kind"] == "code-review-gate" and c["reportedState"] == "ACTION_REQUIRED" for c in checks["checks"]
        )
        github = assess_github_merge(facts["mergeStateStatus"], head, owner_gate)
        base["hadPreviousPassingCi"] = any(c["oid"] != facts["headRefOid"] and c["state"] == "SUCCESS" for c in commits)
        if failed:
            ci = {**base, "kind": "ci-failing", "github": github}
        elif github["kind"] == "refused":
            ci = {**base, "kind": "ci-github-rejected", "github": github}
        elif pending:
            ci = {**base, "kind": "ci-pending"}
        else:
            ci = {**base, "kind": "ci-clean", "github": github}
    return {
        "kind": "open",
        "context": context,
        "facts": facts,
        "threads": threads,
        "ci": ci,
        "reviewAutomationRunning": any(
            c["kind"] == "pending"
            and any(
                token in c["name"].lower()
                for token in ("bugbot", "security review", "pr review automation", "review automation")
            )
            for c in checks["checks"]
        ),
    }


def conflict_blocker(row: Snapshot) -> MergeConflicts | None:
    if row["kind"] == "open" and (
        row["facts"]["mergeable"] == "CONFLICTING" or row["facts"]["mergeStateStatus"] in ("DIRTY", "CONFLICTING")
    ):
        return {"kind": "merge-conflicts", "pr": row["context"], "facts": row["facts"]}
    return None


def thread_blocker(row: Snapshot) -> ReviewThreads | None:
    if row["kind"] == "open" and row["threads"]:
        return {"kind": "review-threads", "pr": row["context"], "threads": row["threads"]}
    return None


def ci_blocker(row: Snapshot) -> FailingChecks | None:
    if row["kind"] != "open":
        return None
    ci = row["ci"]
    if ci["kind"] == "ci-failing" or ci["kind"] == "ci-github-rejected":
        return {"kind": "failing-checks", "pr": row["context"], "ci": ci}
    return None


def gate_reason(row: Snapshot, allow_draft: bool) -> GateReason | None:
    if row["kind"] == "merged":
        return None
    if row["kind"] == "closed":
        return "closed-without-merge"
    if row["facts"]["isDraft"] and not allow_draft:
        return "draft-pr"
    if row["facts"]["reviewDecision"] == "CHANGES_REQUESTED":
        return "changes-requested"
    return None


def gate_blocker(row: Snapshot, allow_draft: bool) -> MergeGate | None:
    reason = gate_reason(row, allow_draft)
    # A draft only reaches gate_reason when open; its pending CI still has to settle first.
    if reason is None or (reason == "draft-pr" and row["kind"] == "open" and row["ci"]["kind"] == "ci-pending"):
        return None
    return {"kind": "merge-gate", "pr": row["context"], "reason": reason}


def ready_contribution(row: Snapshot, allow_draft: bool) -> Contribution | None:
    if row["kind"] == "merged":
        return {"kind": "merged-pr", "context": row["context"], "mergedAt": row["facts"]["mergedAt"]}
    if row["kind"] != "open":
        return None
    ci = row["ci"]
    if ci["kind"] != "ci-clean" or row["threads"] or conflict_blocker(row) or gate_reason(row, allow_draft):
        return None
    return {
        "kind": "ready-pr",
        "context": row["context"],
        "proof": {
            "mergeability": "clear",
            "threads": [],
            "ci": ci,
            "gate": {
                "state": "OPEN",
                "reviewDecision": row["facts"]["reviewDecision"],
                "draft": "draft-allowed" if row["facts"]["isDraft"] else "not-draft",
            },
        },
    }


def select_stack_decision(rows: list[Snapshot], allow_draft: bool = False) -> Decision:
    tiers: tuple[Callable[[Snapshot], Blocker | None], ...] = (
        conflict_blocker,
        thread_blocker,
        ci_blocker,
        lambda row: gate_blocker(row, allow_draft),
    )
    for tier in tiers:
        for row in rows:
            blocker = tier(row)
            if blocker is not None:
                return {"kind": "blocker", "blocker": blocker}
    for row in rows:
        if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending":
            return {"kind": "waiting", "frontier": row["context"], "pending": row["ci"]["pending"]}
    prs = [pr for row in rows if (pr := ready_contribution(row, allow_draft)) is not None]
    if not rows or len(prs) != len(rows):
        raise ValueError("stack has no classified decision")
    return {"kind": "clear", "prs": prs}


def verdict_factory(clock: WatchClock, mode: Mode) -> Stamp:
    sequence = 0

    def stamp() -> Header:
        nonlocal sequence
        sequence += 1
        return {"schemaVersion": 1, "sequence": sequence, "observedAt": clock.observed_at(), "mode": mode}

    return stamp


def blocker_exit_code(blocker: Blocker) -> int:
    match blocker["kind"]:
        case "merge-conflicts":
            return 2
        case "review-threads":
            return 3
        case "failing-checks":
            return 4
        case "merge-gate":
            return 6
        case "status-query":
            return 7
        case _ as unknown:
            assert_never(unknown)


def blocker_verdict(stamp: Stamp, blocker: Blocker) -> BlockerVerdict:
    return {**stamp(), "kind": "BLOCKER", "terminal": True, "exitCode": blocker_exit_code(blocker), "blocker": blocker}


def status_query_verdict(stamp: Stamp, failures: int, failure: Failure) -> BlockerVerdict:
    return blocker_verdict(stamp, {"kind": "status-query", "failures": failures, "failure": failure})


def timeout_verdict(stamp: Stamp, reason: TimeoutReason) -> TimeoutVerdict:
    return {**stamp(), "kind": "TIMEOUT", "terminal": True, "exitCode": 5, "reason": reason}


def poll(clock: WatchClock, emit: Emit, options: Options, stamp: Stamp, step: Callable[[], StepResult]) -> Verdict:
    deadline, failures = Deadline(clock, clock.now(), options.timeout), 0
    result: StepResult
    while True:
        try:
            result = step()
            failures = 0
        except QueryError as error:
            failures += 1
            if not error.failure["retryable"] or failures >= options.max_query_errors:
                return status_query_verdict(stamp, failures, error.failure)
            seconds = deadline.clamp(min(max(options.interval, 60) * 2 ** min(failures - 1, 10), 300))
            emit(
                {
                    **stamp(),
                    "kind": "RETRY",
                    "terminal": False,
                    "failure": error.failure,
                    "consecutiveFailures": failures,
                    "retryInSeconds": seconds,
                }
            )
            result = Sleep(seconds, {"kind": "status-unavailable", "failure": error.failure})
        match result:
            case Terminal(verdict):
                return verdict
            case Sleep(seconds, reason):
                if not deadline.expired():
                    clock.sleep(deadline.clamp(seconds))
                if deadline.expired():
                    return timeout_verdict(stamp, reason)
            case Continue():
                pass
            case _:
                assert_never(result)


def run_simple(
    reader: Reader,
    clock: WatchClock,
    emit: Emit,
    contexts: list[Context],
    options: Options,
    mode: Mode = "single",
    status_only: bool = False,
) -> Verdict:
    stamp = verdict_factory(clock, mode)

    def step() -> StepResult:
        rows = [read_snapshot(reader, context) for context in contexts]
        if status_only:
            return Terminal(
                {**stamp(), "kind": "STATUS", "terminal": True, "exitCode": 0, "reason": "status-only", "rows": rows}
            )
        if mode == "stack":
            emit({**stamp(), "kind": "STATUS", "terminal": False, "reason": "poll", "rows": rows})
        decision = select_stack_decision(rows, options.allow_draft)
        if decision["kind"] == "blocker":
            return Terminal(blocker_verdict(stamp, decision["blocker"]))
        if decision["kind"] == "clear":
            scope: SinglePr | StackPrs = (
                {"kind": "single", "pr": decision["prs"][0]}
                if mode == "single"
                else {"kind": "stack", "prs": decision["prs"]}
            )
            return Terminal({**stamp(), "kind": "READY", "terminal": True, "exitCode": 0, "scope": scope})
        reason: PendingChecks = {"kind": "pending-checks", "pending": decision["pending"]}
        emit({**stamp(), "kind": "WAITING", "terminal": False, "frontier": decision["frontier"], "reason": reason})
        return Sleep(options.interval, reason)

    return poll(clock, emit, options, stamp, step)


class QueuedWatcher:
    """Keep the frozen queue and partial sweep across individual polling attempts."""

    def __init__(
        self, reader: Reader, clock: WatchClock, emit: Emit, contexts: list[Context], options: Options
    ) -> None:
        self.reader, self.clock, self.emit = reader, clock, emit
        self.contexts, self.options = contexts, options
        self.stamp = verdict_factory(clock, "queued-stack")
        self.snapshots: dict[int, Snapshot] = {}
        self.work = list(contexts)
        self.next_sweep, self.deadline = clock.now(), Deadline(clock, clock.now(), options.timeout)
        self.frontier: Context | None = None
        self.last_wait: tuple[str, int, int] | None = None
        self.sweeping = True

    def complete(self, rows: list[Snapshot]) -> Terminal:
        merged: list[MergedPr] = [
            {"kind": "merged-pr", "context": row["context"], "mergedAt": row["facts"]["mergedAt"]}
            for row in rows
            if row["kind"] == "merged"
        ]
        return Terminal(
            {
                **self.stamp(),
                "kind": "COMPLETE",
                "terminal": True,
                "exitCode": 0,
                "queue": self.contexts,
                "merged": merged,
            }
        )

    def step(self) -> StepResult:
        if not self.work:
            active = [c for c in self.contexts if self.snapshots[c["number"]]["kind"] != "merged"]
            if not active:
                return self.complete([self.snapshots[c["number"]] for c in self.contexts])
            self.sweeping = self.clock.now() >= self.next_sweep
            self.work = list(active) if self.sweeping else [active[0]]
        context = self.work[0]
        # Leave the sweep head in place until all reads succeed, so retries resume here.
        self.snapshots[context["number"]] = read_snapshot(self.reader, context, pending_history="omit")
        self.work.pop(0)
        if self.work:
            return Continue()
        rows = [self.snapshots[c["number"]] for c in self.contexts]
        if self.sweeping:
            self.next_sweep = self.clock.now() + self.options.sweep_interval
            self.emit(
                {**self.stamp(), "kind": "STATUS", "terminal": False, "reason": "whole-stack-sweep", "rows": rows}
            )
        return self.evaluate(rows)

    def evaluate(self, rows: list[Snapshot]) -> StepResult:
        active: list[Snapshot] = [r for r in rows if r["kind"] != "merged"]
        if not active:
            return self.complete(rows)
        decision = select_stack_decision(active, self.options.allow_draft)
        if decision["kind"] == "blocker":
            return Terminal(blocker_verdict(self.stamp, decision["blocker"]))
        current = active[0]["context"]
        if self.frontier is not None and self.frontier["number"] != current["number"]:
            self.emit(
                {
                    **self.stamp(),
                    "kind": "ADVANCE",
                    "terminal": False,
                    "merged": self.frontier,
                    "frontier": current,
                    "remaining": len(active),
                }
            )
            self.frontier, self.last_wait = current, None
            return Continue()
        self.frontier = current
        timeout: QueuedStackTimeout = {"kind": "queued-stack", "frontier": current, "unmergedCount": len(active)}
        if self.deadline.expired():
            return Terminal(timeout_verdict(self.stamp, timeout))
        row = active[0]
        reason: WaitReason
        if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending":
            reason = {"kind": "pending-checks", "pending": row["ci"]["pending"]}
            key = ("pending", current["number"], len(row["ci"]["pending"]))
        else:
            reason = {"kind": "merge-queue", "unmergedCount": len(active)}
            key = ("queue", current["number"], len(active))
        if key != self.last_wait:
            self.emit({**self.stamp(), "kind": "WAITING", "terminal": False, "frontier": current, "reason": reason})
        self.last_wait = key
        return Sleep(self.options.interval, timeout)


def run_queued(reader: Reader, clock: WatchClock, emit: Emit, contexts: list[Context], options: Options) -> Verdict:
    watcher = QueuedWatcher(reader, clock, emit, contexts, options)
    emit({**watcher.stamp(), "kind": "QUEUE", "terminal": False, "queue": contexts})
    return poll(clock, emit, options, watcher.stamp, watcher.step)
