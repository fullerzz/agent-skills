"""Read-only gh adapter with fail-closed response parsing."""

from __future__ import annotations

import json
import re
import subprocess
from typing import TYPE_CHECKING, Literal, NoReturn, Protocol, TypedDict, Unpack
from urllib.parse import urlsplit

from schema import MERGE_STATES, MERGEABLE, PR_STATES, REVIEW_DECISIONS, ROLLUP_STATES

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from schema import (
        Check,
        CheckDetails,
        CheckKind,
        CheckSource,
        Comment,
        Context,
        Failure,
        FailureExtra,
        PullRequestFacts,
        Repo,
        RollupState,
        Thread,
    )

REVIEW_THREADS_QUERY = """query ReviewThreads($owner: String!, $repo: String!, $pr: Int!, $after: String) {
 repository(owner: $owner, name: $repo) { pullRequest(number: $pr) {
 reviewThreads(first: 100, after: $after) { pageInfo { hasNextPage endCursor }
 nodes { id isResolved comments(first: 10) { nodes { body createdAt path line author { login } } } } }
 } } }"""
PR_COMMIT_STATUS_QUERY = """query PrCommitStatuses($owner: String!, $repo: String!, $pr: Int!) {
 repository(owner: $owner, name: $repo) { pullRequest(number: $pr) {
 commits(last: 50) { nodes { commit { oid statusCheckRollup { state } } } } } } }"""
PR_CHECK_ROLLUP_QUERY = """query PrCheckRollup($owner: String!, $repo: String!, $pr: Int!, $after: String) {
 repository(owner: $owner, name: $repo) { pullRequest(number: $pr) { commits(last: 1) { nodes {
 commit { statusCheckRollup { contexts(first: 100, after: $after) { pageInfo { hasNextPage endCursor }
 nodes { __typename ... on CheckRun { name status conclusion detailsUrl }
 ... on StatusContext { context state targetUrl } } } } } } } } } }"""
PR_COMMENTS_QUERY = """query PrComments($owner: String!, $repo: String!, $pr: Int!, $after: String) {
 repository(owner: $owner, name: $repo) { pullRequest(number: $pr) {
 comments(first: 100, after: $after) { pageInfo { hasNextPage endCursor } nodes { body url author { login } } }
 } } }"""
# The Codex connector reports review progress by editing one PR comment, not through a check.
CODEX_AUTHORS = ("chatgpt-codex-connector", "chatgpt-codex-connector[bot]")
CODEX_MARKER = "<!-- codex-review-state:v1"
# Observed statuses are "running" and "completed"; the rest of this set is assumed. Any other status
# fails, so an unknown terminal state stops the watch instead of waiting without a bound.
CODEX_ACTIVE = ("queued", "pending", "running", "in_progress")
CODEX_REVIEWS = (("code_review", "Codex code review"), ("security_review", "Codex security review"))
MISSING = object()


class OpenPullRequest(TypedDict):
    number: int
    headRefName: str
    baseRefName: str


class FastChecks(TypedDict):
    kind: Literal["checks"]
    checks: list[Check]


class UnusableChecks(TypedDict):
    kind: Literal["unusable"]
    exitCode: int
    stderr: str


class RollupPage(TypedDict):
    checks: list[Check]
    endCursor: str | None


class CommitRollup(TypedDict):
    oid: str
    state: RollupState | None


class ResolvedChecks(TypedDict):
    source: CheckSource
    checks: list[Check]


class QueryError(Exception):
    def __init__(self, kind: str, detail: str, retryable: bool = True, **extra: Unpack[FailureExtra]) -> None:
        super().__init__(detail)
        self.failure: Failure = {"kind": kind, "retryable": retryable, "detail": detail, **extra}


def first_line(value: str) -> str:
    return value.strip().split("\n")[0][:240]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 - Fixed Git/gh/glab argument vectors from local callers; no shell.
            argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8"
        )
    except OSError as error:
        raise QueryError("command-exit", str(error), code=127) from error


def parse_json(text: str, label: str) -> object:
    try:
        return json.loads(text)
    except ValueError as error:
        raise QueryError("json-parse", f"{label}: {error}") from error


def run_json(argv: list[str]) -> object:
    result = run(argv)
    if result.returncode:
        raise QueryError(
            "command-exit",
            first_line(result.stderr) or f"{' '.join(argv)} exited {result.returncode}",
            code=result.returncode,
        )
    return parse_json(result.stdout, " ".join(argv))


def missing(path: str, value: object = MISSING) -> NoReturn:
    if value is MISSING:
        raise QueryError("missing-key", f"missing {path}")
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise QueryError("missing-key", f"invalid {path}: {raw}", rawValue=raw)


def record(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        missing(path, value)
    return value


def array(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        missing(path, value)
    return value


def at(value: object, *path: str) -> object:
    for key in path:
        value = record(value, ".".join(path))
        if key not in value:
            missing(".".join(path))
        value = value[key]
    return value


def string(value: object, path: str) -> str:
    if not isinstance(value, str):
        missing(path, value)
    return value


def nullable_string(value: object, path: str) -> str | None:
    return None if value is None else string(value, path)


def enum[T: str](value: object, values: Sequence[T], path: str) -> T:
    for choice in values:
        if value == choice:
            return choice
    missing(path, value)


def optional_enum[T: str](value: object, values: Sequence[T], path: str) -> T | None:
    return None if value is None else enum(value, values, path)


def pr_number(value: object) -> int:
    if type(value) is not int or not 0 < value <= 2**53 - 1:
        raise ValueError("PR must be a positive integer")
    return value


def canonical_parts(value: str) -> list[str]:
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or url.hostname != "github.com"
        or url.port
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("not a canonical GitHub URL")
    return [part for part in url.path.split("/") if part]


def parse_remote(value: str) -> Repo | None:
    value = value.strip()
    for prefix in ("git@github.com:", "ssh://git@github.com/"):
        if value.startswith(prefix):
            value = "https://github.com/" + value[len(prefix) :]
    try:
        parts = canonical_parts(value.removesuffix(".git"))
        return {"owner": parts[0], "repo": parts[1]} if len(parts) == 2 else None
    except ValueError:
        return None


def parse_pr_url(value: str) -> Context:
    try:
        parts = canonical_parts(value)
        if len(parts) != 4 or parts[2] != "pull":
            raise ValueError("not a canonical GitHub pull URL")
        return {"owner": parts[0], "repo": parts[1], "number": pr_number(int(parts[3]))}
    except ValueError as error:
        raise QueryError(
            "invalid-context-url", f"could not infer owner/repo from PR URL: {value} ({error})", False, rawValue=value
        ) from error


def optional_text(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    return item if isinstance(item, str) else ""


def details(value: dict[str, object], name_key: str) -> CheckDetails:
    return {
        "name": string(value.get(name_key), name_key),
        "description": optional_text(value, "description"),
        "link": next((link for k in ("link", "detailsUrl") if isinstance(link := value.get(k), str)), ""),
        "workflow": optional_text(value, "workflow"),
    }


def check(base: CheckDetails, kind: CheckKind, state: str) -> Check:
    return {**base, "kind": kind, "reportedState": state}


# The owner-approval gate waits on a human, so it counts as neither pending nor failed.
def gate_or(kind: CheckKind, value: CheckDetails, state: str) -> Check:
    return check(value, "code-review-gate" if value["name"] == "Code Review Gate" else kind, state)


def parse_fast_check(value: object) -> Check:
    value = record(value, "check")
    base = details(value, "name")
    state = string(value.get("state"), "check.state").upper()
    bucket = string(value.get("bucket"), "check.bucket")
    if state == "ACTION_REQUIRED":
        return gate_or("failed", base, state)
    kind: CheckKind
    if bucket == "fail" or state in ("FAILURE", "ERROR"):
        kind = "failed"
    elif bucket == "pending":
        return gate_or("pending", base, state)
    else:
        kind = "passed" if bucket == "pass" else "skipped" if bucket == "skipping" else "failed"
    return check(base, kind, state)


def map_rollup_node(value: object) -> Check | None:
    value = record(value, "rollup node")
    typename = value.get("__typename")
    if typename not in ("CheckRun", "StatusContext"):
        return None
    base = details(value, "name" if typename == "CheckRun" else "context")
    if isinstance(target := value.get("targetUrl"), str):
        base["link"] = target
    kind: CheckKind
    if typename == "CheckRun":
        status, conclusion = str(value.get("status") or "").upper(), str(value.get("conclusion") or "").upper()
        if status != "COMPLETED":
            return gate_or("pending", base, "PENDING")
        if conclusion == "ACTION_REQUIRED":
            return gate_or("failed", base, conclusion)
        kind = "passed" if conclusion == "SUCCESS" else "skipped" if conclusion in ("NEUTRAL", "SKIPPED") else "failed"
        state = conclusion if conclusion in ("SUCCESS", "NEUTRAL", "SKIPPED") else "FAILURE"
    else:
        state = str(value.get("state") or "").upper()
        if state in ("PENDING", "EXPECTED"):
            return gate_or("pending", base, "PENDING")
        kind = "passed" if state == "SUCCESS" else "failed"
        state = state or "FAILURE"
    return check(base, kind, state)


def parse_pull_request(value: object, context: Context) -> PullRequestFacts:
    value = record(value, "pull request")
    is_draft = value.get("isDraft")
    if not isinstance(is_draft, bool):
        missing("pull request.isDraft", is_draft)
    return {
        "context": context,
        "isDraft": is_draft,
        "mergeable": enum(at(value, "mergeable"), MERGEABLE, "pull request.mergeable"),
        "mergeStateStatus": enum(at(value, "mergeStateStatus"), MERGE_STATES, "pull request.mergeStateStatus"),
        "state": enum(at(value, "state"), PR_STATES, "pull request.state"),
        # gh pr view reports a missing review decision as "".
        "reviewDecision": optional_enum(
            None if (decision := at(value, "reviewDecision")) == "" else decision,
            REVIEW_DECISIONS,
            "pull request.reviewDecision",
        ),
        "headRefOid": nullable_string(at(value, "headRefOid"), "pull request.headRefOid"),
        "mergedAt": nullable_string(at(value, "mergedAt"), "pull request.mergedAt"),
        "headRefName": string(at(value, "headRefName"), "pull request.headRefName"),
        "baseRefName": string(at(value, "baseRefName"), "pull request.baseRefName"),
    }


def parse_comment(value: object) -> Comment:
    value = record(value, "review comment")
    author = at(value, "author")
    line = at(value, "line")
    if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
        missing("review comment.line", line)
    return {
        "authorLogin": None if author is None else nullable_string(at(author, "login"), "author.login"),
        "body": string(at(value, "body"), "comment.body"),
        "path": nullable_string(at(value, "path"), "comment.path"),
        "line": line,
        "createdAt": string(at(value, "createdAt"), "comment.createdAt"),
    }


def is_bugbot(comment: Comment | None) -> bool:
    if comment is None:
        return False
    author, body = (comment["authorLogin"] or "").lower(), comment["body"].lower()
    return "bugbot" in author or (
        author == "cursor"
        and any(
            token in body
            for token in ("bugbot", "cursor_automation_id", "agentic security review", "description start", "severity")
        )
    )


def parse_review_threads(value: object) -> list[Thread]:
    nodes = array(at(value, "data", "repository", "pullRequest", "reviewThreads", "nodes"), "reviewThreads.nodes")
    unresolved: list[tuple[str, Comment | None, bool]] = []
    keys: set[str] = set()
    keyless = False
    for raw in nodes:
        node = record(raw, "review thread")
        resolved = node.get("isResolved")
        if not isinstance(resolved, bool):
            missing("review thread.isResolved", resolved)
        comments = array(at(node, "comments", "nodes"), "comments.nodes")
        comment = parse_comment(comments[0]) if comments else None
        bugbot = is_bugbot(comment)
        if bugbot and comment is not None:
            match = re.search(r"RUN_ID:\s*([a-zA-Z0-9_.:-]+)", comment["body"]) or re.search(
                r"CURSOR_AUTOMATION_ID:\s*([a-zA-Z0-9_.:-]+)", comment["body"]
            )
            if match:
                keys.add(match[1])
            else:
                keyless = True
        if not resolved:
            unresolved.append((string(at(node, "id"), "review thread.id"), comment, bugbot))
    passes = len(keys) or int(keyless)
    return [
        {"id": id, "firstComment": comment, "isBugbot": bugbot, "bugbotReviewPasses": passes}
        for id, comment, bugbot in unresolved
    ]


def codex_review_kind(sha: str | None, status: str | None, head: str) -> CheckKind | None:
    if sha == head:
        if status == "completed":
            return None
        return "pending" if status is None or status in CODEX_ACTIVE else "failed"
    # A review queued before it records its commit is about to cover the head.
    return "pending" if sha is None and status in CODEX_ACTIVE else None


def parse_codex_state(body: str) -> list[tuple[str, str | None, str | None]]:
    """Return (check name, commit sha, status) for each review in the comment's Codex marker."""
    start = body.find(CODEX_MARKER)
    if start < 0:
        return []
    payload, closed, _ = body[start + len(CODEX_MARKER) :].partition("-->")
    try:
        if not closed:
            missing("codex-review-state", body[start:][:240])
        state = record(parse_json(payload, "codex-review-state"), "codex-review-state")
        reviews: list[tuple[str, str | None, str | None]] = []
        for key, name in CODEX_REVIEWS:
            if (value := state.get(key)) is not None:
                review = record(value, "codex-review-state." + key)
                sha = nullable_string(review.get("commit_sha"), f"codex-review-state.{key}.commit_sha")
                reviews.append((name, sha, nullable_string(review.get("status"), f"codex-review-state.{key}.status")))
        return reviews
    except QueryError as error:
        # The marker does not change between retries, so report it at once.
        raise QueryError("codex-review-state", error.failure["detail"], False) from error


def parse_comment_reviews(nodes: list[object], head: str) -> list[Check]:
    reviews: list[Check] = []
    for raw in nodes:
        node = record(raw, "PR comment")
        author = at(node, "author")
        if author is None or nullable_string(at(author, "login"), "author.login") not in CODEX_AUTHORS:
            continue
        for name, sha, status in parse_codex_state(string(at(node, "body"), "comment.body")):
            if (kind := codex_review_kind(sha, status, head)) is not None:
                link = string(at(node, "url"), "comment.url")
                details: CheckDetails = {"name": name, "description": "", "link": link, "workflow": ""}
                reviews.append(check(details, kind, (status or "unknown").upper()))
    return reviews


def graphql_args(query: str, context: Context, after: str | None = None) -> list[str]:
    args = [
        "gh",
        "api",
        "graphql",
        "-f",
        "query=" + query,
        "-f",
        "owner=" + context["owner"],
        "-f",
        "repo=" + context["repo"],
        "-F",
        "pr=" + str(context["number"]),
    ]
    if after is not None:
        args += ["-f", "after=" + after]
    return args


def next_cursor(connection: dict[str, object], seen: set[str]) -> str | None:
    page = record(at(connection, "pageInfo"), "pageInfo")
    has_next = page.get("hasNextPage")
    if not isinstance(has_next, bool):
        missing("pageInfo.hasNextPage", has_next)
    cursor = nullable_string(at(page, "endCursor"), "pageInfo.endCursor")
    if not has_next:
        return None
    if not cursor or cursor in seen:
        missing("pageInfo.endCursor", cursor)
    seen.add(cursor)
    return cursor


class Reader(Protocol):
    """Forge-neutral read-only PR source; `forge` is the display name used in human output."""

    forge: str

    def origin_repo(self) -> Repo | None: ...
    def current_pr(self, pr: int | None) -> Context: ...
    def pull_request(self, context: Context) -> PullRequestFacts: ...
    def open_pull_requests(self, context: Context) -> list[OpenPullRequest]: ...
    def checks(self, context: Context) -> ResolvedChecks: ...
    def review_threads(self, context: Context) -> list[Thread]: ...
    def comment_reviews(self, context: Context, head: str | None) -> list[Check]: ...
    def commit_rollups(self, context: Context) -> list[CommitRollup]: ...
    def web_url(self, context: Context) -> str: ...


class CheckPages(Protocol):
    def checks_fast_path(self, context: Context) -> FastChecks | UnusableChecks: ...
    def check_rollup_page(self, context: Context, after: str | None) -> RollupPage: ...


class GitHubReader:
    forge = "GitHub"

    def __init__(self, query_json: Callable[[list[str]], object] = run_json) -> None:
        self.query_json = query_json

    def origin_repo(self) -> Repo | None:
        result = run(["git", "remote", "get-url", "origin"])
        return parse_remote(result.stdout) if result.returncode == 0 else None

    def current_pr(self, pr: int | None) -> Context:
        args = ["gh", "pr", "view"] + ([str(pr)] if pr is not None else []) + ["--json", "number,url"]
        value = record(self.query_json(args), "current PR")
        result = parse_pr_url(string(at(value, "url"), "current PR.url"))
        try:
            result["number"] = pr_number(pr if pr is not None else at(value, "number"))
        except ValueError:
            missing("current PR.number", value.get("number"))
        return result

    def pull_request(self, context: Context) -> PullRequestFacts:
        value = self.query_json(
            [
                "gh",
                "pr",
                "view",
                str(context["number"]),
                "--repo",
                f"{context['owner']}/{context['repo']}",
                "--json",
                "mergeable,mergeStateStatus,reviewDecision,headRefOid,headRefName,baseRefName,state,mergedAt,isDraft",
            ]
        )
        return parse_pull_request(value, context)

    def open_pull_requests(self, context: Context) -> list[OpenPullRequest]:
        values = self.query_json(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                f"{context['owner']}/{context['repo']}",
                "--state",
                "open",
                "--limit",
                "300",
                "--json",
                "number,headRefName,baseRefName",
            ]
        )
        rows: list[OpenPullRequest] = []
        for raw in array(values, "open PRs"):
            value = record(raw, "open PR")
            try:
                number = pr_number(at(value, "number"))
            except ValueError:
                missing("open PR.number", value.get("number"))
            rows.append(
                {
                    "number": number,
                    "headRefName": string(at(value, "headRefName"), "headRefName"),
                    "baseRefName": string(at(value, "baseRefName"), "baseRefName"),
                }
            )
        return rows

    def web_url(self, context: Context) -> str:
        return f"https://github.com/{context['owner']}/{context['repo']}/pull/{context['number']}"

    def checks(self, context: Context) -> ResolvedChecks:
        return resolve_checks(self, context)

    def checks_fast_path(self, context: Context) -> FastChecks | UnusableChecks:
        result = run(
            [
                "gh",
                "pr",
                "checks",
                str(context["number"]),
                "--repo",
                f"{context['owner']}/{context['repo']}",
                "--json",
                "name,state,description,link,workflow,bucket",
            ]
        )
        if result.returncode in (0, 1, 8) and result.stdout.strip():
            try:
                value = parse_json(result.stdout, "gh pr checks")
                if isinstance(value, list):
                    return {"kind": "checks", "checks": [parse_fast_check(item) for item in value]}
            except QueryError:
                pass
        return {"kind": "unusable", "exitCode": result.returncode, "stderr": result.stderr}

    def check_rollup_page(self, context: Context, after: str | None) -> RollupPage:
        value = self.query_json(graphql_args(PR_CHECK_ROLLUP_QUERY, context, after))
        commits = array(at(value, "data", "repository", "pullRequest", "commits", "nodes"), "commits.nodes")
        if not commits:
            return {"checks": [], "endCursor": None}
        rollup = at(commits[-1], "commit", "statusCheckRollup")
        if rollup is None:
            return {"checks": [], "endCursor": None}
        connection = record(at(rollup, "contexts"), "contexts")
        checks = [
            mapped
            for node in array(at(connection, "nodes"), "contexts.nodes")
            if (mapped := map_rollup_node(node)) is not None
        ]
        return {"checks": checks, "endCursor": next_cursor(connection, {after} if after else set())}

    def review_threads(self, context: Context) -> list[Thread]:
        nodes: list[object] = []
        after: str | None = None
        seen: set[str] = set()
        while True:
            connection = record(
                at(
                    self.query_json(graphql_args(REVIEW_THREADS_QUERY, context, after)),
                    "data",
                    "repository",
                    "pullRequest",
                    "reviewThreads",
                ),
                "reviewThreads",
            )
            nodes.extend(array(at(connection, "nodes"), "reviewThreads.nodes"))
            after = next_cursor(connection, seen)
            if after is None:
                break
        return parse_review_threads({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": nodes}}}}})

    def comment_reviews(self, context: Context, head: str | None) -> list[Check]:
        """Checks for review bots that report progress on the head commit in a PR comment."""
        if head is None:
            return []
        nodes: list[object] = []
        after: str | None = None
        seen: set[str] = set()
        while True:
            value = self.query_json(graphql_args(PR_COMMENTS_QUERY, context, after))
            connection = record(at(value, "data", "repository", "pullRequest", "comments"), "comments")
            nodes.extend(array(at(connection, "nodes"), "comments.nodes"))
            after = next_cursor(connection, seen)
            if after is None:
                return parse_comment_reviews(nodes, head)

    def commit_rollups(self, context: Context) -> list[CommitRollup]:
        value = self.query_json(graphql_args(PR_COMMIT_STATUS_QUERY, context))
        commits = array(at(value, "data", "repository", "pullRequest", "commits", "nodes"), "commits.nodes")
        result: list[CommitRollup] = []
        for node in commits:
            commit = at(node, "commit")
            rollup = at(commit, "statusCheckRollup")
            result.append(
                {
                    "oid": string(at(commit, "oid"), "commit.oid"),
                    "state": None
                    if rollup is None
                    else optional_enum(at(rollup, "state"), ROLLUP_STATES, "statusCheckRollup.state"),
                }
            )
        return result


def resolve_checks(reader: CheckPages, context: Context) -> ResolvedChecks:
    fast = reader.checks_fast_path(context)
    if fast["kind"] == "checks" and fast["checks"]:
        return {"source": "gh-pr-checks", "checks": fast["checks"]}
    checks: list[Check] = []
    after: str | None = None
    seen: set[str] = set()
    while True:
        page = reader.check_rollup_page(context, after)
        checks.extend(page["checks"])
        after = page["endCursor"]
        if after is None:
            break
        if after in seen:
            missing("contexts.pageInfo.endCursor", after)
        seen.add(after)
    if checks:
        return {"source": "graphql-rollup", "checks": checks}
    if fast["kind"] == "unusable" and fast["exitCode"] == 1 and fast["stderr"].strip().startswith("no checks reported"):
        return {"source": "graphql-rollup", "checks": []}
    suffix = "fast path and GraphQL rollup were empty"
    if fast["kind"] == "unusable":
        suffix = f"fast path exit={fast['exitCode']}; GraphQL rollup was empty" + (
            f"; {first_line(fast['stderr'])}" if first_line(fast["stderr"]) else ""
        )
    raise QueryError("checks-unavailable", "could not read PR checks: " + suffix)


def resolve_context(reader: Reader, owner: str | None, repo: str | None, pr: int | None) -> Context:
    if pr is not None and owner is not None and repo is not None:
        return {"owner": owner, "repo": repo, "number": pr}
    if pr is not None:
        origin = reader.origin_repo()
        if origin is not None:
            return {
                "owner": owner if owner is not None else origin["owner"],
                "repo": repo if repo is not None else origin["repo"],
                "number": pr,
            }
    inferred = reader.current_pr(pr)
    return {
        "owner": owner if owner is not None else inferred["owner"],
        "repo": repo if repo is not None else inferred["repo"],
        "number": pr if pr is not None else inferred["number"],
    }


def order_stack(context: Context, rows: list[OpenPullRequest]) -> list[Context]:
    by_number, by_head = {r["number"]: r for r in rows}, {r["headRefName"]: r for r in rows}
    start = by_number.get(context["number"])
    if start is None:
        return [context]
    down: list[OpenPullRequest] = []
    current, seen = start, {start["number"]}
    while current["baseRefName"] in by_head:
        current = by_head[current["baseRefName"]]
        if current["number"] in seen:
            raise QueryError("missing-key", "cycle in PR stack")
        seen.add(current["number"])
        down.append(current)
    up: list[OpenPullRequest] = []

    def visit(parent: OpenPullRequest) -> None:
        for child in sorted(rows, key=lambda r: r["number"]):
            if child["baseRefName"] == parent["headRefName"] and child["number"] not in seen:
                seen.add(child["number"])
                up.append(child)
                visit(child)

    visit(start)
    return [{**context, "number": r["number"]} for r in [*list(reversed(down)), start, *up]]
