"""PR watcher contracts using deterministic GitHub responses and a fake clock."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import shutil
import sys
import unittest
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from types import ModuleType

DIRECTORY = Path(__file__).resolve().parents[1] / "skills/z-mode/scripts/watch-pr"
CONTEXT = {"owner": "owner", "repo": "repo", "number": 1}


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required test executable not found: {name}")
    return path


def facts(**changes: object) -> dict[str, Any]:
    return {
        "context": CONTEXT,
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


def check(kind: str = "passed", name: str = "CI") -> dict[str, Any]:
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
    def __init__(self) -> None:
        self.facts = facts()
        self.checks = [check()]
        self.threads: list[dict[str, Any]] = []
        self.rollups = [{"oid": "head", "state": "SUCCESS"}]
        self.rollup_reads = 0
        self.pages: list[dict[str, Any]] = []
        self.reads: list[int] = []

    def pull_request(self, context: dict[str, Any]) -> dict[str, Any]:
        self.reads.append(context["number"])
        return copy.deepcopy(self.facts) | {"context": context}

    def checks_fast_path(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "checks", "checks": self.checks}

    def check_rollup_page(self, context: dict[str, Any], after: str | None) -> dict[str, Any]:
        return self.pages.pop(0) if self.pages else {"checks": [], "endCursor": None}

    def review_threads(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return self.threads

    def commit_rollups(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        self.rollup_reads += 1
        return self.rollups

    def origin_repo(self) -> dict[str, str]:
        return {"owner": "origin", "repo": "repo"}

    def current_pr(self, pr: int | None) -> dict[str, Any]:
        return CONTEXT | {"number": pr or 1}

    def open_pull_requests(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return []


class WatcherTests(unittest.TestCase):
    github: ModuleType
    policy: ModuleType
    render: ModuleType
    cli: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        for name in ("github", "policy", "render", "cli"):
            spec = importlib.util.spec_from_file_location(name, DIRECTORY / (name + ".py"))
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load {name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            setattr(cls, name, module)

    def setUp(self) -> None:
        self.reader, self.clock = Reader(), Clock()
        self.events: list[dict[str, Any]] = []
        self.options = {"interval": 60, "sweepInterval": 300, "timeout": 0, "maxQueryErrors": 5, "allowDraft": False}

    def snapshot(self, **changes: object) -> dict[str, Any]:
        self.reader.facts.update(changes)
        return self.policy.read_snapshot(self.reader, CONTEXT)

    def run_simple(self, **kwargs: object) -> dict[str, Any]:
        return self.policy.run_simple(self.reader, self.clock, self.events.append, [CONTEXT], self.options, **kwargs)

    def test_merge_assessment_truth_table(self) -> None:
        for state in ("BLOCKED", "CLEAN", "UNKNOWN", "UNSTABLE", "DIRTY"):
            for rollup in (None, "SUCCESS", "EXPECTED", "PENDING", "ERROR", "FAILURE"):
                with self.subTest(state=state, rollup=rollup):
                    result = self.policy.assess_github_merge(state, rollup)
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
        self.options["allowDraft"] = True
        self.assertEqual(self.run_simple()["kind"], "READY")

    def test_priority_across_stack(self) -> None:
        first = self.snapshot()
        first["threads"] = [{"id": "thread"}]
        second = self.snapshot(mergeable="CONFLICTING")
        second["context"] = CONTEXT | {"number": 2}
        decision = self.policy.select_stack_decision([first, second])
        self.assertEqual(decision["blocker"]["kind"], "merge-conflicts")
        self.assertEqual(decision["blocker"]["pr"]["number"], 2)

    def test_pending_frontier_is_actual_waiting_pr(self) -> None:
        first = self.snapshot()
        self.reader.checks = [check("pending")]
        second = self.snapshot()
        second["context"] = CONTEXT | {"number": 2}
        decision = self.policy.select_stack_decision([first, second])
        self.assertEqual(decision["frontier"]["number"], 2)
        self.assertEqual(len(decision["pending"]), 1)

    def test_snapshot_skips_history_only_for_pending_queue(self) -> None:
        self.reader.checks = [check("pending")]
        self.policy.read_snapshot(self.reader, CONTEXT, pending_history="omit")
        self.assertEqual(self.reader.rollup_reads, 0)
        self.reader.checks = [check("failed")]
        self.policy.read_snapshot(self.reader, CONTEXT, pending_history="omit")
        self.assertEqual(self.reader.rollup_reads, 1)
        self.reader.facts["state"] = "MERGED"
        with patch.object(self.reader, "review_threads", side_effect=AssertionError("merged PR must short circuit")):
            self.assertEqual(self.snapshot()["kind"], "merged")

    def test_poll_and_retry_delays_are_bounded(self) -> None:
        self.options["timeout"] = 10
        self.reader.checks = [check("pending")]
        self.assertEqual(self.run_simple()["exitCode"], 5)
        self.assertEqual(self.clock.sleeps, [10])
        self.clock = Clock()
        failure = self.github.QueryError("checks-unavailable", "unavailable")
        with patch.object(self.reader, "pull_request", side_effect=failure):
            result = self.run_simple()
        self.assertEqual(result["reason"]["kind"], "status-unavailable")
        self.assertEqual(self.clock.sleeps, [10])

    def test_retry_budget_and_nonretryable_failure(self) -> None:
        self.options["maxQueryErrors"] = 3
        with patch.object(self.reader, "pull_request", side_effect=self.github.QueryError("json-parse", "bad")):
            result = self.run_simple()
        self.assertEqual(result["exitCode"], 7)
        self.assertEqual(self.clock.sleeps, [60, 120])
        self.assertEqual(result["blocker"]["failures"], 3)

    def test_checks_fallback_and_empty_fail_closed(self) -> None:
        self.reader.checks = []
        self.reader.pages = [
            {"checks": [check("pending")], "endCursor": "next"},
            {"checks": [check()], "endCursor": None},
        ]
        result = self.github.resolve_checks(self.reader, CONTEXT)
        self.assertEqual(result["source"], "graphql-rollup")
        self.assertEqual(len(result["checks"]), 2)
        with self.assertRaises(self.github.QueryError):
            self.github.resolve_checks(self.reader, CONTEXT)

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
                self.github.map_rollup_node(
                    {"__typename": "CheckRun", "name": "CI", "status": "COMPLETED", "conclusion": state}
                )["kind"],
                kind,
            )
        self.assertEqual(
            self.github.map_rollup_node(
                {"__typename": "CheckRun", "name": "Code Review Gate", "status": "IN_PROGRESS"}
            )["kind"],
            "code-review-gate",
        )
        for state, kind in [
            ("PENDING", "pending"),
            ("EXPECTED", "pending"),
            ("SUCCESS", "passed"),
            ("ERROR", "failed"),
        ]:
            self.assertEqual(
                self.github.map_rollup_node({"__typename": "StatusContext", "context": "CI", "state": state})["kind"],
                kind,
            )
        self.assertIsNone(self.github.map_rollup_node({"__typename": "FutureType"}))
        self.assertEqual(
            self.github.parse_fast_check({"name": "Code Review Gate", "state": "PENDING", "bucket": "pending"})["kind"],
            "code-review-gate",
        )
        self.assertEqual(
            self.github.parse_fast_check({"name": "CI", "state": "ERROR", "bucket": "pass"})["kind"], "failed"
        )

    def test_closed_enums_and_empty_review_decision(self) -> None:
        self.assertIsNone(self.github.parse_pull_request(facts(reviewDecision=""), CONTEXT)["reviewDecision"])
        for changes in [{"reviewDecision": "FUTURE"}, {"mergeStateStatus": "FUTURE"}, {"isDraft": "false"}]:
            with self.assertRaises(self.github.QueryError):
                self.github.parse_pull_request(facts(**changes), CONTEXT)

    def test_context_and_stack_order(self) -> None:
        self.assertEqual(
            self.github.resolve_context(self.reader, "x", "y", 3), {"owner": "x", "repo": "y", "number": 3}
        )
        self.assertEqual(self.github.resolve_context(self.reader, None, None, 3)["owner"], "origin")
        rows = [
            {"number": 3, "headRefName": "c", "baseRefName": "b"},
            {"number": 1, "headRefName": "a", "baseRefName": "main"},
            {"number": 2, "headRefName": "b", "baseRefName": "a"},
        ]
        self.assertEqual([r["number"] for r in self.github.order_stack(CONTEXT | {"number": 2}, rows)], [1, 2, 3])

    def test_queue_advances_without_sleep_and_keeps_queue(self) -> None:
        contexts = [CONTEXT, CONTEXT | {"number": 2}]
        seen = {1: 0, 2: 0}

        def read(context: dict[str, Any]) -> dict[str, Any]:
            n = context["number"]
            seen[n] += 1
            return facts(
                context=context, state="MERGED" if seen[n] > 1 else "OPEN", mergedAt="now" if seen[n] > 1 else None
            )

        with patch.object(self.reader, "pull_request", side_effect=read):
            result = self.policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        self.assertEqual(result["kind"], "COMPLETE")
        self.assertEqual(result["queue"], contexts)
        self.assertEqual(self.clock.sleeps, [60])
        self.assertEqual([e["kind"] for e in self.events], ["QUEUE", "STATUS", "WAITING", "ADVANCE"])

    def test_queue_resumes_failed_sweep_and_bounds_timeout(self) -> None:
        contexts = [CONTEXT, CONTEXT | {"number": 2}]
        reads = []

        def read(context: dict[str, Any]) -> dict[str, Any]:
            reads.append(context["number"])
            if reads == [1, 2]:
                raise self.github.QueryError("json-parse", "retry second")
            return facts(context=context)

        self.options["timeout"] = 70
        with patch.object(self.reader, "pull_request", side_effect=read):
            result = self.policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
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
                code = self.cli.main(args, reader=self.reader, clock=self.clock, stdout=out, stderr=err)
                self.assertEqual(code, 64)
                self.assertEqual(out.getvalue(), "")
        out = io.StringIO()
        code = self.cli.main(
            ["--owner", "x", "--repo", "y", "--queued-stack", "--stack-prs", "1,2", "--status-only"],
            reader=self.reader,
            clock=self.clock,
            stdout=out,
        )
        self.assertEqual(code, 0)
        event = json.loads(out.getvalue())
        self.assertEqual(event["reason"], "status-only")
        self.assertEqual(len(event["rows"]), 2)
        self.assertIn("| PR | CI | Review | Merge |", self.render.render_pretty(event))

    def test_threads_pagination_and_bugbot_passes(self) -> None:
        def thread(id: str, resolved: bool, run: str) -> dict[str, Any]:
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

        def query(argv: list[str]) -> dict[str, Any]:
            calls.append(argv)
            return {"data": {"repository": {"pullRequest": {"reviewThreads": pages.pop(0)}}}}

        rows = self.github.GitHubReader(query).review_threads(CONTEXT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "unresolved")
        self.assertEqual(rows[0]["bugbotReviewPasses"], 2)
        self.assertIn("after=next", calls[1])

    def test_invalid_or_cyclic_pagination_is_rejected(self) -> None:
        for cursor in (None, ""):

            def query(argv: list[str], cursor: str | None = cursor) -> dict[str, Any]:
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": cursor}}
                            }
                        }
                    }
                }

            with self.assertRaises(self.github.QueryError):
                self.github.GitHubReader(query).review_threads(CONTEXT)
        self.reader.checks = []
        self.reader.pages = [{"checks": [check()], "endCursor": "same"}, {"checks": [], "endCursor": "same"}]
        with self.assertRaises(self.github.QueryError):
            self.github.resolve_checks(self.reader, CONTEXT)

    def test_fast_checks_accept_pending_exit_and_fallback_on_malformed(self) -> None:
        import subprocess

        for code in (0, 1, 8):
            with patch.object(
                self.github,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], code, json.dumps([{"name": "CI", "state": "PENDING", "bucket": "pending"}]), ""
                ),
            ):
                self.assertEqual(self.github.GitHubReader().checks_fast_path(CONTEXT)["checks"][0]["kind"], "pending")
        for text in ("bad json", "[{}]", "{}"):
            with patch.object(self.github, "run", return_value=subprocess.CompletedProcess([], 0, text, "")):
                self.assertEqual(self.github.GitHubReader().checks_fast_path(CONTEXT)["kind"], "unusable")

    def test_context_urls_fail_closed(self) -> None:
        for url in (
            "https://evil.test/o/r/pull/1",
            "https://github.com/o/r/pull/1?x=1",
            "https://user@github.com/o/r/pull/1",
            "https://github.com/o/r/pull/0",
        ):
            with self.assertRaises(self.github.QueryError):
                self.github.parse_pr_url(url)
        self.assertEqual(self.github.parse_remote("git@github.com:o/r.git"), {"owner": "o", "repo": "r"})
        self.assertIsNone(self.github.parse_remote("https://evil.test/o/r"))

    def test_queue_deduplicates_waits_and_sweeps_upstack(self) -> None:
        self.options.update(timeout=180, sweepInterval=120)
        contexts = [CONTEXT, CONTEXT | {"number": 2}]
        result = self.policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        self.assertEqual(result["exitCode"], 5)
        self.assertEqual(self.reader.reads, [1, 2, 1, 1, 2])
        self.assertEqual(len([e for e in self.events if e["kind"] == "WAITING"]), 1)
        self.assertEqual(len([e for e in self.events if e["kind"] == "STATUS"]), 2)

    def test_queue_ignores_upstack_pending_for_merge_frontier_wait(self) -> None:
        contexts = [CONTEXT, CONTEXT | {"number": 2}]

        def checks(context: dict[str, Any]) -> dict[str, Any]:
            return {"kind": "checks", "checks": [check("pending" if context["number"] == 2 else "passed")]}

        self.options["timeout"] = 10
        with patch.object(self.reader, "checks_fast_path", side_effect=checks):
            self.policy.run_queued(self.reader, self.clock, self.events.append, contexts, self.options)
        waiting = next(e for e in self.events if e["kind"] == "WAITING")
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
