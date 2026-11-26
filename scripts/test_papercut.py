"""Behavior contracts for the papercut helper; every run uses a temporary store, never personal state."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/papercut/scripts/papercut.py"
UUID = "3f2a9c1e-7b4d-4e8a-9f10-2c3d4e5f6a7b"
TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required test executable not found: {name}")
    return path


def uv_run() -> list[str]:
    # The documented invocation: no package index and no interpreter download.
    return [executable("uv"), "run", "--quiet", "--offline", "--no-python-downloads"]


def sample(**changes: object) -> dict[str, object]:
    report: dict[str, object] = {
        "component": "z-mode/playbooks/feature.md",
        "host": "claude-code",
        "kind": "missing-prerequisite",
        "summary": "Feature playbook omits the Codex package check",
        "tried": "Followed the feature playbook after adding a skill.",
        "expected": "The playbook names every required check.",
        "actual": "The Codex package check appears only in AGENTS.md.",
        "blocked": False,
        "workaround": "Ran uv run scripts/package_plugin.py by hand.",
    }
    return {**report, **changes}


class PapercutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="papercut test "))
        self.addCleanup(shutil.rmtree, self.temp)
        self.store = self.temp / "state" / "papercuts"
        self.cwd = self.temp / "elsewhere"
        self.cwd.mkdir()
        # Run through a link from an unrelated cwd, as an installed skill would, with no network credentials.
        self.link = self.temp / "papercut.py"
        self.link.symlink_to(HELPER)
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GH_", "GITHUB_", "XDG_STATE_HOME", "ZSTACK_PAPERCUT"))
        }
        self.env |= {"ZSTACK_PAPERCUT_DIR": str(self.store), "HTTPS_PROXY": "http://127.0.0.1:9", "NO_COLOR": "1"}

    def run_helper(
        self, *args: str, stdin: str = "", env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - Fixed local helper argument vectors; no shell.
            [*uv_run(), str(self.link), *args],
            cwd=self.cwd,
            input=stdin,
            capture_output=True,
            text=True,
            env=env or self.env,
            check=False,
        )

    def record(self, report: dict[str, object]) -> str:
        result = self.run_helper("record", stdin=json.dumps(report))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("saved "), result.stdout)
        return result.stdout.split()[1].rstrip(":")

    def test_record_list_show_export_delete_round_trip(self) -> None:
        report_id = self.record(sample())
        saved = self.store / "reports" / f"{report_id}.json"
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        for directory in (self.store, self.store / "reports"):
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        shown = json.loads(self.run_helper("show", report_id).stdout)
        self.assertEqual(shown["schema"], 1)
        self.assertEqual(shown["capture"], "explicit")
        self.assertIsNone(shown["suspected_fix"])
        self.assertRegex(shown["zstack_version"], r"^0\.\d+\.\d+$")
        self.assertIn(report_id, self.run_helper("list", "--component", "z-mode/playbooks/feature.md").stdout)
        self.assertEqual(self.run_helper("list", "--component", "baton").stdout.strip(), "No papercuts recorded.")

        exported = self.run_helper("export", report_id)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        draft = Path(exported.stdout.strip().partition(": ")[2])
        self.assertEqual(draft, self.store / "drafts" / f"{report_id}.md")
        text = draft.read_text(encoding="utf-8")
        self.assertIn("Suggested title: papercut(z-mode/playbooks/feature.md): Feature playbook omits", text)
        self.assertIn("## Workaround", text)
        self.assertNotIn("## Suspected fix", text)
        self.assertNotEqual(self.run_helper("export", report_id).returncode, 0, "export must not clobber edits")
        self.assertEqual(self.run_helper("export", report_id, "--force").returncode, 0)

        self.assertIn(f"deleted {report_id}", self.run_helper("delete", report_id).stdout)
        self.assertFalse(saved.exists())
        self.assertFalse(draft.exists())
        self.assertNotEqual(self.run_helper("show", report_id).returncode, 0)
        self.assertEqual(list(self.cwd.iterdir()), [])

    def test_concurrent_records_all_survive(self) -> None:
        processes = [
            subprocess.Popen(  # noqa: S603 - Fixed local helper argument vectors; no shell.
                [*uv_run(), str(self.link), "record"],
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            )
            for _ in range(8)
        ]
        # Feed every process before closing any stdin, so all eight reach the empty store together.
        pipes = [process.stdin for process in processes if process.stdin is not None]
        self.assertEqual(len(pipes), len(processes))
        for index, pipe in enumerate(pipes):
            pipe.write(json.dumps(sample(summary=f"Report {index}")))
            pipe.flush()
        for pipe in pipes:
            pipe.close()
        outputs = [process.communicate()[0] for process in processes]
        self.assertTrue(all(p.returncode == 0 for p in processes), outputs)
        ids = {line.split()[1].rstrip(":") for line in outputs}
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(json.loads(self.run_helper("list", "--json").stdout)), 8)
        self.assertEqual(list((self.store / "reports").glob(".tmp-*")), [])

    def test_failed_write_says_not_saved(self) -> None:
        self.store.parent.write_text("a file where the store's parent directory belongs", encoding="utf-8")
        result = self.run_helper("record", stdin=json.dumps(sample()))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("papercut: not saved:", result.stderr)

    def test_rejects_logs_unknown_fields_and_checkout_stores(self) -> None:
        cases = {
            "raw log": sample(actual="\n".join(f"line {i}" for i in range(40))),
            "long field": sample(tried="x" * 1001),
            "unknown field": sample(transcript="everything"),
            "missing field": {k: v for k, v in sample().items() if k != "expected"},
            "bad kind": sample(kind="crash"),
            "not bool": sample(blocked="yes"),
        }
        for name, report in cases.items():
            with self.subTest(name):
                result = self.run_helper("record", stdin=json.dumps(report))
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("not saved", result.stderr)
        self.assertFalse((self.store / "reports").exists() and any((self.store / "reports").iterdir()))
        inside = self.env | {"ZSTACK_PAPERCUT_DIR": str(ROOT / ".agent-work" / "papercuts")}
        result = self.run_helper("record", stdin=json.dumps(sample()), env=inside)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside", result.stderr)
        self.assertFalse((ROOT / ".agent-work" / "papercuts").exists())
        self.assertNotEqual(self.run_helper("show", "../../etc/passwd").returncode, 0)

    def test_export_omits_secrets_paths_urls_and_session_ids(self) -> None:
        home = str(Path.home())
        sensitive = (
            f"{TOKEN} at {home}/work/acme-secret/app.py, session id {UUID}, "
            "https://internal.acme.example/runbook?token=abc, api_key=Zq9xPw7Lm3Kd, dev@acme.example, "
            "nas-box:3035 and 10.0.0.5"
        )
        # A report written straight to the store skips record-time scrubbing, so export must scrub on its own.
        report_id = "20261126T000000Z-0123abcd"
        raw = {"id": report_id, "created": "2026-11-26T00:00:00Z", **sample(), "schema": 1, "capture": "explicit"}
        raw |= {"summary": f"Leak {TOKEN} {UUID}", "actual": sensitive, "suspected_fix": f"See {home}/notes.md"}
        raw["zstack_version"] = "0.32.0"
        (self.store / "reports").mkdir(parents=True)
        (self.store / "reports" / f"{report_id}.json").write_text(json.dumps(raw), encoding="utf-8")
        recorded = self.record(sample(summary=f"Leak {TOKEN} {UUID}", actual=sensitive))
        stored = (self.store / "reports" / f"{recorded}.json").read_text(encoding="utf-8")
        for secret in (TOKEN, "Zq9xPw7Lm3Kd"):
            self.assertNotIn(secret, stored)

        for target in (report_id, recorded):
            result = self.run_helper("export", target)
            self.assertEqual(result.returncode, 0, result.stderr)
            draft = Path(result.stdout.strip().partition(": ")[2]).read_text(encoding="utf-8")
            title = draft.splitlines()[1]
            for leaked in (
                TOKEN,
                UUID,
                home,
                "acme-secret",
                "internal.acme",
                "Zq9xPw7Lm3Kd",
                "dev@acme",
                "nas-box",
                "10.0.0",
            ):
                self.assertNotIn(leaked, draft)
                self.assertNotIn(leaked, title)
            self.assertIn("<redacted>", title)
            self.assertIn("Review this draft before filing", draft)

    def test_saved_reports_keep_local_evidence_and_drafts_keep_zstack_context(self) -> None:
        home = str(Path.home())
        evidence = (
            f"Operation not permitted: '{home}/.claude/plugins/data/zstack-zstack-local/z-mode/tmp97lll8yj' "
            f"from ~/.codex/plugins/cache/zstack-local/zstack/0.31.0/skills/z-mode/SKILL.md, session {UUID}, "
            "nas-box:3035, https://github.com/fullerzz/agent-skills/blob/main/skills/baton/SKILL.md, "
            f"sha 6ffd2f9dd09ea02c86db6364a7c26ea70ef14d42, SKILL.md:12, authorization: steps, /baton pass, {TOKEN}"
        )
        report_id = self.record(sample(actual=evidence))
        saved = json.loads(self.run_helper("show", report_id).stdout)["actual"]
        self.assertEqual(saved, evidence.replace(TOKEN, "<redacted>"), "record removes credentials only")

        result = self.run_helper("export", report_id)
        draft = Path(result.stdout.strip().partition(": ")[2]).read_text(encoding="utf-8")
        for removed in (home, "tmp97lll8yj", ".codex/plugins", UUID, "nas-box", TOKEN):
            self.assertNotIn(removed, draft)
        for kept in (
            "<path>/skills/z-mode/SKILL.md",
            "https://github.com/fullerzz/agent-skills/blob/main/skills/baton/SKILL.md",
            "6ffd2f9dd09ea02c86db6364a7c26ea70ef14d42",
            "SKILL.md:12",
            "authorization: steps",
            "/baton pass",
        ):
            self.assertIn(kept, draft)

    def test_helper_has_no_network_browser_or_subprocess_path(self) -> None:
        imported = set()
        for node in ast.walk(ast.parse(HELPER.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported, "no imports parsed")
        forbidden = {"urllib", "http", "socket", "ssl", "webbrowser", "subprocess", "ftplib", "smtplib", "asyncio"}
        self.assertEqual(imported & forbidden, set())
        self.assertIn("--offline --no-python-downloads", HELPER.read_text(encoding="utf-8").splitlines()[0])

    def test_export_scrubs_review_leaks_without_destroying_references(self) -> None:
        leaks = {
            "Authorization: Basic YWxpY2U6c2FtcGxl": "YWxpY2U6c2FtcGxl",
            "password=hunter": "hunter",
            '{"password": "hunter"}': "hunter",
            "session_id=abcdefghi": "abcdefghi",
            "registry.corp.example:443": "registry.corp",
            "https://[fd00::1]:8443/client-payroll": "client-payroll",
            "/Users/alice/Ze Vault/Payroll.md": "Payroll",
            "\\\\corp\\finance\\ProjectDelta": "ProjectDelta",
            "/opt/acme/skills/unreleased-customer/SKILL.md": "unreleased-customer",
            "'/Users/alice/My Files/q3 plan.md'": "q3 plan",
            "password: hunter2x": "hunter2x",
            'password="correct horse battery"': "horse battery",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": "bPxRfiCY",
        }
        kept = (
            "Error in Dockerfile:12",
            "token: authentication failed",
            "SKILL.md:12",
            "authorization: steps",
            "`/baton pass`",
            "/zstack:papercut",
            "the session ID handling",
            "Basic authentication",
            "a basic README.md check",
            "token SessionStart hook",
            "digest sha256:abc",
            "--token-budget=high",
            "`/baton catch docs/plan.md`",
        )
        leak_lines, kept_lines = list(leaks), list(kept)
        report_id = self.record(
            sample(
                summary="Scrub cases",
                actual="\n".join(leak_lines[:7]),
                suspected_fix="\n".join(leak_lines[7:]),
                tried="\n".join(kept_lines[:7]),
                expected="\n".join(kept_lines[7:]),
            )
        )
        saved = json.loads(self.run_helper("show", report_id).stdout)
        self.assertEqual(saved["tried"] + "\n" + saved["expected"], "\n".join(kept), "record keeps prose evidence")
        for secret in ("YWxpY2U6c2FtcGxl", "hunter", "horse battery"):
            self.assertNotIn(secret, saved["actual"] + saved["suspected_fix"], "record removes credentials")

        draft = Path(self.run_helper("export", report_id).stdout.strip().partition(": ")[2]).read_text(encoding="utf-8")
        for case, secret in leaks.items():
            with self.subTest(leak=case):
                self.assertNotIn(secret, draft)
        for case in kept:
            with self.subTest(kept=case):
                self.assertIn(case, draft)

    def test_forced_export_keeps_the_old_draft_when_the_write_fails(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        report_id = self.record(sample())
        draft = Path(self.run_helper("export", report_id).stdout.strip().partition(": ")[2])
        draft.write_text("my edits", encoding="utf-8")
        draft.parent.chmod(0o500)
        self.addCleanup(draft.parent.chmod, 0o700)
        result = self.run_helper("export", report_id, "--force")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(draft.read_text(encoding="utf-8"), "my edits")
        draft.parent.chmod(0o700)
        self.assertEqual(self.run_helper("export", report_id, "--force").returncode, 0)
        self.assertNotEqual(draft.read_text(encoding="utf-8"), "my edits")

    def test_delete_retry_removes_a_leftover_draft(self) -> None:
        report_id = self.record(sample())
        draft = Path(self.run_helper("export", report_id).stdout.strip().partition(": ")[2])
        (self.store / "reports" / f"{report_id}.json").unlink()
        result = self.run_helper("delete", report_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deleted leftover draft", result.stdout)
        self.assertFalse(draft.exists())
        self.assertNotEqual(self.run_helper("delete", report_id).returncode, 0)

    def test_list_skips_malformed_reports(self) -> None:
        healthy = self.record(sample())
        (self.store / "reports" / "20261126T000000Z-deadbeef.json").write_text('{"schema": 1}', encoding="utf-8")
        result = self.run_helper("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(healthy, result.stdout)
        self.assertIn("skipped 20261126T000000Z-deadbeef.json", result.stderr)
        self.assertNotEqual(self.run_helper("show", "20261126T000000Z-deadbeef").returncode, 0)

    def test_default_store_inside_a_checkout_is_refused(self) -> None:
        checkout = self.temp / "other checkout"
        (checkout / ".git").mkdir(parents=True)
        env = {k: v for k, v in self.env.items() if k != "ZSTACK_PAPERCUT_DIR"}
        env["XDG_STATE_HOME"] = str(checkout / ".state")
        result = self.run_helper("record", stdin=json.dumps(sample()), env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("inside a Git checkout", result.stderr)
        self.assertFalse((checkout / ".state").exists())

    def test_existing_directories_keep_their_mode_and_links_are_refused(self) -> None:
        self.store.mkdir(parents=True, mode=0o755)
        self.store.chmod(0o755)
        self.record(sample())
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.store / "reports").stat().st_mode & 0o777, 0o700)

        elsewhere = self.temp / "elsewhere store"
        elsewhere.mkdir()
        other = self.temp / "linked"
        other.mkdir()
        (other / "reports").symlink_to(elsewhere)
        result = self.run_helper(
            "record", stdin=json.dumps(sample()), env=self.env | {"ZSTACK_PAPERCUT_DIR": str(other)}
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("symbolic link", result.stderr)
        self.assertEqual(list(elsewhere.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
