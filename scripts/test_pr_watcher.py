"""PR watcher contracts using deterministic GitHub responses and a fake clock."""

from __future__ import annotations

import dataclasses
import importlib.util
import io
import json
import shutil
import sys
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

DIRECTORY = Path(__file__).resolve().parents[1] / "skills/z-mode/scripts/watch-pr"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / (name + ".py"))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    import cli
    import github
    import gitlab
    import policy
    import render
    import schema
else:
    # The helpers import each other by bare name, so load dependencies first.
    schema, github, gitlab, policy, render, cli = (
        load(name) for name in ("schema", "github", "gitlab", "policy", "render", "cli")
    )

CONTEXT: schema.Context = {"owner": "owner", "repo": "repo", "number": 1}
GOLDEN = Path(__file__).resolve().parent / "fixtures/watch-pr-events.golden"


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required test executable not found: {name}")
    return path


def facts(**changes: object) -> dict[str, object]:
    return {
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": None,
        "headRefOid": "head",
        "headRefName": "topic",
        "baseRefName": "main",
        "state": "OPEN",
        "mergedAt": None,
        "isDraft": False,
    } | changes


def check(kind: schema.CheckKind = "passed", name: str = "CI") -> schema.Check:
    return {
        "name": name,
        "kind": kind,
        "reportedState": {"passed": "SUCCESS", "pending": "PENDING", "failed": "FAILURE"}.get(kind, "PENDING"),
        "description": "",
        "link": "",
        "workflow": "",
    }


class Clock:
    def __init__(self) -> None:
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def observed_at(self) -> str:
        return "2026-10-04T00:00:00.000Z"

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds


class Reader:
    """Fake gh adapter; the per-PR fields script multi-PR and retry scenarios."""

    forge = "GitHub"

    def __init__(
        self,
        *,
        overrides: dict[str, object] | None = None,
        checks: list[schema.Check] | None = None,
        threads: list[schema.Thread] | None = None,
        rollups: list[github.CommitRollup] | None = None,
        overrides_by_pr: dict[int, dict[str, object]] | None = None,
        merged_from_read: dict[int, int] | None = None,
        checks_by_pr: dict[int, list[schema.Check]] | None = None,
        open_prs: list[github.OpenPullRequest] | None = None,
        query_failures: int = 0,
    ) -> None:
        self.facts = facts(**(overrides or {}))
        self.fast_checks = [check()] if checks is None else checks
        self.threads = threads or []
        self.rollups: list[github.CommitRollup] = (
            rollups if rollups is not None else [{"oid": "head", "state": "SUCCESS"}]
        )
        self.overrides_by_pr = overrides_by_pr or {}
        self.merged_from_read = merged_from_read or {}
        self.checks_by_pr = checks_by_pr or {}
        self.open_prs = open_prs or []
        self.query_failures = query_failures
        self.rollup_reads = 0
        self.pages: list[github.RollupPage] = []
        self.reads: list[int] = []

    def pull_request(self, context: schema.Context) -> schema.PullRequestFacts:
        if self.query_failures:
            self.query_failures -= 1
            raise github.QueryError("json-parse", "bad response")
        n = context["number"]
        self.reads.append(n)
        merged = 0 < self.merged_from_read.get(n, 0) <= self.reads.count(n)
        changes: dict[str, object] = {"state": "MERGED", "mergedAt": "now"} if merged else {}
        return github.parse_pull_request(self.facts | self.overrides_by_pr.get(n, {}) | changes, context)

    def checks_fast_path(self, context: schema.Context) -> github.FastChecks | github.UnusableChecks:
        return {"kind": "checks", "checks": self.checks_by_pr.get(context["number"], self.fast_checks)}

    def check_rollup_page(self, context: schema.Context, after: str | None) -> github.RollupPage:
        return self.pages.pop(0) if self.pages else {"checks": [], "endCursor": None}

    def checks(self, context: schema.Context) -> github.ResolvedChecks:
        return github.resolve_checks(self, context)

    def web_url(self, context: schema.Context) -> str:
        return f"https://{self.forge.lower()}.com/{context['owner']}/{context['repo']}/pull/{context['number']}"

    def review_threads(self, context: schema.Context) -> list[schema.Thread]:
        return self.threads

    def commit_rollups(self, context: schema.Context) -> list[github.CommitRollup]:
        self.rollup_reads += 1
        return self.rollups

    def origin_repo(self) -> schema.Repo:
        return {"owner": "origin", "repo": "repo"}

    def current_pr(self, pr: int | None) -> schema.Context:
        return {**CONTEXT, "number": pr or 1}

    def open_pull_requests(self, context: schema.Context) -> list[github.OpenPullRequest]:
        return self.open_prs


STACK: list[github.OpenPullRequest] = [
    {"number": 1, "headRefName": "a", "baseRefName": "main"},
    {"number": 2, "headRefName": "b", "baseRefName": "a"},
]
COMMENT: schema.Comment = {
    "authorLogin": "cursor",
    "body": "Bugbot RUN_ID: one\nsecond line",
    "path": "app.py",
    "line": 3,
    "createdAt": "now",
}
# One run per verdict, blocker, wait, and timeout shape; --pr 1 is added unless --stack-prs selects PRs.
GOLDEN_SCENARIOS: list[tuple[str, list[str], Callable[[], Reader]]] = [
    ("ready", [], Reader),
    ("ready-allow-draft", ["--allow-draft"], lambda: Reader(overrides={"isDraft": True})),
    ("merged", [], lambda: Reader(overrides={"state": "MERGED", "mergedAt": "now"})),
    ("merge-conflicts", [], lambda: Reader(overrides={"mergeable": "CONFLICTING"})),
    (
        "review-threads",
        [],
        lambda: Reader(
            threads=[
                {"id": "t1", "firstComment": COMMENT, "isBugbot": True, "bugbotReviewPasses": 1},
                {"id": "t2", "firstComment": None, "isBugbot": False, "bugbotReviewPasses": 1},
            ]
        ),
    ),
    ("failing-checks", [], lambda: Reader(checks=[check(), check("failed"), check("pending")])),
    (
        "github-rejected",
        [],
        lambda: Reader(
            overrides={"mergeStateStatus": "BLOCKED"},
            rollups=[{"oid": "older", "state": "SUCCESS"}, {"oid": "head", "state": "FAILURE"}],
        ),
    ),
    (
        "owner-gate",
        [],
        lambda: Reader(
            overrides={"mergeStateStatus": "BLOCKED"},
            checks=[check(), {**check("code-review-gate", "Code Review Gate"), "reportedState": "ACTION_REQUIRED"}],
            rollups=[{"oid": "head", "state": "FAILURE"}],
        ),
    ),
    ("draft-gate", [], lambda: Reader(overrides={"isDraft": True})),
    ("changes-requested", [], lambda: Reader(overrides={"reviewDecision": "CHANGES_REQUESTED"})),
    ("closed", [], lambda: Reader(overrides={"state": "CLOSED"})),
    (
        "pending-timeout",
        ["--stack", "--timeout", "100"],
        lambda: Reader(checks=[check("pending"), check("pending", "Bugbot")]),
    ),
    ("retry-then-ready", [], lambda: Reader(query_failures=2)),
    ("status-query", ["--max-query-errors", "2"], lambda: Reader(query_failures=9)),
    ("status-unavailable-timeout", ["--timeout", "90"], lambda: Reader(query_failures=9)),
    ("stack-ready", ["--stack"], lambda: Reader(open_prs=STACK)),
    ("stack-status-only", ["--stack", "--status-only"], lambda: Reader(open_prs=STACK)),
    ("queued-complete", ["--queued-stack", "--stack-prs", "1,2"], lambda: Reader(merged_from_read={1: 2, 2: 2})),
    (
        "queued-pending-timeout",
        ["--queued-stack", "--stack-prs", "1,2", "--timeout", "200", "--sweep-interval", "90"],
        lambda: Reader(checks_by_pr={1: [check("pending")]}),
    ),
    ("queued-merge-queue-timeout", ["--queued-stack", "--stack-prs", "1,2", "--timeout", "100"], Reader),
    (
        "queued-closed",
        ["--queued-stack", "--stack-prs", "1,2"],
        lambda: Reader(overrides_by_pr={2: {"state": "CLOSED"}}),
    ),
    ("queued-status-only", ["--queued-stack", "--stack-prs", "1,2", "--status-only"], Reader),
]


def golden_stream() -> str:
    chunks = []
    for name, args, reader in GOLDEN_SCENARIOS:
        argv = ["--owner", "owner", "--repo", "repo", *args, *([] if "--stack-prs" in args else ["--pr", "1"])]
        for pretty in ([], ["--pretty"]):
            out = io.StringIO()
            code = cli.main([*argv, *pretty], reader=reader(), clock=Clock(), stdout=out, stderr=io.StringIO())
            chunks.append(f"== {' '.join([name, *pretty])} exit={code}\n{out.getvalue()}")
    return "".join(chunks)


class GoldenStreamTests(unittest.TestCase):
    def test_ndjson_and_pretty_output_match_golden_bytes(self) -> None:
        # Key order and rendering are the wire contract; the golden file pins both byte for byte.
        self.maxDiff = None
        self.assertEqual(golden_stream(), GOLDEN.read_text(encoding="utf-8"))

    def test_pretty_output_names_the_reader_forge(self) -> None:
        out = io.StringIO()
        for _, args, factory in GOLDEN_SCENARIOS:
            reader = factory()
            reader.forge = "GitLab"
            argv = ["--owner", "group/sub", "--repo", "repo", "--pretty", *args]
            cli.main(
                [*argv, *([] if "--stack-prs" in args else ["--pr", "1"])], reader=reader, clock=Clock(), stdout=out
            )
        text = out.getvalue()
        self.assertNotIn("GitHub", text)
        self.assertNotIn("github.com", text)
        for phrase in ("GitLab authentication", "GitLab status", "https://gitlab.com/group/sub/"):
            self.assertIn(phrase, text)
        reader = Reader(overrides={"mergeStateStatus": "BLOCKED"}, rollups=[{"oid": "head", "state": "FAILURE"}])
        reader.forge = "GitLab"
        row = render.status_table([policy.read_snapshot(reader, CONTEXT)], reader)
        self.assertIn("❌ GitLab reports failing checks", row)


class ForgeSelectionTests(unittest.TestCase):
    def test_auto_detection_and_explicit_gitlab_host(self) -> None:
        for origin, forge, env, expected in [
            ("git@github.com:o/r.git", None, "gitlab.example.com", None),
            ("https://github.com/o/r", None, None, None),
            ("git@gitlab.example.com:group/sub/proj.git", None, None, "gitlab.example.com"),
            ("https://gitlab.com/group/proj.git", None, None, "gitlab.com"),
            ("git@code.example.com:o/r.git", None, None, None),
            ("", None, None, None),
            ("git@gitlab.example.com:group/proj.git", "github", None, None),
            ("git@gitlab.example.com:group/proj.git", "gitlab", "other.example.com", "gitlab.example.com"),
            ("", "gitlab", "https://gitlab.internal/", "gitlab.internal"),
            ("", "gitlab", " ", "gitlab.com"),
            ("", "gitlab", None, "gitlab.com"),
            ("git@github.com:o/r.git", "gitlab", None, "gitlab.com"),
            ("https://github.com/o/r", "gitlab", "gitlab.internal", "gitlab.internal"),
        ]:
            with self.subTest(origin=origin, forge=forge, env=env):
                self.assertEqual(cli.gitlab_host(origin, forge, env), expected)

    def test_github_reader_url(self) -> None:
        self.assertEqual(github.GitHubReader().web_url(CONTEXT), "https://github.com/owner/repo/pull/1")


class WatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader, self.clock = Reader(), Clock()
        self.events: list[schema.Event] = []
        self.options = policy.Options(interval=60, sweep_interval=300, timeout=0, max_query_errors=5, allow_draft=False)

    def snapshot(self, **changes: object) -> schema.Snapshot:
        self.reader.facts.update(changes)
        return policy.read_snapshot(self.reader, CONTEXT)

    def run_simple(self) -> schema.Verdict:
        return policy.run_simple(self.reader, self.clock, self.events.append, [CONTEXT], self.options)

    def test_merge_assessment_truth_table(self) -> None:
        states: tuple[schema.MergeState, ...] = ("BLOCKED", "CLEAN", "UNKNOWN", "UNSTABLE", "DIRTY")
        rollups: tuple[schema.RollupState | None, ...] = (None, "SUCCESS", "EXPECTED", "PENDING", "ERROR", "FAILURE")
        for state in states:
            for rollup in rollups:
                with self.subTest(state=state, rollup=rollup):
                    result = policy.assess_github_merge(state, rollup)
                    self.assertEqual(
                        result["kind"],
                        "refused" if state == "BLOCKED" and rollup in ("ERROR", "FAILURE") else "allowed",
                    )

    def test_hidden_ci_refusal_and_draft_gate(self) -> None:
        self.reader.rollups = [{"oid": "head", "state": "FAILURE"}]
        self.reader.facts["mergeStateStatus"] = "BLOCKED"
        self.assertEqual(self.run_simple()["exitCode"], 4)
        self.reader.rollups = []
        self.reader.facts.update(mergeStateStatus="CLEAN", isDraft=True)
        self.assertEqual(self.run_simple()["exitCode"], 6)
        self.options = dataclasses.replace(self.options, allow_draft=True)
        self.assertEqual(self.run_simple()["kind"], "READY")

    def test_owner_gate_failing_rollup_is_not_refusal(self) -> None:
        self.reader.rollups = [{"oid": "head", "state": "FAILURE"}]
        self.reader.facts["mergeStateStatus"] = "BLOCKED"
        gate: schema.Check = {**check("code-review-gate", "Code Review Gate"), "reportedState": "ACTION_REQUIRED"}
        self.reader.fast_checks = [check(), gate]
        self.assertEqual(self.run_simple()["kind"], "READY")
        self.assertEqual(
            policy.assess_github_merge("BLOCKED", "FAILURE", True),
            {"mergeStateStatus": "BLOCKED", "headRollupState": "FAILURE", "kind": "allowed", "basis": "owner-gate"},
        )
        self.reader.fast_checks = [check(), check("code-review-gate", "Code Review Gate")]
        self.assertEqual(self.run_simple()["exitCode"], 4)

    def test_priority_across_stack(self) -> None:
        self.reader.threads = [{"id": "thread", "firstComment": None, "isBugbot": False, "bugbotReviewPasses": 0}]
        first = self.snapshot()
        self.reader.threads = []
        second = self.snapshot(mergeable="CONFLICTING")
        second["context"] = {**CONTEXT, "number": 2}
        decision = policy.select_stack_decision([first, second])
        if decision["kind"] != "blocker" or decision["blocker"]["kind"] == "status-query":
            self.fail(f"unexpected decision {decision}")
        self.assertEqual(decision["blocker"]["kind"], "merge-conflicts")
        self.assertEqual(decision["blocker"]["pr"]["number"], 2)

    def test_pending_frontier_is_actual_waiting_pr(self) -> None:
        first = self.snapshot()
        self.reader.fast_checks = [check("pending")]
        second = self.snapshot()
        second["context"] = {**CONTEXT, "number": 2}
        decision = policy.select_stack_decision([first, second])
        if decision["kind"] != "waiting":
            self.fail(f"unexpected decision {decision}")
        self.assertEqual(decision["frontier"]["number"], 2)
        self.assertEqual(len(decision["pending"]), 1)

    def test_snapshot_skips_history_only_for_pending_queue(self) -> None:
        self.reader.fast_checks = [check("pending")]
        policy.read_snapshot(self.reader, CONTEXT, pending_history="omit")
        self.assertEqual(self.reader.rollup_reads, 0)
        self.reader.fast_checks = [check("failed")]
        policy.read_snapshot(self.reader, CONTEXT, pending_history="omit")
        self.assertEqual(self.reader.rollup_reads, 1)
        self.reader.facts["state"] = "MERGED"
        with patch.object(self.reader, "review_threads", side_effect=AssertionError("merged PR must short circuit")):
            self.assertEqual(self.snapshot()["kind"], "merged")

    def test_poll_and_retry_delays_are_bounded(self) -> None:
        self.options = dataclasses.replace(self.options, timeout=10)
        self.reader.fast_checks = [check("pending")]
        self.assertEqual(self.run_simple()["exitCode"], 5)
        self.assertEqual(self.clock.sleeps, [10])
        self.clock = Clock()
        failure = github.QueryError("checks-unavailable", "unavailable")
        with patch.object(self.reader, "pull_request", side_effect=failure):
            result = self.run_simple()
        if result["kind"] != "TIMEOUT":
            self.fail(f"unexpected verdict {result}")
        self.assertEqual(result["reason"]["kind"], "status-unavailable")
        self.assertEqual(self.clock.sleeps, [10])

    def test_retry_budget_and_nonretryable_failure(self) -> None:
        self.options = dataclasses.replace(self.options, max_query_errors=3)
        with patch.object(self.reader, "pull_request", side_effect=github.QueryError("json-parse", "bad")):
            result = self.run_simple()
        if result["kind"] != "BLOCKER" or result["blocker"]["kind"] != "status-query":
            self.fail(f"unexpected verdict {result}")
        self.assertEqual(result["exitCode"], 7)
        self.assertEqual(self.clock.sleeps, [60, 120])
        self.assertEqual(result["blocker"]["failures"], 3)

    def test_checks_fallback_and_empty_fail_closed(self) -> None:
        self.reader.fast_checks = []
        self.reader.pages = [
            {"checks": [check("pending")], "endCursor": "next"},
            {"checks": [check()], "endCursor": None},
        ]
        result = github.resolve_checks(self.reader, CONTEXT)
        self.assertEqual(result["source"], "graphql-rollup")
        self.assertEqual(len(result["checks"]), 2)
        with self.assertRaises(github.QueryError):
            github.resolve_checks(self.reader, CONTEXT)

    def mapped_kind(self, node: object) -> str:
        check = github.map_rollup_node(node)
        if check is None:
            self.fail(f"unmapped rollup node {node}")
        return check["kind"]

    def test_check_mapping(self) -> None:
        for state, kind in [
            ("SUCCESS", "passed"),
            ("SKIPPED", "skipped"),
            ("NEUTRAL", "skipped"),
            ("FAILURE", "failed"),
            ("ACTION_REQUIRED", "failed"),
            ("UNKNOWN", "failed"),
        ]:
            self.assertEqual(
                self.mapped_kind({"__typename": "CheckRun", "name": "CI", "status": "COMPLETED", "conclusion": state}),
                kind,
            )
        self.assertEqual(
            self.mapped_kind({"__typename": "CheckRun", "name": "Code Review Gate", "status": "IN_PROGRESS"}),
            "code-review-gate",
        )
        for state, kind in [
            ("PENDING", "pending"),
            ("EXPECTED", "pending"),
            ("SUCCESS", "passed"),
            ("ERROR", "failed"),
        ]:
            self.assertEqual(
                self.mapped_kind({"__typename": "StatusContext", "context": "CI", "state": state}),
                kind,
            )
        self.assertIsNone(github.map_rollup_node({"__typename": "FutureType"}))
        self.assertEqual(
            github.parse_fast_check({"name": "Code Review Gate", "state": "PENDING", "bucket": "pending"})["kind"],
            "code-review-gate",
        )
        self.assertEqual(github.parse_fast_check({"name": "CI", "state": "ERROR", "bucket": "pass"})["kind"], "failed")

    def test_owner_approval_gate_is_neither_pending_nor_failed(self) -> None:
        gate = github.map_rollup_node(
            {
                "__typename": "CheckRun",
                "name": "Code Review Gate",
                "status": "COMPLETED",
                "conclusion": "ACTION_REQUIRED",
            }
        )
        if gate is None:
            self.fail("gate check was not mapped")
        self.assertEqual((gate["kind"], gate["reportedState"]), ("code-review-gate", "ACTION_REQUIRED"))
        self.assertEqual(
            github.parse_fast_check({"name": "Code Review Gate", "state": "ACTION_REQUIRED", "bucket": "fail"})["kind"],
            "code-review-gate",
        )
        other = github.parse_fast_check({"name": "CI", "state": "ACTION_REQUIRED", "bucket": "fail"})
        self.assertEqual((other["kind"], other["reportedState"]), ("failed", "ACTION_REQUIRED"))

    def test_closed_enums_and_empty_review_decision(self) -> None:
        self.assertIsNone(github.parse_pull_request(facts(reviewDecision=""), CONTEXT)["reviewDecision"])
        for changes in [{"reviewDecision": "FUTURE"}, {"mergeStateStatus": "FUTURE"}, {"isDraft": "false"}]:
            with self.assertRaises(github.QueryError):
                github.parse_pull_request(facts(**changes), CONTEXT)

    def test_first_invalid_field_is_reported_in_field_order(self) -> None:
        payload = {k: v for k, v in facts(mergeable="FUTURE").items() if k != "reviewDecision"}
        with self.assertRaises(github.QueryError) as caught:
            github.parse_pull_request(payload, CONTEXT)
        self.assertEqual(caught.exception.failure["detail"], 'invalid pull request.mergeable: "FUTURE"')

    def test_context_and_stack_order(self) -> None:
        self.assertEqual(github.resolve_context(self.reader, "x", "y", 3), {"owner": "x", "repo": "y", "number": 3})
        self.assertEqual(github.resolve_context(self.reader, None, None, 3)["owner"], "origin")
        rows: list[github.OpenPullRequest] = [
            {"number": 3, "headRefName": "c", "baseRefName": "b"},
            {"number": 1, "headRefName": "a", "baseRefName": "main"},
            {"number": 2, "headRefName": "b", "baseRefName": "a"},
        ]
        self.assertEqual([r["number"] for r in github.order_stack({**CONTEXT, "number": 2}, rows)], [1, 2, 3])

    def test_queue_advances_without_sleep_and_keeps_queue(self) -> None:
        contexts: list[schema.Context] = [CONTEXT, {**CONTEXT, "number": 2}]
        seen = {1: 0, 2: 0}

        def read(context: schema.Context) -> schema.PullRequestFacts:
            n = context["number"]
            seen[n] += 1
            merged = seen[n] > 1
            return github.parse_pull_request(
                facts(state="MERGED" if merged else "OPEN", mergedAt="now" if merged else None), context
            )

        with patch.object(self.reader, "pull_request", side_effect=read):
            result = policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        if result["kind"] != "COMPLETE":
            self.fail(f"unexpected verdict {result}")
        self.assertEqual(result["queue"], contexts)
        self.assertEqual(self.clock.sleeps, [60])
        self.assertEqual([e["kind"] for e in self.events], ["QUEUE", "STATUS", "WAITING", "ADVANCE"])

    def test_queue_resumes_failed_sweep_and_bounds_timeout(self) -> None:
        contexts: list[schema.Context] = [CONTEXT, {**CONTEXT, "number": 2}]
        reads = []

        def read(context: schema.Context) -> schema.PullRequestFacts:
            reads.append(context["number"])
            if reads == [1, 2]:
                raise github.QueryError("json-parse", "retry second")
            return github.parse_pull_request(facts(), context)

        self.options = dataclasses.replace(self.options, timeout=70)
        with patch.object(self.reader, "pull_request", side_effect=read):
            result = policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        self.assertEqual(reads, [1, 2, 2])
        self.assertEqual(self.clock.sleeps, [60, 10])
        self.assertEqual(result["exitCode"], 5)
        self.assertEqual(len([e for e in self.events if e["kind"] == "STATUS"]), 1)

    def test_cli_usage_and_status_json(self) -> None:
        for args in [
            ["--stack", "--queued-stack"],
            ["--stack-prs", "1"],
            ["--interval", "0"],
            ["--timeout", "-1"],
            ["--pr", "NaN"],
            ["--max-query-errors", "1.5"],
            ["--queued-stack", "--stack-prs", "1,1"],
        ]:
            with self.subTest(args=args):
                out, err = io.StringIO(), io.StringIO()
                code = cli.main(args, reader=self.reader, clock=self.clock, stdout=out, stderr=err)
                self.assertEqual(code, 64)
                self.assertEqual(out.getvalue(), "")
        out = io.StringIO()
        code = cli.main(
            ["--owner", "x", "--repo", "y", "--queued-stack", "--stack-prs", "1,2", "--status-only"],
            reader=self.reader,
            clock=self.clock,
            stdout=out,
        )
        self.assertEqual(code, 0)
        event = json.loads(out.getvalue())
        self.assertEqual(event["reason"], "status-only")
        self.assertEqual(len(event["rows"]), 2)
        self.assertIn("| PR | CI | Review | Merge |", render.render_pretty(event, self.reader))

    def test_frozen_stack_accepts_whitespace_and_hash_prefixes(self) -> None:
        for value in ("#10, 11,#12", " #10, #11,\t#12 "):
            with self.subTest(value=value):
                args = cli.parse_args(["--queued-stack", "--stack-prs", value])
                self.assertEqual(args.stack_prs, [10, 11, 12])

    def test_command_streams_use_utf8_with_non_utf8_default(self) -> None:
        payload = {"branch": "作業", "check": "検査", "comment": "résumé"}
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        error = "échec: 作業".encode()
        with patch("subprocess._text_encoding", return_value="cp1252"):
            result = github.run_json([sys.executable, "-c", f"import sys; sys.stdout.buffer.write({encoded!r})"])
            self.assertEqual(result, payload)
            with self.assertRaises(github.QueryError) as caught:
                github.run_json([sys.executable, "-c", f"import sys; sys.stderr.buffer.write({error!r}); sys.exit(1)"])
            self.assertEqual(caught.exception.failure["detail"], error.decode("utf-8"))

    def test_threads_pagination_and_bugbot_passes(self) -> None:
        def thread(id: str, resolved: bool, run: str) -> dict[str, object]:
            return {
                "id": id,
                "isResolved": resolved,
                "comments": {
                    "nodes": [
                        {
                            "author": {"login": "cursor"},
                            "body": "Bugbot RUN_ID: " + run,
                            "path": "app.py",
                            "line": 1,
                            "createdAt": "now",
                        }
                    ]
                },
            }

        pages = [
            {"nodes": [thread("resolved", True, "first")], "pageInfo": {"hasNextPage": True, "endCursor": "next"}},
            {"nodes": [thread("unresolved", False, "second")], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        ]
        calls = []

        def query(argv: list[str]) -> object:
            calls.append(argv)
            return {"data": {"repository": {"pullRequest": {"reviewThreads": pages.pop(0)}}}}

        rows = github.GitHubReader(query).review_threads(CONTEXT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "unresolved")
        self.assertEqual(rows[0]["bugbotReviewPasses"], 2)
        self.assertIn("after=next", calls[1])

    def test_invalid_or_cyclic_pagination_is_rejected(self) -> None:
        for cursor in (None, ""):

            def query(argv: list[str], cursor: str | None = cursor) -> object:
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": cursor}}
                            }
                        }
                    }
                }

            with self.assertRaises(github.QueryError):
                github.GitHubReader(query).review_threads(CONTEXT)
        self.reader.fast_checks = []
        self.reader.pages = [{"checks": [check()], "endCursor": "same"}, {"checks": [], "endCursor": "same"}]
        with self.assertRaises(github.QueryError):
            github.resolve_checks(self.reader, CONTEXT)

    def test_fast_checks_accept_pending_exit_and_fallback_on_malformed(self) -> None:
        import subprocess

        for code in (0, 1, 8):
            with patch.object(
                github,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], code, json.dumps([{"name": "CI", "state": "PENDING", "bucket": "pending"}]), ""
                ),
            ):
                fast = github.GitHubReader().checks_fast_path(CONTEXT)
                if fast["kind"] != "checks":
                    self.fail(f"unexpected fast path {fast}")
                self.assertEqual(fast["checks"][0]["kind"], "pending")
        for text in ("bad json", "[{}]", "{}"):
            with patch.object(github, "run", return_value=subprocess.CompletedProcess([], 0, text, "")):
                self.assertEqual(github.GitHubReader().checks_fast_path(CONTEXT)["kind"], "unusable")

    def test_context_urls_fail_closed(self) -> None:
        for url in (
            "https://evil.test/o/r/pull/1",
            "https://github.com/o/r/pull/1?x=1",
            "https://user@github.com/o/r/pull/1",
            "https://github.com/o/r/pull/0",
        ):
            with self.assertRaises(github.QueryError):
                github.parse_pr_url(url)
        self.assertEqual(github.parse_remote("git@github.com:o/r.git"), {"owner": "o", "repo": "r"})
        self.assertIsNone(github.parse_remote("https://evil.test/o/r"))

    def test_queue_deduplicates_waits_and_sweeps_upstack(self) -> None:
        self.options = dataclasses.replace(self.options, timeout=180, sweep_interval=120)
        contexts: list[schema.Context] = [CONTEXT, {**CONTEXT, "number": 2}]
        result = policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        self.assertEqual(result["exitCode"], 5)
        self.assertEqual(self.reader.reads, [1, 2, 1, 1, 2])
        self.assertEqual(len([e for e in self.events if e["kind"] == "WAITING"]), 1)
        self.assertEqual(len([e for e in self.events if e["kind"] == "STATUS"]), 2)

    def test_queue_ignores_upstack_pending_for_merge_frontier_wait(self) -> None:
        contexts: list[schema.Context] = [CONTEXT, {**CONTEXT, "number": 2}]

        def checks(context: schema.Context) -> github.FastChecks:
            return {"kind": "checks", "checks": [check("pending" if context["number"] == 2 else "passed")]}

        self.options = dataclasses.replace(self.options, timeout=10)
        with patch.object(self.reader, "checks_fast_path", side_effect=checks):
            policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        waiting = next(e for e in self.events if e["kind"] == "WAITING")
        if waiting["kind"] != "WAITING":
            self.fail(f"unexpected event {waiting}")
        self.assertEqual(waiting["frontier"]["number"], 1)
        self.assertEqual(waiting["reason"]["kind"], "merge-queue")


class WatcherProcessTests(unittest.TestCase):
    def test_uv_cli_uses_target_cwd_and_returns_structured_verdicts(self) -> None:
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory(prefix="watcher cli ") as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text(
                f"#!{sys.executable}\n"
                """import json, os, sys
from pathlib import Path
assert Path.cwd() == Path(os.environ['EXPECTED_CWD']).resolve()
args=sys.argv[1:]
state=os.environ['CHECK_STATE']
if args[:2] == ['pr','view']:
 value=dict(mergeable='MERGEABLE',mergeStateStatus='CLEAN',reviewDecision='',headRefOid='head',headRefName='topic',baseRefName='main',state='OPEN',mergedAt=None,isDraft=False)
elif args[:2] == ['pr','checks']:
 value=[dict(name='CI',state=state,bucket='pending' if state=='PENDING' else 'pass',description='',link='',workflow='')]
 print(json.dumps(value)); sys.exit(8 if state=='PENDING' else 0)
elif args[:2] == ['api','graphql']:
 query=next(a for a in args if a.startswith('query='))
 if 'ReviewThreads' in query:
  value=dict(data=dict(repository=dict(pullRequest=dict(reviewThreads=dict(nodes=[],pageInfo=dict(hasNextPage=False,endCursor=None))))))
 elif 'PrCommitStatuses' in query:
  commit={'oid': 'head', 'statusCheckRollup': {'state': state}}
  value={'data': {'repository': {'pullRequest': {'commits': {'nodes': [{'commit': commit}]}}}}}
 else: raise AssertionError(args)
else: raise AssertionError(args)
print(json.dumps(value))
"""
            )
            gh.chmod(0o755)
            env = os.environ | {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "EXPECTED_CWD": str(root)}
            for state, code, kind in [("SUCCESS", 0, "READY"), ("PENDING", 5, "TIMEOUT")]:
                result = subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                    [
                        executable("uv"),
                        "run",
                        str(DIRECTORY / "watch_pr.py"),
                        "--owner",
                        "o",
                        "--repo",
                        "r",
                        "--pr",
                        "1",
                        "--timeout",
                        "0.01",
                    ],
                    cwd=root,
                    env=env | {"CHECK_STATE": state},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, code, result.stderr + result.stdout)
                events = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(events[-1]["kind"], kind)
                self.assertTrue(events[-1]["terminal"])
                self.assertEqual([e["sequence"] for e in events], list(range(1, len(events) + 1)))
