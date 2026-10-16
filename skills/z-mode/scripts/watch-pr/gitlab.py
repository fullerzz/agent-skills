"""Read-only glab adapter mapping GitLab merge requests onto the watcher's normalized facts."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

from github import (
    QueryError,
    array,
    at,
    first_line,
    missing,
    nullable_string,
    optional_text,
    parse_json,
    parse_review_threads,
    pr_number,
    record,
    run,
    run_json,
    string,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from github import CommitRollup, OpenPullRequest, ResolvedChecks
    from schema import (
        Check,
        CheckKind,
        Context,
        Mergeable,
        MergeState,
        PrState,
        PullRequestFacts,
        Repo,
        ReviewDecision,
        RollupState,
        Thread,
    )

PENDING = ("created", "pending", "running", "preparing", "waiting_for_resource", "scheduled", "waiting_for_callback")
STATES: dict[str, PrState] = {"opened": "OPEN", "locked": "OPEN", "closed": "CLOSED", "merged": "MERGED"}
MERGE_STATUS: dict[str, tuple[MergeState, Mergeable]] = {
    "mergeable": ("CLEAN", "MERGEABLE"),
    "conflict": ("DIRTY", "CONFLICTING"),
    "broken_status": ("DIRTY", "CONFLICTING"),
    "need_rebase": ("BEHIND", "MERGEABLE"),
    "draft_status": ("DRAFT", "MERGEABLE"),
    **dict.fromkeys(("checking", "unchecked", "preparing", "approvals_syncing", "not_open"), ("UNKNOWN", "UNKNOWN")),
    **dict.fromkeys(
        (
            "ci_must_pass",
            "ci_still_running",
            "not_approved",
            "discussions_not_resolved",
            "blocked_status",
            "requested_changes",
            "external_status_checks",
            "status_checks_must_pass",
            "jira_association_missing",
            "merge_request_blocked",
            "merge_time",
            "security_policy_violations",
            "security_policy_pipeline_check",
            "locked_paths",
            "locked_lfs_files",
            "title_regex",
            "commits_status",
        ),
        ("BLOCKED", "MERGEABLE"),
    ),
}
# Policy allows BLOCKED with a green rollup, so non-review gates surface as a synthetic check.
# shortcut: a failed external status check reads as pending until it times out;
# upgrade via the MR status_checks endpoint.
MERGE_CHECKS: dict[str, CheckKind] = {
    **dict.fromkeys(
        (
            "merge_time",
            "merge_request_blocked",
            "jira_association_missing",
            "title_regex",
            "locked_paths",
            "locked_lfs_files",
            "security_policy_violations",
            "commits_status",
            "blocked_status",
            # Fast-forward and semi-linear merge methods refuse until the source branch is rebased.
            "need_rebase",
        ),
        "failed",
    ),
    **dict.fromkeys(("status_checks_must_pass", "external_status_checks", "security_policy_pipeline_check"), "pending"),
    # GitLab is still computing mergeability, approvals, or CI, so wait rather than read them as clear.
    **dict.fromkeys(("checking", "unchecked", "preparing", "approvals_syncing", "ci_still_running"), "pending"),
}
# shortcut: detailed_merge_status reports one blocking reason, so another reason can mask a review state;
# upgrade via the approvals endpoints if that matters.
REVIEWS: dict[str, ReviewDecision] = {"requested_changes": "CHANGES_REQUESTED", "not_approved": "REVIEW_REQUIRED"}
# None marks a failure whose kind depends on allow_failure; a blocking manual job waits on a human.
JOB_KINDS: dict[str, CheckKind | None] = {
    "success": "passed",
    "skipped": "skipped",
    "failed": None,
    "manual": None,
    "canceled": "failed",
    "canceling": "failed",
    **dict.fromkeys(PENDING, "pending"),
}
ROLLUPS: dict[str, RollupState | None] = {
    "success": "SUCCESS",
    "failed": "FAILURE",
    "canceled": "FAILURE",
    "canceling": "FAILURE",
    "skipped": None,
    **dict.fromkeys((*PENDING, "manual"), "PENDING"),
}


def lookup[T](table: dict[str, T], value: object, path: str) -> T:
    if not isinstance(value, str) or value not in table:
        missing(path, value)
    return table[value]


def positive(value: object, path: str) -> int:
    try:
        return pr_number(value)
    except ValueError:
        missing(path, value)


def boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        missing(path, value)
    return value


def run_ndjson(argv: list[str]) -> list[object]:
    result = run(argv)
    if result.returncode:
        raise QueryError(
            "command-exit",
            first_line(result.stderr) or f"{' '.join(argv)} exited {result.returncode}",
            code=result.returncode,
        )
    return [parse_json(line, " ".join(argv)) for line in result.stdout.splitlines() if line.strip()]


def parse_gitlab_remote(value: str) -> tuple[str, Repo] | None:
    value = value.strip()
    if "://" not in value and ":" in value:
        value = "ssh://" + value.replace(":", "/", 1)
    try:
        url = urlsplit(value.removesuffix(".git"))
        # The SSH port is not the API port; an HTTPS port is.
        host = url.hostname if url.scheme == "ssh" else url.netloc.rpartition("@")[2].lower()
        _ = url.port
    except ValueError:
        return None
    parts = [part for part in url.path.split("/") if part]
    if url.scheme not in ("ssh", "https") or not host or url.password or url.query or url.fragment:
        return None
    if len(parts) < 2 or "-" in parts:
        return None
    return host, {"owner": "/".join(parts[:-1]), "repo": parts[-1]}


def parse_mr_url(value: str, host: str) -> Context:
    try:
        url = urlsplit(value)
        parts = [part for part in url.path.split("/") if part]
        if (
            url.scheme != "https"
            or url.netloc != host
            or url.query
            or url.fragment
            or len(parts) < 5
            or parts[-3:-1] != ["-", "merge_requests"]
        ):
            raise ValueError("not a canonical GitLab merge request URL")
        return {"owner": "/".join(parts[:-4]), "repo": parts[-4], "number": pr_number(int(parts[-1]))}
    except ValueError as error:
        raise QueryError(
            "invalid-context-url", f"could not infer owner/repo from MR URL: {value} ({error})", False, rawValue=value
        ) from error


def parse_job(value: object) -> Check:
    value = record(value, "job")
    status = at(value, "status")
    kind = lookup(JOB_KINDS, status, "job.status")
    if kind is None:
        kind = "skipped" if boolean(at(value, "allow_failure"), "job.allow_failure") else "failed"
    return {
        "name": string(at(value, "name"), "job.name"),
        "description": optional_text(value, "failure_reason"),
        "link": optional_text(value, "web_url"),
        "workflow": optional_text(value, "stage"),
        "kind": kind,
        "reportedState": string(status, "job.status").upper(),
    }


def thread_node(value: object) -> dict[str, object] | None:
    discussion = record(value, "discussion")
    notes = [record(note, "discussion note") for note in array(at(discussion, "notes"), "discussion.notes")]
    resolvable = [note for note in notes if boolean(at(note, "resolvable"), "note.resolvable")]
    if not resolvable:
        return None
    first = notes[0]
    author, position = at(first, "author"), first.get("position")
    position = {} if position is None else record(position, "note.position")
    return {
        "id": string(at(discussion, "id"), "discussion.id"),
        "isResolved": all(boolean(at(note, "resolved"), "note.resolved") for note in resolvable),
        "comments": {
            "nodes": [
                {
                    "body": at(first, "body"),
                    "createdAt": at(first, "created_at"),
                    "path": position.get("new_path") or position.get("old_path") or None,
                    "line": position.get("new_line") or position.get("old_line") or None,
                    "author": None if author is None else {"login": at(author, "username")},
                }
            ]
        },
    }


class GitLabReader:
    forge = "GitLab"

    def __init__(
        self,
        host: str,
        query_json: Callable[[list[str]], object] = run_json,
        query_ndjson: Callable[[list[str]], list[object]] = run_ndjson,
    ) -> None:
        self.host, self.query_json, self.query_ndjson = host, query_json, query_ndjson

    def api(self, path: str) -> dict[str, object]:
        return record(self.query_json(["glab", "api", "--hostname", self.host, path]), path)

    def api_list(self, path: str) -> list[object]:
        return self.query_ndjson(["glab", "api", "--hostname", self.host, path, "--paginate", "--output", "ndjson"])

    def project(self, context: Context) -> str:
        return "projects/" + quote(f"{context['owner']}/{context['repo']}", safe="")

    def merge_request_path(self, context: Context) -> str:
        return f"{self.project(context)}/merge_requests/{context['number']}"

    def origin_repo(self) -> Repo | None:
        result = run(["git", "remote", "get-url", "origin"])
        parsed = parse_gitlab_remote(result.stdout) if result.returncode == 0 else None
        return parsed[1] if parsed is not None and parsed[0] == self.host else None

    def current_pr(self, pr: int | None) -> Context:
        # glab mr view has no --hostname; it resolves the cwd remote, and the URL host check pins it.
        value = record(
            self.query_json(["glab", "mr", "view"] + ([str(pr)] if pr is not None else []) + ["-F", "json"]),
            "current MR",
        )
        result = parse_mr_url(string(at(value, "web_url"), "current MR.web_url"), self.host)
        result["number"] = positive(pr if pr is not None else at(value, "iid"), "current MR.iid")
        return result

    def pull_request(self, context: Context) -> PullRequestFacts:
        value = self.api(self.merge_request_path(context))
        status = string(at(value, "detailed_merge_status"), "merge request.detailed_merge_status")
        merge_state, mergeable = lookup(MERGE_STATUS, status, "merge request.detailed_merge_status")
        if boolean(at(value, "has_conflicts"), "merge request.has_conflicts"):
            mergeable = "CONFLICTING"
        return {
            "context": context,
            "isDraft": boolean(at(value, "draft"), "merge request.draft"),
            "mergeable": mergeable,
            "mergeStateStatus": merge_state,
            # locked is GitLab's transient merging state; poll again.
            "state": lookup(STATES, at(value, "state"), "merge request.state"),
            "reviewDecision": REVIEWS.get(status),
            "headRefOid": nullable_string(at(value, "sha"), "merge request.sha"),
            "mergedAt": nullable_string(at(value, "merged_at"), "merge request.merged_at"),
            "headRefName": string(at(value, "source_branch"), "merge request.source_branch"),
            "baseRefName": string(at(value, "target_branch"), "merge request.target_branch"),
        }

    def open_pull_requests(self, context: Context) -> list[OpenPullRequest]:
        rows: list[OpenPullRequest] = []
        for raw in self.api_list(self.project(context) + "/merge_requests?state=opened&per_page=100"):
            value = record(raw, "open MR")
            rows.append(
                {
                    "number": positive(at(value, "iid"), "open MR.iid"),
                    "headRefName": string(at(value, "source_branch"), "open MR.source_branch"),
                    "baseRefName": string(at(value, "target_branch"), "open MR.target_branch"),
                }
            )
        return rows

    def current(self, context: Context, value: dict[str, object], pipeline: object) -> bool:
        # A push or [ci skip] leaves head_pipeline on the previous commit's run.
        sha = nullable_string(at(value, "sha"), "merge request.sha")
        pipeline_sha = string(at(pipeline, "sha"), "head_pipeline.sha")
        if sha is None or pipeline_sha == sha:
            return sha is not None
        refs = [f"refs/merge-requests/{context['number']}/{kind}" for kind in ("merge", "train")]
        if string(at(pipeline, "ref"), "head_pipeline.ref") not in refs:
            return False
        # Merged-results and merge-train pipelines test a merge commit built on the MR head.
        project = positive(at(pipeline, "project_id"), "head_pipeline.project_id")
        commit = self.api(f"projects/{project}/repository/commits/{pipeline_sha}")
        return sha in array(at(commit, "parent_ids"), "commit.parent_ids")

    def pipeline_checks(self, pipeline: object) -> list[Check]:
        # Fork MR pipelines run in the source project, so use the pipeline's own project.
        path = (
            f"projects/{positive(at(pipeline, 'project_id'), 'head_pipeline.project_id')}"
            f"/pipelines/{positive(at(pipeline, 'id'), 'head_pipeline.id')}"
        )
        jobs = [*self.api_list(path + "/jobs?per_page=100"), *self.api_list(path + "/bridges?per_page=100")]
        status = at(pipeline, "status")
        if not jobs and lookup(ROLLUPS, status, "head_pipeline.status") == "FAILURE":
            # A CI config error fails the pipeline before it creates any job.
            state = string(status, "head_pipeline.status")
            link = optional_text(record(pipeline, "head_pipeline"), "web_url")
            return [
                {
                    "name": "GitLab pipeline",
                    "description": state,
                    "link": link,
                    "workflow": "",
                    "kind": "failed",
                    "reportedState": state.upper(),
                }
            ]
        return [parse_job(job) for job in jobs]

    def checks(self, context: Context) -> ResolvedChecks:
        value = self.api(self.merge_request_path(context))
        pipeline = at(value, "head_pipeline")
        checks: list[Check] = []
        reason = "no head pipeline"
        current = pipeline is not None and self.current(context, value, pipeline)
        if pipeline is not None and not current:
            reason = "head pipeline is not for the current head"
        elif current:
            checks, reason = self.pipeline_checks(pipeline), "head pipeline has no jobs"
        status = string(at(value, "detailed_merge_status"), "merge request.detailed_merge_status")
        kind = MERGE_CHECKS.get(status)
        # GitLab can reject CI that the jobs don't explain, such as a skipped pipeline when skips don't count.
        # A missing or stale pipeline stays unavailable CI to retry, and a running one is still pending.
        if status == "ci_must_pass" and current and not any(c["kind"] in ("failed", "pending") for c in checks):
            running = lookup(ROLLUPS, at(pipeline, "status"), "head_pipeline.status") == "PENDING"
            kind = "pending" if running else "failed"
        if kind is not None:
            checks.append(
                {
                    "name": "GitLab merge check",
                    "description": status,
                    "link": optional_text(value, "web_url"),
                    "workflow": "",
                    "kind": kind,
                    "reportedState": status.upper(),
                }
            )
        if not checks:
            raise QueryError("checks-unavailable", "could not read MR checks: " + reason)
        return {"source": "gitlab-pipeline", "checks": checks}

    def commit_rollups(self, context: Context) -> list[CommitRollup]:
        path = self.merge_request_path(context)
        value = self.api(path)
        head = at(value, "head_pipeline")
        head_id = None if head is None else positive(at(head, "id"), "head_pipeline.id")
        sha = nullable_string(at(value, "sha"), "merge request.sha")
        current = head is not None and self.current(context, value, head)
        heads: list[CommitRollup] = []
        rest: list[CommitRollup] = []
        for raw in self.api_list(path + "/pipelines?per_page=100"):
            pipeline = record(raw, "pipeline")
            is_head = positive(at(pipeline, "id"), "pipeline.id") == head_id
            # A current merged-results or merge-train pipeline runs on a merge-ref sha, not the MR head sha.
            oid = sha if is_head and current and sha is not None else string(at(pipeline, "sha"), "pipeline.sha")
            state = lookup(ROLLUPS, at(pipeline, "status"), "pipeline.status")
            (heads if is_head else rest).append({"oid": oid, "state": state})
        # Policy reads the first rollup matching the head oid, so the head pipeline goes first.
        return heads + rest

    def review_threads(self, context: Context) -> list[Thread]:
        raw = self.api_list(self.merge_request_path(context) + "/discussions?per_page=100")
        nodes = [node for value in raw if (node := thread_node(value)) is not None]
        return parse_review_threads({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": nodes}}}}})

    def web_url(self, context: Context) -> str:
        return f"https://{self.host}/{context['owner']}/{context['repo']}/-/merge_requests/{context['number']}"
