"""Behavior contracts for the uv helpers; fixtures never touch personal state."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

# Retain the repository's standard-library unittest harness.
# ruff: noqa: PT009, PT027
from unittest.mock import patch

if TYPE_CHECKING:
    from types import ModuleType

TOOLS = Path(__file__).resolve().parents[1] / "skills/z-mode/scripts"


def load(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, TOOLS / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load("orch_store", "orch/store.py")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="orch tests ")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.store = self.module.Store(self.path)
        self.addCleanup(self.store.close)
        self.store.init()

    def test_units_and_existing_tsv(self) -> None:
        s = self.store
        self.assertEqual(s.unit_add("u1", "build")["state"], "pending")
        s.unit_add("=SUM(A1)", "+build")
        updated = s.unit_set("u1", "done", branch="topic", pr=42, sha="abc")
        self.assertEqual(s.unit_get("u1"), updated)
        self.assertEqual(updated["pr"], "42")
        self.assertEqual(s.unit_list(state="done"), [updated])
        self.assertEqual(s.unit_counts(), {"done": 1, "pending": 1})
        self.assertEqual(s.unit_get("=SUM(A1)")["track"], "'+build")
        with self.assertRaises(self.module.UserError):
            s.unit_add("u1", "build")
        with self.assertRaises(self.module.NotFoundError):
            s.unit_get("missing")
        before = (self.path / "units.tsv").read_bytes()
        s.init()
        self.assertEqual((self.path / "units.tsv").read_bytes(), before)

    def test_ledger_is_keyed_by_pr_and_sha(self) -> None:
        s = self.store
        with self.assertRaises(self.module.NotFoundError) as error:
            s.ledger_check(42, "abc")
        self.assertEqual(error.exception.output["verdict"], "NOT-VERIFIED")
        first = s.ledger_record(42, "abc", "unit-test-verified", "proof")
        self.assertEqual(s.ledger_check(42, "abc"), first)
        s.ledger_record(42, "abc", "live-ui-verified", "new proof")
        self.assertEqual(s.ledger_summary(), {"live-ui-verified": 1})
        with self.assertRaises(self.module.NotFoundError):
            s.ledger_check(42, "new-head")
        with self.assertRaises(self.module.UserError):
            s.ledger_record(42, "abc", "looks-good", "proof")

    def test_inbox_and_gates_status(self) -> None:
        s = self.store
        s.inbox_push("worker", "u1", "done", "report")
        s.inbox_push("worker", "u2", "failed")
        self.assertEqual(s.inbox_count(), 2)
        self.assertEqual(len(s.inbox_peek()), 2)
        self.assertEqual(len(s.inbox_drain()), 2)
        self.assertEqual(s.inbox_count(), 0)
        s.gate_park("release", "Ship?", "ship,wait", "wait")
        s.standing_add("Never force push.")
        self.assertEqual(s.status()["changed"], "first render")
        self.assertEqual(s.status()["changed"], "no derived changes")
        s.gate_resolve("release", "ship")
        self.assertEqual(s.status()["changed"], "open gates 1->0")
        self.assertEqual(s.gate_list(), [])
        self.assertEqual(s.standing_show(), [{"number": 1, "line": "Never force push."}])
        self.assertIn("| release | resolved | Ship? |", (self.path / "status.md").read_text())

    def test_lock_read_only_force_and_dead_holder(self) -> None:
        self.store.close()
        lock = self.path / ".orch.lock"
        lock.write_text(str(os.getpid()) + "\n")
        blocked = self.module.Store(self.path)
        self.addCleanup(blocked.close)
        self.assertEqual(blocked.unit_list(), [])
        with self.assertRaisesRegex(self.module.UserError, "lock held"):
            blocked.unit_add("u1", "build")
        forced = self.module.Store(self.path, force=True)
        forced.unit_add("u1", "build")
        forced.close()
        self.assertFalse(lock.exists())
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        lock.write_text(str(child.pid) + "\n")
        recovered = self.module.Store(self.path)
        recovered.unit_add("u2", "build")
        recovered.close()
        self.assertFalse(lock.exists())
        with self.assertRaisesRegex(self.module.UserError, "closed"):
            recovered.unit_list()

    def test_malformed_files_fail_closed(self) -> None:
        cases = [
            ("units.tsv", "wrong\n", self.store.unit_list),
            ("ledger.tsv", "pr\tsha\tverdict\tevidence\tverifier\tts\n1\tx\tbad\tp\tv\tt\n", self.store.ledger_summary),
            ("frontier.json", '{"generation":"1"}', self.store.frontier_show),
            ("gates.md", "# bad", self.store.gate_list),
            ("preferences.md", "3. gap\n", self.store.standing_show),
            ("inbox/bad.tsv", "too\tshort\n", self.store.inbox_peek),
        ]
        for name, contents, operation in cases:
            with self.subTest(name=name):
                (self.path / name).write_text(contents)
                with self.assertRaises(self.module.UserError):
                    operation()

    def test_whitespace_only_standing_file_is_empty(self) -> None:
        (self.path / "preferences.md").write_text(" \n\t\n")
        self.assertEqual(self.store.standing_show(), [])

    def test_cli_json_and_exit_codes(self) -> None:
        self.store.close()

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                [sys.executable, str(TOOLS / "orch/orch.py"), "--store", str(self.path), *args],
                capture_output=True,
                text=True,
            )

        result = run("unit", "add", "u1", "--track", "build", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "pending")
        self.assertEqual(run("unit", "get", "missing").returncode, 2)
        missing = run("--json", "ledger", "check", "42", "abc")
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(json.loads(missing.stdout)["verdict"], "NOT-VERIFIED")
        self.assertEqual(run("unit", "add", "x").returncode, 1)
        self.assertEqual(run("frontier", "set").returncode, 1)


class EntrypointTests(unittest.TestCase):
    def test_uv_launchers_work_from_a_link_in_a_separate_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="helper install ") as temp:
            root = Path(temp)
            target = root / "target repo"
            target.mkdir()
            installed = root / "installed scripts"
            shutil.copytree(TOOLS, installed, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
            for path in ["orch/orch.py", "watch-pr/watch-pr.py"]:
                link = root / Path(path).name
                link.symlink_to(installed / path)
                result = subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                    [shutil.which("uv"), "run", str(link), "--help"], cwd=target, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
            self.assertEqual(list(target.iterdir()), [])


class FrontierTests(unittest.TestCase):
    def test_graphite_frontier_uses_target_repo_and_preserves_on_bad_pin(self) -> None:
        module = load("frontier_store", "orch/store.py")
        with tempfile.TemporaryDirectory(prefix="graphite fixture ") as temp:
            root = Path(temp)
            repo, store_dir, bin_dir = root / "repo", root / "store", root / "bin"
            repo.mkdir()
            bin_dir.mkdir()

            def git(*args: str) -> str:
                return subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                    [shutil.which("git"), "-C", str(repo), *args], capture_output=True, text=True, check=True
                ).stdout.strip()

            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (repo / "note").write_text("baseline")
            git("add", ".")
            git("commit", "-m", "fixture")
            for branch in ("stack/merged", "stack/closed", "stack/open"):
                git("branch", branch)
            script = bin_dir / "gt"
            script.write_text(
                f"#!{sys.executable}\n"
                """import os, sys
from pathlib import Path
assert Path.cwd() == Path(os.environ['EXPECTED_REPO']).resolve()
args=sys.argv[1:]
if args == ['--no-interactive','log','short','--stack','--reverse']:
 print('◯ main\\n◯ stack/merged\\n◯ stack/closed\\n◉ stack/open (current)')
else:
 assert args[:2] == ['--no-interactive','info']
 number,state={'stack/merged':(10,'Merged'),'stack/closed':(13,'Closed'),'stack/open':(11,'Needs approvals')}[args[2]]
 print(f'PR #{number} ({state}) change')
"""
            )
            script.chmod(0o755)
            s = module.Store(store_dir)
            self.addCleanup(s.close)
            with patch.dict(
                os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "EXPECTED_REPO": str(repo)}
            ):
                s.init()
                frontier = s.frontier_set(repo, [10, 13, 11])
                self.assertEqual(frontier["lowestUnmerged"], 11)
                self.assertEqual([r["state"] for r in frontier["prs"]], ["MERGED", "CLOSED", "OPEN"])
                self.assertEqual(frontier["prs"][0]["sha"], git("rev-parse", "stack/merged"))
                before = (store_dir / "frontier.json").read_bytes()
                for pin in ([10, 11, 12], [13, 10, 11], [10, 10]):
                    with self.assertRaises(module.UserError):
                        s.frontier_set(repo, pin)
                    self.assertEqual((store_dir / "frontier.json").read_bytes(), before)
                script.write_text(f'#!{sys.executable}\nprint("bad output")\n')
                with self.assertRaisesRegex(module.UserError, "unparseable"):
                    s.frontier_set(repo)
            s.close()


if __name__ == "__main__":
    unittest.main()
