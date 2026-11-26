"""Behavior contracts for the papercut helper; every run uses a temporary store, never personal state."""

from __future__ import annotations

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
            [executable("uv"), "run", "--quiet", str(self.link), *args],
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
                [executable("uv"), "run", "--quiet", str(self.link), "record"],
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            )
            for _ in range(8)
        ]
        outputs = [p.communicate(json.dumps(sample(summary=f"Report {i}")))[0] for i, p in enumerate(processes)]
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
        source = HELPER.read_text(encoding="utf-8")
        for module in ("urllib", "http", "socket", "webbrowser", "subprocess", "ssl"):
            self.assertNotRegex(source, rf"^\s*(?:import|from) {module}\b", module)


if __name__ == "__main__":
    unittest.main()
