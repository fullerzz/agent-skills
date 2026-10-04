"""Read-only gh adapter with fail-closed response parsing."""

from __future__ import annotations

import json
import re
import subprocess
from typing import TYPE_CHECKING, Any, NoReturn, Protocol
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

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
MERGE_STATES = ("BEHIND", "BLOCKED", "CLEAN", "CONFLICTING", "DIRTY", "DRAFT", "HAS_HOOKS", "UNKNOWN", "UNSTABLE")
ROLLUP_STATES = ("ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS")
REVIEW_DECISIONS = ("APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED")
MISSING = object()


class QueryError(Exception):
    def __init__(self, kind: str, detail: str, retryable: bool = True, **extra: object) -> None:
        super().__init__(detail)
        self.failure = dict(kind=kind, retryable=retryable, detail=detail, **extra)


def first_line(value: str) -> str:
    return value.strip().split("\n")[0][:240]


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 - Fixed Git/gh/gt argument vectors from local callers; no shell.
            argv, stdin=subprocess.DEVNULL, capture_output=True, text=True
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


def record(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        missing(path, value)
    return value


def array(value: object, path: str) -> list[Any]:
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


def enum(value: object, values: Sequence[str], path: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or value not in values:
        missing(path, value)
    return value


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


def parse_remote(value: str) -> dict[str, Any] | None:
    value = value.strip()
    for prefix in ("git@github.com:", "ssh://git@github.com/"):
        if value.startswith(prefix):
            value = "https://github.com/" + value[len(prefix) :]
    try:
        parts = canonical_parts(value.removesuffix(".git"))
        return {"owner": parts[0], "repo": parts[1]} if len(parts) == 2 else None
    except ValueError:
        return None


def parse_pr_url(value: str) -> dict[str, Any]:
    try:
        parts = canonical_parts(value)
        if len(parts) != 4 or parts[2] != "pull":
            raise ValueError("not a canonical GitHub pull URL")
        return {"owner": parts[0], "repo": parts[1], "number": pr_number(int(parts[3]))}
    except ValueError as error:
        raise QueryError(
            "invalid-context-url", f"could not infer owner/repo from PR URL: {value} ({error})", False, rawValue=value
        ) from error


def details(value: dict[str, Any], name_key: str) -> dict[str, Any]:
    return {
        "name": string(value.get(name_key), name_key),
        "description": value.get("description") if isinstance(value.get("description"), str) else "",
        "link": next((value[k] for k in ("link", "detailsUrl") if isinstance(value.get(k), str)), ""),
        "workflow": value.get("workflow") if isinstance(value.get("workflow"), str) else "",
    }


def pending_or_gate(value: dict[str, Any], state: str) -> dict[str, Any]:
    return value | {
        "kind": "code-review-gate" if value["name"] == "Code Review Gate" else "pending",
        "reportedState": state,
    }


def parse_fast_check(value: object) -> dict[str, Any]:
    value = record(value, "check")
    base = details(value, "name")
    state = string(value.get("state"), "check.state").upper()
    bucket = string(value.get("bucket"), "check.bucket")
    if bucket == "fail" or state in ("FAILURE", "ERROR", "ACTION_REQUIRED"):
        kind = "failed"
    elif bucket == "pending":
        return pending_or_gate(base, state)
    else:
        kind = {"pass": "passed", "skipping": "skipped"}.get(bucket, "failed")
    return base | {"kind": kind, "reportedState": state}


def map_rollup_node(value: object) -> dict[str, Any] | None:
    value = record(value, "rollup node")
    typename = value.get("__typename")
    if typename not in ("CheckRun", "StatusContext"):
        return None
    base = details(value, "name" if typename == "CheckRun" else "context")
    if isinstance(value.get("targetUrl"), str):
        base["link"] = value["targetUrl"]
    if typename == "CheckRun":
        status, conclusion = str(value.get("status") or "").upper(), str(value.get("conclusion") or "").upper()
        if status != "COMPLETED":
            return pending_or_gate(base, "PENDING")
        kind = {"SUCCESS": "passed", "NEUTRAL": "skipped", "SKIPPED": "skipped"}.get(conclusion, "failed")
        state = conclusion if conclusion in ("SUCCESS", "NEUTRAL", "SKIPPED", "ACTION_REQUIRED") else "FAILURE"
    else:
        state = str(value.get("state") or "").upper()
        if state in ("PENDING", "EXPECTED"):
            return pending_or_gate(base, "PENDING")
        kind = "passed" if state == "SUCCESS" else "failed"
        state = state or "FAILURE"
    return base | {"kind": kind, "reportedState": state}


def parse_pull_request(value: object, context: dict[str, Any]) -> dict[str, Any]:
    value = record(value, "pull request")
    if type(value.get("isDraft")) is not bool:
        missing("pull request.isDraft", value.get("isDraft"))
    result = {"context": context, "isDraft": value["isDraft"]}
    for key, choices in [
        ("mergeable", ("MERGEABLE", "CONFLICTING", "UNKNOWN")),
        ("mergeStateStatus", MERGE_STATES),
        ("state", ("OPEN", "CLOSED", "MERGED")),
    ]:
        result[key] = enum(at(value, key), choices, "pull request." + key)
    decision = at(value, "reviewDecision")
    result["reviewDecision"] = enum(
        None if decision == "" else decision, REVIEW_DECISIONS, "pull request.reviewDecision", True
    )
    for key in ("headRefOid", "mergedAt"):
        result[key] = nullable_string(at(value, key), "pull request." + key)
    for key in ("headRefName", "baseRefName"):
        result[key] = string(at(value, key), "pull request." + key)
    return result


def parse_comment(value: object) -> dict[str, Any]:
    value = record(value, "review comment")
    author = at(value, "author")
    line = at(value, "line")
    if line is not None and type(line) is not int:
        missing("review comment.line", line)
    return {
        "authorLogin": None if author is None else nullable_string(at(author, "login"), "author.login"),
        "body": string(at(value, "body"), "comment.body"),
        "path": nullable_string(at(value, "path"), "comment.path"),
        "line": line,
        "createdAt": string(at(value, "createdAt"), "comment.createdAt"),
    }


def is_bugbot(comment: dict[str, Any] | None) -> bool:
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


def parse_review_threads(value: object) -> list[dict[str, Any]]:
    nodes = array(at(value, "data", "repository", "pullRequest", "reviewThreads", "nodes"), "reviewThreads.nodes")
    threads, keys, keyless = [], set(), False
    for node in nodes:
        record(node, "review thread")
        if type(node.get("isResolved")) is not bool:
            missing("review thread.isResolved", node.get("isResolved"))
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
        if not node["isResolved"]:
            threads.append(
                {"id": string(at(node, "id"), "review thread.id"), "firstComment": comment, "isBugbot": bugbot}
            )
    passes = len(keys) or int(keyless)
    return [row | {"bugbotReviewPasses": passes} for row in threads]


def graphql_args(query: str, context: dict[str, Any], after: str | None = None) -> list[str]:
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


def next_cursor(connection: dict[str, Any], seen: set[str]) -> str | None:
    page = record(at(connection, "pageInfo"), "pageInfo")
    if type(page.get("hasNextPage")) is not bool:
        missing("pageInfo.hasNextPage", page.get("hasNextPage"))
    cursor = nullable_string(at(page, "endCursor"), "pageInfo.endCursor")
    if not page["hasNextPage"]:
        return None
    if not cursor or cursor in seen:
        missing("pageInfo.endCursor", cursor)
    seen.add(cursor)
    return cursor


class Reader(Protocol):
    def origin_repo(self) -> dict[str, Any] | None: ...
    def current_pr(self, pr: int | None) -> dict[str, Any]: ...
    def pull_request(self, context: dict[str, Any]) -> dict[str, Any]: ...
    def open_pull_requests(self, context: dict[str, Any]) -> list[dict[str, Any]]: ...
    def checks_fast_path(self, context: dict[str, Any]) -> dict[str, Any]: ...
    def check_rollup_page(self, context: dict[str, Any], after: str | None) -> dict[str, Any]: ...
    def review_threads(self, context: dict[str, Any]) -> list[dict[str, Any]]: ...
    def commit_rollups(self, context: dict[str, Any]) -> list[dict[str, Any]]: ...


class GitHubReader:
    def __init__(self, query_json: Callable[[list[str]], object] = run_json) -> None:
        self.query_json = query_json

    def origin_repo(self) -> dict[str, Any] | None:
        result = run(["git", "remote", "get-url", "origin"])
        return parse_remote(result.stdout) if result.returncode == 0 else None

    def current_pr(self, pr: int | None) -> dict[str, Any]:
        args = ["gh", "pr", "view"] + ([str(pr)] if pr is not None else []) + ["--json", "number,url"]
        value = record(self.query_json(args), "current PR")
        result = parse_pr_url(string(at(value, "url"), "current PR.url"))
        try:
            result["number"] = pr_number(pr if pr is not None else at(value, "number"))
        except ValueError:
            missing("current PR.number", value.get("number"))
        return result

    def pull_request(self, context: dict[str, Any]) -> dict[str, Any]:
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

    def open_pull_requests(self, context: dict[str, Any]) -> list[dict[str, Any]]:
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
        rows = []
        for value in array(values, "open PRs"):
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

    def checks_fast_path(self, context: dict[str, Any]) -> dict[str, Any]:
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

    def check_rollup_page(self, context: dict[str, Any], after: str | None) -> dict[str, Any]:
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

    def review_threads(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        nodes, after, seen = [], None, set()
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

    def commit_rollups(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        value = self.query_json(graphql_args(PR_COMMIT_STATUS_QUERY, context))
        commits = array(at(value, "data", "repository", "pullRequest", "commits", "nodes"), "commits.nodes")
        result = []
        for node in commits:
            commit = at(node, "commit")
            rollup = at(commit, "statusCheckRollup")
            result.append(
                {
                    "oid": string(at(commit, "oid"), "commit.oid"),
                    "state": None
                    if rollup is None
                    else enum(at(rollup, "state"), ROLLUP_STATES, "statusCheckRollup.state", True),
                }
            )
        return result


def resolve_checks(reader: Reader, context: dict[str, Any]) -> dict[str, Any]:
    fast = reader.checks_fast_path(context)
    if fast["kind"] == "checks" and fast["checks"]:
        return {"source": "gh-pr-checks", "checks": fast["checks"]}
    checks, after, seen = [], None, set()
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
    suffix = "fast path and GraphQL rollup were empty"
    if fast["kind"] == "unusable":
        suffix = f"fast path exit={fast['exitCode']}; GraphQL rollup was empty" + (
            f"; {first_line(fast['stderr'])}" if first_line(fast["stderr"]) else ""
        )
    raise QueryError("checks-unavailable", "could not read PR checks: " + suffix)


def resolve_context(reader: Reader, owner: str | None, repo: str | None, pr: int | None) -> dict[str, Any]:
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


def order_stack(context: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_number, by_head = {r["number"]: r for r in rows}, {r["headRefName"]: r for r in rows}
    start = by_number.get(context["number"])
    if start is None:
        return [context]
    down, current, seen = [], start, {start["number"]}
    while current["baseRefName"] in by_head:
        current = by_head[current["baseRefName"]]
        if current["number"] in seen:
            raise QueryError("missing-key", "cycle in PR stack")
        seen.add(current["number"])
        down.append(current)
    up = []

    def visit(parent: dict[str, Any]) -> None:
        for child in sorted(rows, key=lambda r: r["number"]):
            if child["baseRefName"] == parent["headRefName"] and child["number"] not in seen:
                seen.add(child["number"])
                up.append(child)
                visit(child)

    visit(start)
    return [context | {"number": r["number"]} for r in [*list(reversed(down)), start, *up]]
