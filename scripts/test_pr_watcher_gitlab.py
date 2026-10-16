"""GitLab reader contracts using deterministic glab responses."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

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
    from collections.abc import Mapping, Sequence
    from types import ModuleType

    import github
    import gitlab
    import policy
    import schema
else:
    # The helpers import each other by bare name, so load dependencies first.
    schema, github, gitlab, policy, render, cli = (
        load(name) for name in ("schema", "github", "gitlab", "policy", "render", "cli")
    )

HOST = "gitlab.example.com"
PROJECT = "projects/group%2Fsub%2Fproj"
MR = PROJECT + "/merge_requests/7"
JOBS = "projects/99/pipelines/50/jobs?per_page=100"
BRIDGES = "projects/99/pipelines/50/bridges?per_page=100"
PIPELINES = MR + "/pipelines?per_page=100"
MERGE_COMMIT = "projects/99/repository/commits/merge-ref"
TRAIN = "refs/merge-requests/7/train"
# GitLab's documented detailed_merge_status values.
DOCUMENTED_STATUSES = [
    "approvals_syncing",
    "checking",
    "ci_must_pass",
    "ci_still_running",
    "commits_status",
    "conflict",
    "discussions_not_resolved",
    "draft_status",
    "jira_association_missing",
    "locked_lfs_files",
    "locked_paths",
    "merge_request_blocked",
    "merge_time",
    "mergeable",
    "need_rebase",
    "not_approved",
    "not_open",
    "preparing",
    "requested_changes",
    "security_policy_pipeline_check",
    "security_policy_violations",
    "status_checks_must_pass",
    "title_regex",
    "unchecked",
]
CONTEXT: schema.Context = {"owner": "group/sub", "repo": "proj", "number": 7}


def merge_request(**changes: object) -> dict[str, object]:
    return {
        "iid": 7,
        "state": "opened",
        "draft": False,
        "sha": "head",
        "merged_at": None,
        "source_branch": "topic",
        "target_branch": "main",
        "detailed_merge_status": "mergeable",
        "has_conflicts": False,
        "web_url": f"https://{HOST}/group/sub/proj/-/merge_requests/7",
        "head_pipeline": pipeline(),
    } | changes


def pipeline(**changes: object) -> dict[str, object]:
    return {
        "id": 50,
        "project_id": 99,
        "sha": "head",
        "ref": "topic",
        "status": "success",
        "web_url": f"https://{HOST}/group/sub/proj/-/pipelines/50",
    } | changes


def job(status: str, name: str = "test", allow_failure: bool = False) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "stage": "test",
        "allow_failure": allow_failure,
        "failure_reason": "script_failure" if status == "failed" else None,
        "web_url": f"https://{HOST}/group/sub/proj/-/jobs/1",
    }


def note(**changes: object) -> dict[str, object]:
    return {
        "body": "fix this",
        "created_at": "2026-01-01T00:00:00Z",
        "author": {"username": "reviewer"},
        "resolvable": True,
        "resolved": False,
        "position": {"new_path": "a.py", "old_path": "a.py", "new_line": 3, "old_line": None},
    } | changes


class Api:
    def __init__(self, objects: Mapping[str, object], lists: Mapping[str, Sequence[object]] | None = None) -> None:
        self.objects, self.lists = dict(objects), dict(lists or {})

    def json(self, argv: list[str]) -> object:
        if argv[:2] == ["glab", "mr"]:
            return self.objects[" ".join(argv)]
        if argv[:4] != ["glab", "api", "--hostname", HOST]:
            raise AssertionError(argv)
        return self.objects[argv[4]]

    def ndjson(self, argv: list[str]) -> list[object]:
        if argv[:4] != ["glab", "api", "--hostname", HOST] or argv[5:] != ["--paginate", "--output", "ndjson"]:
            raise AssertionError(argv)
        return list(self.lists[argv[4]])

    def reader(self) -> gitlab.GitLabReader:
        return gitlab.GitLabReader(HOST, self.json, self.ndjson)


class RemoteTests(unittest.TestCase):
    def test_parses_gitlab_remotes(self) -> None:
        nested = {"owner": "group/sub", "repo": "proj"}
        for value, expected in [
            ("git@gitlab.example.com:group/sub/proj.git\n", (HOST, nested)),
            ("ssh://git@gitlab.example.com:2222/group/sub/proj.git", (HOST, nested)),
            ("https://gitlab.example.com:8443/group/sub/proj", ("gitlab.example.com:8443", nested)),
            ("https://oauth2@gitlab.com/ns/proj.git", ("gitlab.com", {"owner": "ns", "repo": "proj"})),
            ("https://user:secret@gitlab.com/ns/proj.git", None),
            ("https://gitlab.com/ns/proj?x=1", None),
            ("https://gitlab.com/ns/proj#frag", None),
            ("https://gitlab.com/proj", None),
            ("git@gitlab.com:proj.git", None),
            ("http://gitlab.com/ns/proj", None),
            ("https://gitlab.com/ns/proj/-/merge_requests/1", None),
        ]:
            with self.subTest(value=value):
                self.assertEqual(gitlab.parse_gitlab_remote(value), expected)

    def test_current_pr_pins_host_from_web_url(self) -> None:
        url = f"https://{HOST}/group/sub/proj/-/merge_requests/7"
        api = Api({"glab mr view -F json": {"iid": 7, "web_url": url}})
        self.assertEqual(api.reader().current_pr(None), CONTEXT)
        for bad in ("https://other.example.com/group/proj/-/merge_requests/7", f"https://{HOST}/group/proj/-/issues/7"):
            api.objects["glab mr view 7 -F json"] = {"iid": 7, "web_url": bad}
            with self.subTest(url=bad), self.assertRaises(github.QueryError) as caught:
                api.reader().current_pr(7)
            self.assertEqual(caught.exception.failure["kind"], "invalid-context-url")


class MergeRequestTests(unittest.TestCase):
    def facts(self, **changes: object) -> schema.PullRequestFacts:
        return Api({MR: merge_request(**changes)}).reader().pull_request(CONTEXT)

    def test_maps_facts_in_github_key_order(self) -> None:
        facts = self.facts()
        self.assertEqual(list(facts), list(schema.PullRequestFacts.__annotations__))
        self.assertEqual(
            (facts["state"], facts["mergeStateStatus"], facts["mergeable"], facts["headRefOid"]),
            ("OPEN", "CLEAN", "MERGEABLE", "head"),
        )

    def test_maps_status_review_and_conflicts(self) -> None:
        cases: list[tuple[dict[str, object], tuple[str, str, str | None]]] = [
            ({"has_conflicts": True}, ("CLEAN", "CONFLICTING", None)),
            ({"detailed_merge_status": "requested_changes"}, ("BLOCKED", "MERGEABLE", "CHANGES_REQUESTED")),
            ({"detailed_merge_status": "not_approved"}, ("BLOCKED", "MERGEABLE", "REVIEW_REQUIRED")),
            ({"detailed_merge_status": "need_rebase"}, ("BEHIND", "MERGEABLE", None)),
            ({"detailed_merge_status": "conflict"}, ("DIRTY", "CONFLICTING", None)),
            ({"detailed_merge_status": "checking"}, ("UNKNOWN", "UNKNOWN", None)),
        ]
        for changes, expected in cases:
            with self.subTest(changes=changes):
                facts = self.facts(**changes)
                self.assertEqual((facts["mergeStateStatus"], facts["mergeable"], facts["reviewDecision"]), expected)
        self.assertEqual(self.facts(state="locked")["state"], "OPEN")
        self.assertEqual(self.facts(state="merged")["state"], "MERGED")

    def test_documented_merge_statuses_map(self) -> None:
        for status in DOCUMENTED_STATUSES:
            with self.subTest(status=status):
                self.facts(detailed_merge_status=status)

    def test_unknown_values_fail_closed(self) -> None:
        unknowns: list[dict[str, object]] = [
            {"detailed_merge_status": "new_reason"},
            {"state": "archived"},
            {"draft": None},
        ]
        for changes in unknowns:
            with self.subTest(changes=changes), self.assertRaises(github.QueryError) as caught:
                self.facts(**changes)
            self.assertEqual(caught.exception.failure["kind"], "missing-key")

    def test_open_pull_requests_use_iids_and_branches(self) -> None:
        api = Api({}, {PROJECT + "/merge_requests?state=opened&per_page=100": [merge_request()]})
        self.assertEqual(
            api.reader().open_pull_requests(CONTEXT), [{"number": 7, "headRefName": "topic", "baseRefName": "main"}]
        )


class CheckTests(unittest.TestCase):
    def test_maps_job_kinds_from_fork_pipeline_project(self) -> None:
        cases = [
            (job("success"), "passed"),
            (job("skipped"), "skipped"),
            (job("failed"), "failed"),
            (job("failed", allow_failure=True), "skipped"),
            (job("canceled"), "failed"),
            (job("manual"), "failed"),
            (job("manual", allow_failure=True), "skipped"),
            (job("running"), "pending"),
            (job("waiting_for_resource"), "pending"),
        ]
        bridge = job("pending", name="downstream")
        api = Api({MR: merge_request()}, {JOBS: [value for value, _ in cases], BRIDGES: [bridge]})
        result = api.reader().checks(CONTEXT)
        self.assertEqual(result["source"], "gitlab-pipeline")
        self.assertEqual([c["kind"] for c in result["checks"]], [kind for _, kind in cases] + ["pending"])
        self.assertEqual(result["checks"][2]["description"], "script_failure")
        self.assertEqual(result["checks"][2]["reportedState"], "FAILED")

    def test_unusable_pipelines_fail_closed(self) -> None:
        cases: list[tuple[dict[str, object], dict[str, list[object]], str]] = [
            ({MR: merge_request(head_pipeline=None)}, {}, "checks-unavailable"),
            ({MR: merge_request()}, {JOBS: [], BRIDGES: []}, "checks-unavailable"),
            ({MR: merge_request()}, {JOBS: [job("mystery")], BRIDGES: []}, "missing-key"),
        ]
        for objects, lists, kind in cases:
            with self.subTest(kind=kind), self.assertRaises(github.QueryError) as caught:
                Api(objects, lists).reader().checks(CONTEXT)
            self.assertEqual(caught.exception.failure["kind"], kind)

    def test_failed_pipeline_without_jobs_is_a_failed_check(self) -> None:
        head = pipeline(status="failed")
        api = Api({MR: merge_request(head_pipeline=head)}, {JOBS: [], BRIDGES: []})
        self.assertEqual(
            api.reader().checks(CONTEXT)["checks"],
            [
                {
                    "name": "GitLab pipeline",
                    "description": "failed",
                    "link": head["web_url"],
                    "workflow": "",
                    "kind": "failed",
                    "reportedState": "FAILED",
                }
            ],
        )

    def test_merge_gates_add_a_synthetic_check(self) -> None:
        for status, kind in [("merge_time", "failed"), ("status_checks_must_pass", "pending")]:
            api = Api({MR: merge_request(detailed_merge_status=status)}, {JOBS: [job("success")], BRIDGES: []})
            with self.subTest(status=status):
                self.assertEqual(
                    api.reader().checks(CONTEXT)["checks"][-1],
                    {
                        "name": "GitLab merge check",
                        "description": status,
                        "link": merge_request()["web_url"],
                        "workflow": "",
                        "kind": kind,
                        "reportedState": status.upper(),
                    },
                )

    def test_stale_head_pipeline_contributes_no_checks(self) -> None:
        cases: list[tuple[dict[str, object], list[str]]] = [
            (pipeline(sha="old"), []),
            (pipeline(sha="merge-ref", ref=TRAIN), ["base", "other"]),
            (pipeline(sha="merge-ref", ref="refs/merge-requests/8/train"), ["base", "head"]),
        ]
        for head, parents in cases:
            api = Api(
                {MR: merge_request(head_pipeline=head), MERGE_COMMIT: {"parent_ids": parents}},
                {JOBS: [job("success")], BRIDGES: []},
            )
            with self.subTest(head=head, parents=parents), self.assertRaises(github.QueryError) as caught:
                api.reader().checks(CONTEXT)
            self.assertEqual(caught.exception.failure["kind"], "checks-unavailable")
            self.assertIn("not for the current head", caught.exception.failure["detail"])

    def test_commit_rollups_relabel_only_a_current_merge_train_pipeline(self) -> None:
        pipelines: list[object] = [
            {"id": 40, "sha": "head", "status": "success"},
            {"id": 50, "sha": "merge-ref", "status": "failed"},
            {"id": 30, "sha": "old", "status": "skipped"},
            {"id": 20, "sha": "older", "status": "canceling"},
        ]
        head = pipeline(sha="merge-ref", ref=TRAIN)
        for parents, oid in [(["base", "head"], "head"), (["base", "other"], "merge-ref")]:
            api = Api(
                {MR: merge_request(head_pipeline=head), MERGE_COMMIT: {"parent_ids": parents}},
                {PIPELINES: list(pipelines)},
            )
            with self.subTest(parents=parents):
                self.assertEqual(
                    api.reader().commit_rollups(CONTEXT),
                    [
                        {"oid": oid, "state": "FAILURE"},
                        {"oid": "head", "state": "SUCCESS"},
                        {"oid": "old", "state": None},
                        {"oid": "older", "state": "FAILURE"},
                    ],
                )


class ThreadTests(unittest.TestCase):
    def test_only_unresolved_resolvable_discussions_become_threads(self) -> None:
        discussions: list[object] = [
            {"id": "open", "notes": [note(), note(body="reply", position=None)]},
            {"id": "done", "notes": [note(resolved=True)]},
            {"id": "chat", "notes": [note(resolvable=False, resolved=None, position=None)]},
            {"id": "bot", "notes": [note(author={"username": "cursor-bugbot"}, body="RUN_ID: r1", position=None)]},
        ]
        api = Api({}, {MR + "/discussions?per_page=100": discussions})
        threads = api.reader().review_threads(CONTEXT)
        self.assertEqual([t["id"] for t in threads], ["open", "bot"])
        self.assertEqual(
            threads[0]["firstComment"],
            {
                "authorLogin": "reviewer",
                "body": "fix this",
                "path": "a.py",
                "line": 3,
                "createdAt": "2026-01-01T00:00:00Z",
            },
        )
        self.assertEqual((threads[1]["isBugbot"], threads[1]["bugbotReviewPasses"]), (True, 1))


class SnapshotTests(unittest.TestCase):
    def snapshot(
        self, jobs: list[object], objects: Mapping[str, object] | None = None, **changes: object
    ) -> policy.Decision:
        mr = merge_request(**changes)
        api = Api(
            {MR: mr, **(objects or {})},
            {
                JOBS: jobs,
                BRIDGES: [],
                MR + "/discussions?per_page=100": [],
                PIPELINES: [mr["head_pipeline"]],
            },
        )
        return policy.select_stack_decision([policy.read_snapshot(api.reader(), CONTEXT)])

    def assert_failing(self, decision: policy.Decision, names: list[str]) -> None:
        if decision["kind"] != "blocker" or decision["blocker"]["kind"] != "failing-checks":
            self.fail(str(decision))
        self.assertEqual([c["name"] for c in decision["blocker"]["ci"]["failed"]], names)

    def test_ready_and_failing_checks(self) -> None:
        ready = self.snapshot([job("success")])
        self.assertEqual(ready["kind"], "clear")
        self.assert_failing(self.snapshot([job("success"), job("failed", name="lint")]), ["lint"])

    def test_stale_head_pipeline_is_not_ready(self) -> None:
        with self.assertRaises(github.QueryError) as caught:
            self.snapshot([job("success")], head_pipeline=pipeline(sha="old"))
        self.assertEqual(caught.exception.failure["kind"], "checks-unavailable")
        train = pipeline(sha="merge-ref", ref=TRAIN)
        accepted = self.snapshot(
            [job("success")], {MERGE_COMMIT: {"parent_ids": ["base", "head"]}}, head_pipeline=train
        )
        self.assertEqual(accepted["kind"], "clear")

    def test_merge_gates_are_not_ready(self) -> None:
        self.assert_failing(self.snapshot([job("success")], detailed_merge_status="merge_time"), ["GitLab merge check"])
        self.assert_failing(
            self.snapshot([job("success")], detailed_merge_status="locked_paths", head_pipeline=pipeline(sha="old")),
            ["GitLab merge check"],
        )
        waiting = self.snapshot([job("success")], detailed_merge_status="status_checks_must_pass")
        self.assertEqual(waiting["kind"], "waiting")
        self.assertEqual(self.snapshot([job("success")], detailed_merge_status="not_approved")["kind"], "clear")

    def test_required_rebase_is_not_ready(self) -> None:
        self.assert_failing(
            self.snapshot([job("success")], detailed_merge_status="need_rebase"), ["GitLab merge check"]
        )

    def test_ci_gate_holds_when_jobs_do_not_explain_it(self) -> None:
        skipped = self.snapshot(
            [job("skipped")], detailed_merge_status="ci_must_pass", head_pipeline=pipeline(status="skipped")
        )
        self.assert_failing(skipped, ["GitLab merge check"])
        # Failing or pending jobs already explain the gate, so no extra check is added.
        self.assert_failing(self.snapshot([job("failed", name="lint")], detailed_merge_status="ci_must_pass"), ["lint"])
        self.assertEqual(self.snapshot([job("running")], detailed_merge_status="ci_must_pass")["kind"], "waiting")

    def test_pipeline_without_jobs(self) -> None:
        self.assert_failing(self.snapshot([], head_pipeline=pipeline(status="failed")), ["GitLab pipeline"])
        with self.assertRaises(github.QueryError) as caught:
            self.snapshot([], head_pipeline=pipeline(status="running"))
        self.assertEqual(caught.exception.failure["kind"], "checks-unavailable")


class GitLabProcessTests(unittest.TestCase):
    def test_uv_cli_detects_gitlab_origin(self) -> None:
        import os
        import subprocess
        import tempfile

        uv, git = shutil.which("uv"), shutil.which("git")
        if uv is None or git is None:
            raise RuntimeError("Required test executables not found: uv, git")
        with tempfile.TemporaryDirectory(prefix="watcher gitlab ") as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            subprocess.run([git, "init", "-q"], cwd=root, check=True)  # noqa: S603 - Fixed argument vector.
            subprocess.run(  # noqa: S603 - Fixed argument vector.
                [git, "remote", "add", "origin", "git@gitlab.example.com:group/sub/proj.git"], cwd=root, check=True
            )
            glab = bin_dir / "glab"
            glab.write_text(
                f"#!{sys.executable}\n"
                """import json, sys
args=sys.argv[1:]
assert args[:3] == ['api','--hostname','gitlab.example.com'], args
path=args[3]
mr='projects/group%2Fsub%2Fproj/merge_requests/7'
pipeline={'id':50,'project_id':99,'sha':'head','ref':'topic','status':'success'}
values={
 mr: dict(iid=7,state='opened',draft=False,sha='head',merged_at=None,source_branch='topic',target_branch='main',
  detailed_merge_status='mergeable',has_conflicts=False,head_pipeline=pipeline),
 mr+'/discussions?per_page=100': [],
 mr+'/pipelines?per_page=100': [pipeline],
 'projects/99/pipelines/50/jobs?per_page=100': [dict(name='test',status='success',stage='test',allow_failure=False)],
 'projects/99/pipelines/50/bridges?per_page=100': [],
}
value=values[path]
if args[4:] == ['--paginate','--output','ndjson']:
 for item in value: print(json.dumps(item))
else:
 assert len(args) == 4, args
 print(json.dumps(value))
"""
            )
            glab.chmod(0o755)
            env = os.environ | {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}
            env.pop("GITLAB_HOST", None)
            result = subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                [uv, "run", str(DIRECTORY / "watch_pr.py"), "--pr", "7", "--status-only"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(events[-1]["kind"], "STATUS")
            row = events[-1]["rows"][0]
            self.assertEqual(row["context"], CONTEXT)
            self.assertEqual((row["ci"]["source"], row["ci"]["kind"]), ("gitlab-pipeline", "ci-clean"))


if __name__ == "__main__":
    unittest.main()
