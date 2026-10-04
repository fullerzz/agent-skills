"""Deterministic PR readiness decisions and bounded polling."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from github import QueryError, Reader, resolve_checks

type Stamp = Callable[[dict[str, Any]], dict[str, Any]]
type Emit = Callable[[dict[str, Any]], None]


class WatchClock(Protocol):
    def now(self) -> float: ...
    def observed_at(self) -> str: ...
    def sleep(self, seconds: float) -> None: ...


class Clock:
    def now(self) -> float:
        return time.monotonic()

    def observed_at(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def assess_github_merge(state: str, rollup: str | None) -> dict[str, Any]:
    base = {"mergeStateStatus": state, "headRollupState": rollup}
    if state == "BLOCKED" and rollup in ("ERROR", "FAILURE"):
        return base | {"kind": "refused"}
    return base | {"kind": "allowed", "basis": "rollup" if state == "BLOCKED" else "merge-state"}


def read_snapshot(reader: Reader, context: dict[str, Any], pending_history: str = "include") -> dict[str, Any]:
    facts = reader.pull_request(context)
    if facts["state"] == "MERGED" or facts["mergedAt"] is not None:
        return {"kind": "merged", "context": context, "facts": facts}
    if facts["state"] == "CLOSED":
        return {"kind": "closed", "context": context, "facts": facts}
    threads, checks = reader.review_threads(context), resolve_checks(reader, context)
    failed = [c for c in checks["checks"] if c["kind"] == "failed"]
    pending = [c for c in checks["checks"] if c["kind"] == "pending"]
    ci = {
        "source": checks["source"],
        "all": checks["checks"],
        "failed": failed,
        "pending": pending,
        "hadPreviousPassingCi": False,
    }
    if not failed and pending and pending_history == "omit":
        ci["kind"] = "ci-pending"
    else:
        commits = reader.commit_rollups(context)
        head = next((c["state"] for c in commits if c["oid"] == facts["headRefOid"]), None)
        github = assess_github_merge(facts["mergeStateStatus"], head)
        ci["hadPreviousPassingCi"] = any(c["oid"] != facts["headRefOid"] and c["state"] == "SUCCESS" for c in commits)
        ci["kind"] = (
            "ci-failing"
            if failed
            else "ci-github-rejected"
            if github["kind"] == "refused"
            else "ci-pending"
            if pending
            else "ci-clean"
        )
        if ci["kind"] != "ci-pending":
            ci["github"] = github
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


def conflict_blocker(row: dict[str, Any]) -> dict[str, Any] | None:
    if row["kind"] == "open" and (
        row["facts"]["mergeable"] == "CONFLICTING" or row["facts"]["mergeStateStatus"] in ("DIRTY", "CONFLICTING")
    ):
        return {"kind": "merge-conflicts", "pr": row["context"], "facts": row["facts"]}
    return None


def thread_blocker(row: dict[str, Any]) -> dict[str, Any] | None:
    if row["kind"] == "open" and row["threads"]:
        return {"kind": "review-threads", "pr": row["context"], "threads": row["threads"]}
    return None


def ci_blocker(row: dict[str, Any]) -> dict[str, Any] | None:
    if row["kind"] == "open" and row["ci"]["kind"] in ("ci-failing", "ci-github-rejected"):
        return {"kind": "failing-checks", "pr": row["context"], "ci": row["ci"]}
    return None


def gate_reason(row: dict[str, Any], allow_draft: bool) -> str | None:
    if row["kind"] == "merged":
        return None
    if row["kind"] == "closed":
        return "closed-without-merge"
    if row["facts"]["isDraft"] and not allow_draft:
        return "draft-pr"
    if row["facts"]["reviewDecision"] == "CHANGES_REQUESTED":
        return "changes-requested"
    return None


def gate_blocker(row: dict[str, Any], allow_draft: bool) -> dict[str, Any] | None:
    reason = gate_reason(row, allow_draft)
    if reason is not None and not (reason == "draft-pr" and row["ci"]["kind"] == "ci-pending"):
        return {"kind": "merge-gate", "pr": row["context"], "reason": reason}
    return None


def ready_contribution(row: dict[str, Any], allow_draft: bool) -> dict[str, Any] | None:
    if row["kind"] == "merged":
        return {"kind": "merged-pr", "context": row["context"], "mergedAt": row["facts"]["mergedAt"]}
    if (
        row["kind"] != "open"
        or row["ci"]["kind"] != "ci-clean"
        or row["threads"]
        or conflict_blocker(row)
        or gate_reason(row, allow_draft)
    ):
        return None
    return {
        "kind": "ready-pr",
        "context": row["context"],
        "proof": {
            "mergeability": "clear",
            "threads": [],
            "ci": row["ci"],
            "gate": {
                "state": "OPEN",
                "reviewDecision": row["facts"]["reviewDecision"],
                "draft": "draft-allowed" if row["facts"]["isDraft"] else "not-draft",
            },
        },
    }


def select_stack_decision(rows: list[dict[str, Any]], allow_draft: bool = False) -> dict[str, Any]:
    for tier in (conflict_blocker, thread_blocker, ci_blocker, lambda row: gate_blocker(row, allow_draft)):
        for row in rows:
            blocker = tier(row)
            if blocker is not None:
                return {"kind": "blocker", "blocker": blocker}
    for row in rows:
        if row["kind"] == "open" and row["ci"]["kind"] == "ci-pending":
            return {"kind": "waiting", "frontier": row["context"], "pending": row["ci"]["pending"]}
    prs = [ready_contribution(row, allow_draft) for row in rows]
    if not prs or any(pr is None for pr in prs):
        raise ValueError("stack has no classified decision")
    return {"kind": "clear", "prs": prs}


def verdict_factory(clock: WatchClock, mode: str) -> Stamp:
    sequence = 0

    def stamp(payload: dict[str, Any]) -> dict[str, Any]:
        nonlocal sequence
        sequence += 1
        return {"schemaVersion": 1, "sequence": sequence, "observedAt": clock.observed_at(), "mode": mode} | payload

    return stamp


def blocker_verdict(stamp: Stamp, blocker: dict[str, Any]) -> dict[str, Any]:
    code = {"merge-conflicts": 2, "review-threads": 3, "failing-checks": 4, "merge-gate": 6, "status-query": 7}[
        blocker["kind"]
    ]
    return stamp({"kind": "BLOCKER", "terminal": True, "exitCode": code, "blocker": blocker})


def status_query_verdict(stamp: Stamp, failures: int, failure: dict[str, Any]) -> dict[str, Any]:
    return blocker_verdict(stamp, {"kind": "status-query", "failures": failures, "failure": failure})


def timeout_verdict(stamp: Stamp, reason: dict[str, Any]) -> dict[str, Any]:
    return stamp({"kind": "TIMEOUT", "terminal": True, "exitCode": 5, "reason": reason})


def poll(
    clock: WatchClock, emit: Emit, options: dict[str, Any], stamp: Stamp, step: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    started, failures = clock.now(), 0

    def expired() -> bool:
        return options["timeout"] > 0 and clock.now() - started >= options["timeout"]

    def delay(seconds: float) -> float:
        return max(0, min(seconds, started + options["timeout"] - clock.now())) if options["timeout"] > 0 else seconds

    result: dict[str, Any]
    while True:
        try:
            result = step()
            failures = 0
        except QueryError as error:
            failures += 1
            if not error.failure["retryable"] or failures >= options["maxQueryErrors"]:
                return status_query_verdict(stamp, failures, error.failure)
            seconds = delay(min(max(options["interval"], 60) * 2 ** min(failures - 1, 10), 300))
            emit(
                stamp(
                    {
                        "kind": "RETRY",
                        "terminal": False,
                        "failure": error.failure,
                        "consecutiveFailures": failures,
                        "retryInSeconds": seconds,
                    }
                )
            )
            result = {
                "kind": "sleep",
                "seconds": seconds,
                "reason": {"kind": "status-unavailable", "failure": error.failure},
            }
        if result["kind"] == "terminal":
            return result["verdict"]
        if result["kind"] == "sleep":
            if not expired():
                clock.sleep(delay(result["seconds"]))
            if expired():
                return timeout_verdict(stamp, result["reason"])


def run_simple(
    reader: Reader,
    clock: WatchClock,
    emit: Emit,
    contexts: list[dict[str, Any]],
    options: dict[str, Any],
    mode: str = "single",
    status_only: bool = False,
) -> dict[str, Any]:
    stamp = verdict_factory(clock, mode)

    def step() -> dict[str, Any]:
        rows = [read_snapshot(reader, context) for context in contexts]
        if status_only:
            verdict = stamp({"kind": "STATUS", "terminal": True, "exitCode": 0, "reason": "status-only", "rows": rows})
            return {"kind": "terminal", "verdict": verdict}
        if mode == "stack":
            emit(stamp({"kind": "STATUS", "terminal": False, "reason": "poll", "rows": rows}))
        decision = select_stack_decision(rows, options["allowDraft"])
        if decision["kind"] == "blocker":
            return {"kind": "terminal", "verdict": blocker_verdict(stamp, decision["blocker"])}
        if decision["kind"] == "clear":
            scope = (
                {"kind": "single", "pr": decision["prs"][0]}
                if mode == "single"
                else {"kind": "stack", "prs": decision["prs"]}
            )
            return {
                "kind": "terminal",
                "verdict": stamp({"kind": "READY", "terminal": True, "exitCode": 0, "scope": scope}),
            }
        reason = {"kind": "pending-checks", "pending": decision["pending"]}
        emit(stamp({"kind": "WAITING", "terminal": False, "frontier": decision["frontier"], "reason": reason}))
        return {"kind": "sleep", "seconds": options["interval"], "reason": reason}

    return poll(clock, emit, options, stamp, step)


class QueuedWatcher:
    """Keep the frozen queue and partial sweep across individual polling attempts."""

    def __init__(
        self, reader: Reader, clock: WatchClock, emit: Emit, contexts: list[dict[str, Any]], options: dict[str, Any]
    ) -> None:
        self.reader, self.clock, self.emit = reader, clock, emit
        self.contexts, self.options = contexts, options
        self.stamp = verdict_factory(clock, "queued-stack")
        self.snapshots: dict[int, dict[str, Any]] = {}
        self.work = list(contexts)
        self.next_sweep, self.started = clock.now(), clock.now()
        self.frontier: dict[str, Any] | None = None
        self.last_wait: tuple[str, int, int] | None = None
        self.sweeping = True

    def complete(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "kind": "terminal",
            "verdict": self.stamp(
                {
                    "kind": "COMPLETE",
                    "terminal": True,
                    "exitCode": 0,
                    "queue": self.contexts,
                    "merged": [ready_contribution(row, self.options["allowDraft"]) for row in rows],
                }
            ),
        }

    def step(self) -> dict[str, Any]:
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
            return {"kind": "continue"}
        rows = [self.snapshots[c["number"]] for c in self.contexts]
        if self.sweeping:
            self.next_sweep = self.clock.now() + self.options["sweepInterval"]
            self.emit(self.stamp({"kind": "STATUS", "terminal": False, "reason": "whole-stack-sweep", "rows": rows}))
        return self.evaluate(rows)

    def evaluate(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        active = [r for r in rows if r["kind"] != "merged"]
        if not active:
            return self.complete(rows)
        decision = select_stack_decision(active, self.options["allowDraft"])
        if decision["kind"] == "blocker":
            return {"kind": "terminal", "verdict": blocker_verdict(self.stamp, decision["blocker"])}
        current = active[0]["context"]
        if self.frontier is not None and self.frontier["number"] != current["number"]:
            self.emit(
                self.stamp(
                    {
                        "kind": "ADVANCE",
                        "terminal": False,
                        "merged": self.frontier,
                        "frontier": current,
                        "remaining": len(active),
                    }
                )
            )
            self.frontier, self.last_wait = current, None
            return {"kind": "continue"}
        self.frontier = current
        timeout = {"kind": "queued-stack", "frontier": current, "unmergedCount": len(active)}
        if self.options["timeout"] > 0 and self.clock.now() - self.started >= self.options["timeout"]:
            return {"kind": "terminal", "verdict": timeout_verdict(self.stamp, timeout)}
        row = active[0]
        if row["ci"]["kind"] == "ci-pending":
            reason = {"kind": "pending-checks", "pending": row["ci"]["pending"]}
            key = ("pending", current["number"], len(row["ci"]["pending"]))
        else:
            reason = {"kind": "merge-queue", "unmergedCount": len(active)}
            key = ("queue", current["number"], len(active))
        if key != self.last_wait:
            self.emit(self.stamp({"kind": "WAITING", "terminal": False, "frontier": current, "reason": reason}))
        self.last_wait = key
        return {"kind": "sleep", "seconds": self.options["interval"], "reason": timeout}


def run_queued(
    reader: Reader, clock: WatchClock, emit: Emit, contexts: list[dict[str, Any]], options: dict[str, Any]
) -> dict[str, Any]:
    watcher = QueuedWatcher(reader, clock, emit, contexts, options)
    emit(watcher.stamp({"kind": "QUEUE", "terminal": False, "queue": contexts}))
    return poll(clock, emit, options, watcher.stamp, watcher.step)
