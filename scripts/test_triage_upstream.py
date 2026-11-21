"""Exercise the upstream triage CLI with a stubbed HTTPS connection."""

import io
import json
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("triage_upstream.py")
KEY = "test-key-kept-out-of-diagnostics"
EVIDENCE = '  TLC prints "résultat".\r\nThe parser uses .split("\\n").\n'
EXPECTED_RUBRIC = (
    "How should this specific pstack change be routed for the pinned zstack revision? "
    "Use only the supplied evidence. Select exactly one label.\n\n"
    "review — The change addresses a concrete gap in zstack's existing behavior or stated scope and warrants "
    "deeper review.\n"
    "already_covered — zstack already enforces the same rule or provides equivalent behavior.\n"
    "out_of_scope — The change depends on an upstream feature or design that zstack explicitly excludes or replaces "
    "with a different workflow.\n"
    "needs_context — A missing fact about requirements, support policy, or current behavior could change the routing "
    "decision.\n\n"
    "Evaluate only the change described in the input, even if its upstream PR contains other changes."
)
CASE = {
    "case_id": "tlc-crlf",
    "upstream_url": "https://github.com/cursor/plugins/pull/1292",
    "upstream_sha": "0b46ec399d55f2829e88822998f53b84944837d3",
    "downstream_sha": "6e4b100d33b3604f0a002c8b41edb31984c4e342",
    "evidence": EVIDENCE,
}
CASE_JSON = json.dumps(CASE, ensure_ascii=False).encode("utf-8")
PROBABILITIES = [
    {"value": "needs_context", "probability": 0.65},
    {"value": "review", "probability": 0.25},
    {"value": "already_covered", "probability": 0.06},
    {"value": "out_of_scope", "probability": 0.04},
]
ANSWER = {
    "type": "choice",
    "name": "port_triage",
    "choice": "needs_context",
    "confidence": 0.64,
    "probabilities": PROBABILITIES,
}
MODEL = "gpt-6-luna-test-snapshot"
RAW_ERROR = f"private response body with {KEY} and evidence: {EVIDENCE}"


class TriageUpstreamTests(unittest.TestCase):
    def setUp(self) -> None:
        https = patch("http.client.HTTPSConnection")
        self.https = https.start()
        self.addCleanup(https.stop)
        self.connection = self.https.return_value
        self.response = self.connection.getresponse.return_value.__enter__.return_value
        self.response.status = 200
        self.respond([ANSWER])

    def respond(self, answers: object) -> None:
        self.response.read.return_value = json.dumps({"model": MODEL, "answers": answers}).encode()

    def run_cli(self, stdin: bytes = CASE_JSON, *, key: str = KEY) -> tuple[object, str, str]:
        env = {"OPENAI_API_KEY": key} if key else {}
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            io.TextIOWrapper(io.BytesIO(stdin), encoding="ascii") as stream,
            patch.dict("os.environ", env, clear=True),
            patch("sys.stdin", stream),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
            self.assertRaises(SystemExit) as stopped,
        ):
            # Use the same __main__ path as `uv run scripts/triage_upstream.py`.
            runpy.run_path(str(SCRIPT), run_name="__main__")
        return stopped.exception.code, stdout.getvalue(), stderr.getvalue()

    def assert_failure(self, result: tuple[object, str, str], reason: str) -> None:
        code, stdout, stderr = result
        self.assertNotIn(code, (0, None))
        self.assertEqual(stdout, "")
        self.assertIn(reason, stderr)
        for private in (KEY, "TLC prints", "private response body"):
            self.assertNotIn(private, stderr)

    def test_sends_only_evidence_and_records_the_named_choice(self) -> None:
        code, stdout, stderr = self.run_cli()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(len(stdout.splitlines()), 1)
        self.assertEqual(json.loads(stdout), {
            "case_id": "tlc-crlf",
            "upstream_url": "https://github.com/cursor/plugins/pull/1292",
            "upstream_sha": "0b46ec399d55f2829e88822998f53b84944837d3",
            "downstream_sha": "6e4b100d33b3604f0a002c8b41edb31984c4e342",
            "choice": "needs_context",
            "probabilities": {"review": 0.25, "already_covered": 0.06, "out_of_scope": 0.04, "needs_context": 0.65},
            "confidence": 0.64,
            "model": MODEL,
        })
        self.assertEqual(self.https.call_count, 1)
        self.assertEqual(self.https.call_args.args, ("api.openai.com",))
        self.assertGreater(self.https.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(self.https.call_args.kwargs["timeout"], 60)
        self.assertEqual(self.connection.request.call_count, 1)
        request = self.connection.request.call_args
        self.assertEqual(request.args, ("POST", "/v1/decisions"))
        self.assertEqual(request.kwargs["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(request.kwargs["headers"]["Content-Type"], "application/json")
        payload = json.loads(request.kwargs["body"])
        self.assertEqual(set(payload), {"model", "input", "questions"})
        self.assertEqual(payload["model"], "gpt-6-luna")
        self.assertEqual(payload["input"], EVIDENCE)
        question, = payload["questions"]
        self.assertEqual(question["name"], "port_triage")
        self.assertEqual(question["type"], "choice")
        self.assertEqual(question["instructions"], EXPECTED_RUBRIC)
        self.assertEqual(question["choices"], [
            {"value": "review"}, {"value": "already_covered"},
            {"value": "out_of_scope"}, {"value": "needs_context"},
        ])

    def test_rejects_invalid_input_before_connecting(self) -> None:
        for data in (b"{", b'"\xff"', b"[]", b"{} {}", b'{"extra": NaN}'):
            with self.subTest(data=data):
                self.assert_failure(self.run_cli(data), "input")
        for field, invalid in (
            ("case_id", " "), ("evidence", []), ("upstream_url", "https://github.com/cursor/plugins/issues/1292"),
            ("upstream_url", "https://github.com@other.invalid/cursor/plugins/pull/1292"),
            ("upstream_sha", "0b46ec3"), ("downstream_sha", "z" * 40),
        ):
            with self.subTest(field=field, invalid=invalid):
                self.assert_failure(self.run_cli(json.dumps(CASE | {field: invalid}).encode()), field)
        self.https.assert_not_called()

    def test_rejects_missing_key_before_connecting(self) -> None:
        self.assert_failure(self.run_cli(key=""), "OPENAI_API_KEY")
        self.https.assert_not_called()

    def test_refusal_leaves_no_success_record(self) -> None:
        self.respond([{"type": "refusal", "name": "port_triage", "detail": RAW_ERROR}])
        self.assert_failure(self.run_cli(), "refused")

    def test_rejects_unexpected_answers(self) -> None:
        for answers in (
            [], [ANSWER, ANSWER], [ANSWER | {"name": RAW_ERROR}], [ANSWER | {"type": "predicate"}],
            [ANSWER | {"choice": []}], [ANSWER | {"confidence": None}], [ANSWER | {"confidence": True}],
        ):
            with self.subTest(answers=answers):
                self.respond(answers)
                self.assert_failure(self.run_cli(), "unexpected")

    def test_rejects_incomplete_or_invalid_probabilities(self) -> None:
        for value, probability in (
            ("review", 0.04), ("unknown", 0.04), ("out_of_scope", -0.01), ("out_of_scope", 1.01),
            ("out_of_scope", float("inf")), ("out_of_scope", float("nan")),
        ):
            with self.subTest(value=value, probability=probability):
                entry = {"value": value, "probability": probability}
                self.respond([ANSWER | {"probabilities": [*PROBABILITIES[:-1], entry]}])
                self.assert_failure(self.run_cli(), "Decisions API")
        self.respond([ANSWER | {"probabilities": PROBABILITIES[:-1]}])
        self.assert_failure(self.run_cli(), "unexpected")
        boolean_entries = [entry | {"probability": entry["value"] == "needs_context"} for entry in PROBABILITIES]
        self.respond([ANSWER | {"probabilities": boolean_entries}])
        self.assert_failure(self.run_cli(), "unexpected")

    def test_rejects_invalid_probability_totals(self) -> None:
        for values in ((0, 0, 0, 0), (0.65, 0.25, 0.06, 0.01), (0.65, 0.25, 0.06, 0.07)):
            with self.subTest(values=values):
                entries = [entry | {"probability": value} for entry, value in zip(PROBABILITIES, values, strict=True)]
                self.respond([ANSWER | {"probabilities": entries}])
                self.assert_failure(self.run_cli(), "unexpected Decisions API response")

    def test_accepts_probability_totals_within_rounding_tolerance(self) -> None:
        for probability in (0.02, 0.06):
            with self.subTest(probability=probability):
                entries = [*PROBABILITIES[:-1], PROBABILITIES[-1] | {"probability": probability}]
                self.respond([ANSWER | {"probabilities": entries}])
                code, stdout, stderr = self.run_cli()
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.assertEqual(json.loads(stdout)["probabilities"]["out_of_scope"], probability)

    def test_rejects_an_unreadable_response(self) -> None:
        self.response.read.return_value = RAW_ERROR.encode()
        self.assert_failure(self.run_cli(), "invalid JSON")

    def test_http_error_omits_response_body(self) -> None:
        self.response.status = 401
        self.response.read.return_value = RAW_ERROR.encode()
        self.assert_failure(self.run_cli(), "HTTP 401")
        self.response.read.assert_not_called()

    def test_redirect_is_an_error_without_another_request(self) -> None:
        self.response.status = 307
        self.response.getheader.return_value = "https://elsewhere.invalid"
        self.assert_failure(self.run_cli(), "HTTP 307")
        self.assertEqual(self.https.call_count, 1)
        self.assertEqual(self.connection.request.call_count, 1)

    def test_timeout_is_reported_without_retrying_or_leaking_details(self) -> None:
        self.connection.getresponse.side_effect = TimeoutError(RAW_ERROR)
        self.assert_failure(self.run_cli(), "timed out")
        self.assertEqual(self.connection.request.call_count, 1)
