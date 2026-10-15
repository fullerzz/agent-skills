"""NDJSON event contract emitted by the watcher; every nested shape here reaches stdout.

TypedDicts serialize as plain dicts, so the producers' dict literals fix key order, not these classes.
"""

from __future__ import annotations

from typing import Literal, TypedDict

type Mode = Literal["single", "stack", "queued-stack"]
type MergeState = Literal[
    "BEHIND", "BLOCKED", "CLEAN", "CONFLICTING", "DIRTY", "DRAFT", "HAS_HOOKS", "UNKNOWN", "UNSTABLE"
]
type RollupState = Literal["ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS"]
type ReviewDecision = Literal["APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED"]
type Mergeable = Literal["MERGEABLE", "CONFLICTING", "UNKNOWN"]
type PrState = Literal["OPEN", "CLOSED", "MERGED"]
type CheckKind = Literal["passed", "failed", "pending", "skipped", "code-review-gate"]
type CheckSource = Literal["gh-pr-checks", "graphql-rollup"]
MERGE_STATES: tuple[MergeState, ...] = (
    "BEHIND",
    "BLOCKED",
    "CLEAN",
    "CONFLICTING",
    "DIRTY",
    "DRAFT",
    "HAS_HOOKS",
    "UNKNOWN",
    "UNSTABLE",
)
ROLLUP_STATES: tuple[RollupState, ...] = ("ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS")
REVIEW_DECISIONS: tuple[ReviewDecision, ...] = ("APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED")
MERGEABLE: tuple[Mergeable, ...] = ("MERGEABLE", "CONFLICTING", "UNKNOWN")
PR_STATES: tuple[PrState, ...] = ("OPEN", "CLOSED", "MERGED")


class Repo(TypedDict):
    owner: str
    repo: str


class Context(Repo):
    number: int


class FailureExtra(TypedDict, total=False):
    code: int
    rawValue: str


class Failure(FailureExtra):
    kind: str
    retryable: bool
    detail: str


class CheckDetails(TypedDict):
    name: str
    description: str
    link: str
    workflow: str


class Check(CheckDetails):
    kind: CheckKind
    reportedState: str


class PullRequestFacts(TypedDict):
    context: Context
    isDraft: bool
    mergeable: Mergeable
    mergeStateStatus: MergeState
    state: PrState
    reviewDecision: ReviewDecision | None
    headRefOid: str | None
    mergedAt: str | None
    headRefName: str
    baseRefName: str


class Comment(TypedDict):
    authorLogin: str | None
    body: str
    path: str | None
    line: int | None
    createdAt: str


class Thread(TypedDict):
    id: str
    firstComment: Comment | None
    isBugbot: bool
    bugbotReviewPasses: int


class AllowedMerge(TypedDict):
    mergeStateStatus: MergeState
    headRollupState: RollupState | None
    kind: Literal["allowed"]
    basis: Literal["owner-gate", "rollup", "merge-state"]


class RefusedMerge(TypedDict):
    mergeStateStatus: MergeState
    headRollupState: RollupState | None
    kind: Literal["refused"]


type GitHubMerge = AllowedMerge | RefusedMerge


class CiBase(TypedDict):
    source: CheckSource
    all: list[Check]
    failed: list[Check]
    pending: list[Check]
    hadPreviousPassingCi: bool


class PendingCi(CiBase):
    kind: Literal["ci-pending"]


class FailingCi(CiBase):
    kind: Literal["ci-failing"]
    github: GitHubMerge


class RejectedCi(CiBase):
    kind: Literal["ci-github-rejected"]
    github: RefusedMerge


class CleanCi(CiBase):
    kind: Literal["ci-clean"]
    github: AllowedMerge


type Ci = PendingCi | FailingCi | RejectedCi | CleanCi


class MergedRow(TypedDict):
    kind: Literal["merged"]
    context: Context
    facts: PullRequestFacts


class ClosedRow(TypedDict):
    kind: Literal["closed"]
    context: Context
    facts: PullRequestFacts


class OpenRow(TypedDict):
    kind: Literal["open"]
    context: Context
    facts: PullRequestFacts
    threads: list[Thread]
    ci: Ci
    reviewAutomationRunning: bool


type Snapshot = MergedRow | ClosedRow | OpenRow
type GateReason = Literal["closed-without-merge", "draft-pr", "changes-requested"]


class MergeConflicts(TypedDict):
    kind: Literal["merge-conflicts"]
    pr: Context
    facts: PullRequestFacts


class ReviewThreads(TypedDict):
    kind: Literal["review-threads"]
    pr: Context
    threads: list[Thread]


class FailingChecks(TypedDict):
    kind: Literal["failing-checks"]
    pr: Context
    ci: FailingCi | RejectedCi


class MergeGate(TypedDict):
    kind: Literal["merge-gate"]
    pr: Context
    reason: GateReason


class StatusQuery(TypedDict):
    kind: Literal["status-query"]
    failures: int
    failure: Failure


type Blocker = MergeConflicts | ReviewThreads | FailingChecks | MergeGate | StatusQuery


class MergedPr(TypedDict):
    kind: Literal["merged-pr"]
    context: Context
    mergedAt: str | None


class GateProof(TypedDict):
    state: Literal["OPEN"]
    reviewDecision: ReviewDecision | None
    draft: Literal["draft-allowed", "not-draft"]


class ReadyProof(TypedDict):
    mergeability: Literal["clear"]
    threads: list[Thread]
    ci: CleanCi
    gate: GateProof


class ReadyPr(TypedDict):
    kind: Literal["ready-pr"]
    context: Context
    proof: ReadyProof


type Contribution = MergedPr | ReadyPr


class PendingChecks(TypedDict):
    kind: Literal["pending-checks"]
    pending: list[Check]


class MergeQueue(TypedDict):
    kind: Literal["merge-queue"]
    unmergedCount: int


class QueuedStackTimeout(TypedDict):
    kind: Literal["queued-stack"]
    frontier: Context
    unmergedCount: int


class StatusUnavailable(TypedDict):
    kind: Literal["status-unavailable"]
    failure: Failure


type WaitReason = PendingChecks | MergeQueue
type TimeoutReason = PendingChecks | QueuedStackTimeout | StatusUnavailable


class SinglePr(TypedDict):
    kind: Literal["single"]
    pr: Contribution


class StackPrs(TypedDict):
    kind: Literal["stack"]
    prs: list[Contribution]


class Header(TypedDict):
    schemaVersion: Literal[1]
    sequence: int
    observedAt: str
    mode: Mode


class NonTerminalHeader(Header):
    terminal: Literal[False]


class TerminalHeader(Header):
    terminal: Literal[True]
    exitCode: int


class StatusEvent(NonTerminalHeader):
    kind: Literal["STATUS"]
    reason: Literal["poll", "whole-stack-sweep"]
    rows: list[Snapshot]


class QueueEvent(NonTerminalHeader):
    kind: Literal["QUEUE"]
    queue: list[Context]


class WaitingEvent(NonTerminalHeader):
    kind: Literal["WAITING"]
    frontier: Context
    reason: WaitReason


class AdvanceEvent(NonTerminalHeader):
    kind: Literal["ADVANCE"]
    merged: Context
    frontier: Context
    remaining: int


class RetryEvent(NonTerminalHeader):
    kind: Literal["RETRY"]
    failure: Failure
    consecutiveFailures: int
    retryInSeconds: float


class StatusVerdict(TerminalHeader):
    kind: Literal["STATUS"]
    reason: Literal["status-only"]
    rows: list[Snapshot]


class BlockerVerdict(TerminalHeader):
    kind: Literal["BLOCKER"]
    blocker: Blocker


class ReadyVerdict(TerminalHeader):
    kind: Literal["READY"]
    scope: SinglePr | StackPrs


class CompleteVerdict(TerminalHeader):
    kind: Literal["COMPLETE"]
    queue: list[Context]
    merged: list[MergedPr]


class TimeoutVerdict(TerminalHeader):
    kind: Literal["TIMEOUT"]
    reason: TimeoutReason


type Verdict = StatusVerdict | BlockerVerdict | ReadyVerdict | CompleteVerdict | TimeoutVerdict
type Event = StatusEvent | QueueEvent | WaitingEvent | AdvanceEvent | RetryEvent | Verdict
