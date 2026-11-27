"""Behavior contracts for the papercut helper; every run uses a temporary store, never personal state."""

from __future__ import annotations

import ast
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


SCANNERS = [name for name in ("betterleaks", "gitleaks") if shutil.which(name)]
# A stand-in scanner that records how it was called. FAKE_SCANNER_MODE picks its answer.
FAKE_SCANNER = """#!/usr/bin/env python3
import json, os, sys
text = sys.stdin.read()
with open(os.environ["FAKE_SCANNER_LOG"], "a") as log:
    settings = sorted(key for key in os.environ if key.startswith(("GITLEAKS_", "BETTERLEAKS_")))
    log.write(json.dumps({"argv": sys.argv[1:], "settings": settings}) + "\\n")
mode = os.environ.get("FAKE_SCANNER_MODE", "clean")
if mode == "fail":
    sys.stderr.write("scanner exploded\\n")
    sys.exit(3)
if mode == "garbage":
    print("not json")
elif mode == "blank":
    print(json.dumps([{"RuleID": "fake", "Secret": ""}]))
elif mode == "encoded":
    # A decoded finding: its Secret is not in the scanned text, so it cannot be removed literally.
    print(json.dumps([{"RuleID": "fake", "Secret": "decoded-value-not-in-text"}]))
elif mode == "silent":
    pass
elif mode == "title" and "Suggested title" in text:
    print(json.dumps([{"RuleID": "fake", "Secret": "Suggested title"}]))
else:
    print("[]")
"""


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
        self.base_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GH_", "GITHUB_", "XDG_STATE_HOME", "ZSTACK_PAPERCUT"))
        }
        self.base_env |= {"ZSTACK_PAPERCUT_DIR": str(self.store), "HTTPS_PROXY": "http://127.0.0.1:9", "NO_COLOR": "1"}
        # Storage and CLI contracts run against the stand-in scanner; detection tests ask for a real one.
        self.env, _ = self.fake_scanner("clean")

    def real_scanner(self) -> dict[str, str]:
        if not SCANNERS:
            self.skipTest("needs betterleaks or gitleaks on PATH")
        return self.only_scanner(SCANNERS[0])

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
        # communicate() would flush the closed stdin and raise on Python 3.12.
        outputs = []
        for process in processes:
            with process:
                outputs.append(process.stdout.read() if process.stdout else "")
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
        self.env = self.real_scanner()
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
        self.assertNotIn(TOKEN, stored, "record removes credentials the scanner finds")

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
        self.env = self.real_scanner()
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
            "/baton pass",
            "authorization: <redacted>",
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
        forbidden = {"urllib", "http", "socket", "ssl", "webbrowser", "ftplib", "smtplib", "asyncio"}
        self.assertEqual(imported & forbidden, set())
        self.assertIn("--offline --no-python-downloads", HELPER.read_text(encoding="utf-8").splitlines()[0])

    def test_record_keeps_evidence_and_export_removes_review_leaks(self) -> None:
        if not SCANNERS:
            self.skipTest("needs betterleaks or gitleaks on PATH")
        # Probes from three cross-harness reviews, each mapped to text that must not reach the draft.
        leaks = {
            "Authorization: Basic YWxpY2U6c2FtcGxl": "YWxpY2U6c2FtcGxl",
            "Authorization: Basic YTpi": "YTpi",
            'Authorization: Digest username="bob", response="6629fae49393a05397450978507c4ef1"': "6629fae4",
            "Authorization: ApiKey example-key": "example-key",
            'curl -H "Authorization: Bearer SAMPLEabc123" returned exit 22': "SAMPLEabc123",
            'headers={"Authorization": "Basic QWxhZGRpbjpvcGVu"}, retry': "QWxhZGRpbjpvcGVu",
            '{"Cookie": "session=\\"sample-session-value\\"; sid=another-private-session"}': "another-private",
            '{"Authorization": "Digest username=\\"bob\\", response=\\"escaped-digest-value\\""}': "escaped-digest",
            "password=hunter": "hunter",
            '{"password": "hunter"}': "hunter",
            "password: staple battery horse": "battery horse",
            'password="correct horse battery"': "horse battery",
            'password="<payroll2026!"': "payroll2026",
            '{"password":"use\\"VeryPrivateTail"}': "VeryPrivateTail",
            "token=abcdefghijklmnop": "abcdefghijklmnop",
            "uv publish --token simple-example-key": "simple-example-key",
            "session_id=abcdefghi": "abcdefghi",
            '{"session_id":"abcdefghijkl"}': "abcdefghijkl",
            "session id alpha-bravo-charlie expired": "alpha-bravo",
            "registry.corp.example:443": "registry.corp",
            "buildbox:22 and BUILD-SERVER:8443": "BUILD-SERVER",
            "10-42-0-3.build.svc:8080 and buildbox:7": "build.svc",
            "[2001:4860:4860:0:0:0:0:8888]:443": "4860",
            "https://[fd00::1]:8443/client-payroll": "client-payroll",
            f"https://{TOKEN}@build.private.corp/internal": "build.private",
            "https://github.com/fullerzz/agent-skills#access_token=sample-only-value": "sample-only",
            "GET https://wiki.private.example/pages/Setup_(Payroll)/client-plan.md returned 404": "client-plan",
            "git@code.corp.example:finance/payroll.git": "payroll.git",
            "//registry.corp.example/payroll/": "registry.corp",
            "/Users/alice/Ze Vault/Payroll.md": "Vault",
            "/Users/alice/Top Secret Project/Payroll.md": "Secret Project",
            "/Users/alice/Documents/Team/Client (Payroll)/report.txt not found": "Client",
            "/Applications/project financial records/private.md was missing": "financial",
            "C:/Users/alice/finance/report.json": "finance",
            "\\\\corp\\Finance Team\\Payroll.xlsx": "Finance",
            "/opt/acme/skills/baton/customer-payroll/private.md": "customer-payroll",
            "'/Users/alice/My Files/q3 plan.md'": "q3 plan",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": "bPxRfiCY",
        }
        draft_kept = (
            "Error in Dockerfile:12 and SKILL.md:12",
            "`/baton pass` and /zstack:papercut",
            "the session ID handling",
            "Basic authentication",
            "a basic README.md check",
            "token SessionStart hook",
            "at 12:30:45, version 0.31.0",
            "sha 6ffd2f9dd09ea02c86db6364a7c26ea70ef14d42",
            "https://github.com/fullerzz/agent-skills/blob/6ffd2f9dd09ea02c86db6364a7c26ea70ef14d42/skills/baton/SKILL.md",
            "skills/z-mode/SKILL.md and z-mode/playbooks/feature.md",
        )
        # Export may redact these, but the saved report must keep them exactly.
        record_kept = (
            "token: authentication failed",
            "a basic NullPointerException in Passwordless=true",
            "--token-budget=high and digest sha256:abc",
            "step 1, authorization: steps, then /baton pass failed",
            "cookie: none set yet",
            "unsupported SSH key type sk-ecdsa-sha2-nistp256@openssh.com",
            'parse failed: missing "-----BEGIN PRIVATE KEY-----" marker in input',
            "GET https://svc.example?ref=alice@team failed",
        )
        lines = list(leaks)
        # Text fields hold 12 lines each, so the leaks past 36 share the tried field with the kept text.
        fields = {"actual": lines[:12], "suspected_fix": lines[12:24], "workaround": lines[24:36]}
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner):
                env = self.only_scanner(scanner)
                report = sample(
                    summary="Title buildbox:22 token=abcdefghijklmnop",
                    tried="\n".join((*draft_kept, *lines[36:])),
                    expected="\n".join(record_kept),
                    **{key: "\n".join(value) for key, value in fields.items()},
                )
                result = self.run_helper("record", stdin=json.dumps(report), env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                report_id = result.stdout.split()[1].rstrip(":")
                saved = json.loads(self.run_helper("show", report_id, env=env).stdout)
                self.assertTrue(saved["tried"].startswith("\n".join(draft_kept)), saved["tried"])
                self.assertEqual(saved["expected"], "\n".join(record_kept), "record keeps non-credential evidence")
                stored = json.dumps(saved)
                record_removed = ("YWxpY2U6c2FtcGxl", "YTpi", "6629fae4", "QWxhZGRpbjpvcGVu", "SAMPLEabc123", TOKEN)
                for credential in (*record_removed, "sample-session", "another-private", "escaped-digest"):
                    self.assertNotIn(credential, stored, "record removes header values and scanned secrets")
                self.assertIn("exit 22", stored, "a shell-quoted header keeps the rest of its line")

                exported = self.run_helper("export", report_id, env=env)
                self.assertEqual(exported.returncode, 0, exported.stderr)
                draft = Path(exported.stdout.strip().partition(": ")[2]).read_text(encoding="utf-8")
                title = draft.splitlines()[1]
                for secret in ("buildbox", "abcdefghijklmnop"):
                    self.assertNotIn(secret, title)
                for case, secret in leaks.items():
                    with self.subTest(scanner=scanner, leak=case):
                        self.assertNotIn(secret, draft)
                for case in draft_kept:
                    with self.subTest(scanner=scanner, kept=case):
                        self.assertIn(case, draft)

    def only_scanner(self, name: str) -> dict[str, str]:
        """An environment whose PATH offers exactly one scanner, so each adapter path is exercised."""
        directory = self.temp / f"bin-{name}"
        directory.mkdir(exist_ok=True)
        link = directory / name
        if not link.exists():
            link.symlink_to(executable(name))
        return self.base_env | {"PATH": f"{directory}{os.pathsep}/usr/bin{os.pathsep}/bin"}

    def fake_scanner(self, mode: str) -> tuple[dict[str, str], Path]:
        directory = self.temp / "bin-fake"
        directory.mkdir(exist_ok=True)
        script = directory / "betterleaks"
        script.write_text(FAKE_SCANNER, encoding="utf-8")
        script.chmod(0o755)
        log = self.temp / "fake-scanner.log"
        env = self.base_env | {"PATH": f"{directory}{os.pathsep}/usr/bin{os.pathsep}/bin"}
        # Scanner settings in the environment could swap the rules or turn on live validation; none may reach it.
        settings = {"BETTERLEAKS_VALIDATE": "true", "GITLEAKS_CONFIG": "/nowhere.toml", "BETTERLEAKS_CONFIG_TOML": "x"}
        return env | settings | {"FAKE_SCANNER_MODE": mode, "FAKE_SCANNER_LOG": str(log)}, log

    def test_scanner_contract_and_failures(self) -> None:
        env, log = self.fake_scanner("clean")
        log.unlink(missing_ok=True)
        result = self.run_helper("record", stdin=json.dumps(sample()), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(calls)
        for call in calls:
            self.assertEqual(call["argv"][0], "stdin")
            self.assertIn("--ignore-gitleaks-allow", call["argv"])
            depth = call["argv"].index("--max-decode-depth") + 1
            self.assertGreater(int(call["argv"][depth]), 0, "decoding must not depend on the scanner's default")
            self.assertFalse(any("valid" in arg for arg in call["argv"]), call["argv"])
            self.assertEqual(call["settings"], [], "scanner settings must not reach the scanner")
        report_id = result.stdout.split()[1].rstrip(":")

        # The finished draft gets its own scan; a finding there stops the export before anything is written.
        env, _ = self.fake_scanner("title")
        blocked = self.run_helper("export", report_id, env=env)
        self.assertEqual(blocked.returncode, 2, blocked.stdout)
        self.assertIn("not written", blocked.stderr)
        self.assertFalse((self.store / "drafts" / f"{report_id}.md").exists())

        for mode in ("fail", "garbage", "silent", "blank", "encoded"):
            with self.subTest(mode=mode):
                env, _ = self.fake_scanner(mode)
                result = self.run_helper("record", stdin=json.dumps(sample()), env=env)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("not saved: ", result.stderr)
                expected = "could not be removed" if mode == "encoded" else "secret scan"
                self.assertIn(expected, result.stderr)
        missing = self.env | {"PATH": f"/usr/bin{os.pathsep}/bin"}
        result = self.run_helper("record", stdin=json.dumps(sample()), env=missing)
        self.assertEqual(result.returncode, 2)
        self.assertIn("needs a secret scanner", result.stderr)
        self.assertEqual(len(list((self.store / "reports").glob("*.json"))), 1)

    def test_real_scanners_keep_default_rules_and_refuse_encoded_secrets(self) -> None:
        if not SCANNERS:
            self.skipTest("needs betterleaks or gitleaks on PATH")
        encoded = base64.b64encode(f"token {TOKEN}".encode()).decode()
        no_rules = '[[rules]]\nid = "nothing"\nregex = "zzqqzzqq"\n'
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner):
                env = self.only_scanner(scanner) | {
                    "GITLEAKS_CONFIG_TOML": no_rules,
                    "BETTERLEAKS_CONFIG_TOML": no_rules,
                }
                report_id = self.record_with(env, sample(actual=f"Leaked {TOKEN} in output."))
                self.assertNotIn(TOKEN, (self.store / "reports" / f"{report_id}.json").read_text(encoding="utf-8"))
                result = self.run_helper("record", stdin=json.dumps(sample(actual=f"blob {encoded} end")), env=env)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("could not be removed", result.stderr)

    def record_with(self, env: dict[str, str], report: dict[str, object]) -> str:
        result = self.run_helper("record", stdin=json.dumps(report), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split()[1].rstrip(":")

    def test_export_redacts_inside_angle_brackets(self) -> None:
        private = "<https://wiki.private.example/payroll> and <dev@acme.example> and <build.corp.example:8443>"
        kept = "<https://github.com/fullerzz/agent-skills> and <component>"
        nested = "<" * 999  # One word per bracket layer must not exhaust the stack.
        report = sample(summary="See <https://wiki.private.example/x>", actual=f"{private}\n{kept}", workaround=nested)
        report_id = self.record(report)
        result = self.run_helper("export", report_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = Path(result.stdout.strip().partition(": ")[2]).read_text(encoding="utf-8")
        for leaked in ("wiki.private", "dev@acme", "build.corp"):
            self.assertNotIn(leaked, draft)
        self.assertIn(kept, draft)

    def test_export_output_cannot_overwrite_a_report(self) -> None:
        report_id = self.record(sample())
        report = self.store / "reports" / f"{report_id}.json"
        before = report.read_text(encoding="utf-8")
        result = self.run_helper("export", report_id, "--force", "--output", str(report))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(report.read_text(encoding="utf-8"), before)

    def test_list_fails_when_the_store_cannot_be_read(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        self.record(sample())
        reports = self.store / "reports"
        reports.chmod(0o000)
        self.addCleanup(reports.chmod, 0o700)
        result = self.run_helper("list", "--json")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("[]", result.stdout)

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
        reports = self.store / "reports"
        (reports / "20261126T000000Z-deadbeef.json").write_text('{"schema": 1}', encoding="utf-8")
        loose = json.loads((reports / f"{healthy}.json").read_text(encoding="utf-8"))
        loose |= {"id": "20261126T000000Z-feedface", "schema": True, "workaround": {"private": "corrupt"}}
        del loose["capture"]
        (reports / "20261126T000000Z-feedface.json").write_text(json.dumps(loose), encoding="utf-8")
        split = json.loads((reports / f"{healthy}.json").read_text(encoding="utf-8"))
        split |= {"id": "20261126T000000Z-0badc0de", "summary": "first\nsecond"}
        (reports / "20261126T000000Z-0badc0de.json").write_text(json.dumps(split), encoding="utf-8")
        result = self.run_helper("list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["id"] for r in json.loads(result.stdout)], [healthy])
        for bad in ("deadbeef", "feedface", "0badc0de"):
            self.assertIn(f"skipped 20261126T000000Z-{bad}.json", result.stderr)
            self.assertNotEqual(self.run_helper("show", f"20261126T000000Z-{bad}").returncode, 0)

    @unittest.skipIf(sys.platform == "win32", "uses POSIX flock")
    def test_export_waits_for_the_store_lock(self) -> None:
        import fcntl

        report_id = self.record(sample())
        with (self.store / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with subprocess.Popen(  # noqa: S603 - Fixed local helper argument vectors; no shell.
                [*uv_run(), str(self.link), "export", report_id],
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            ) as process:
                time.sleep(2)
                self.assertIsNone(process.poll(), "export ran while another command held the lock")
                self.assertFalse((self.store / "drafts" / f"{report_id}.md").exists())
                fcntl.flock(lock, fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn(f"exported {report_id}", stdout)

    def test_delete_continues_past_a_missing_id(self) -> None:
        first, second = self.record(sample()), self.record(sample())
        self.assertEqual(self.run_helper("delete", first).returncode, 0)
        result = self.run_helper("delete", first, second)
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"no papercut {first}", result.stderr)
        self.assertIn(f"deleted {second}", result.stdout)
        self.assertFalse((self.store / "reports" / f"{second}.json").exists())

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
        report_id = self.record(sample())
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.store / "reports").stat().st_mode & 0o777, 0o700)

        # A linked drafts/ must not let delete or export reach the file it points at.
        outside = self.temp / "outside drafts"
        outside.mkdir()
        victim = outside / f"{report_id}.md"
        victim.write_text("not the store's", encoding="utf-8")
        (self.store / "drafts").symlink_to(outside)
        for args in (("delete", report_id), ("export", report_id)):
            with self.subTest(args=args):
                result = self.run_helper(*args)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("symbolic link", result.stderr)
        self.assertEqual(victim.read_text(encoding="utf-8"), "not the store's")
        self.assertTrue((self.store / "reports" / f"{report_id}.json").exists())

        # A linked reports/ is refused for writes and reads alike.
        elsewhere = self.temp / "elsewhere store"
        elsewhere.mkdir()
        other = self.temp / "linked"
        other.mkdir()
        (other / "reports").symlink_to(elsewhere)
        env = self.env | {"ZSTACK_PAPERCUT_DIR": str(other)}
        commands: list[tuple[tuple[str, ...], str]] = [
            (("record",), json.dumps(sample())),
            (("list",), ""),
            (("show", report_id), ""),
        ]
        drafts_only = self.temp / "drafts link store"
        (drafts_only / "drafts").parent.mkdir()
        (drafts_only / "drafts").symlink_to(outside)
        refused = self.run_helper(
            "record", stdin=json.dumps(sample()), env=self.env | {"ZSTACK_PAPERCUT_DIR": str(drafts_only)}
        )
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertFalse((drafts_only / "reports").exists())
        for command, stdin in commands:
            with self.subTest(command=command):
                result = self.run_helper(*command, stdin=stdin, env=env)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("symbolic link", result.stderr)
        self.assertEqual(list(elsewhere.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
