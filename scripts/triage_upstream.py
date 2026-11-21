"""Route one pinned pstack change for maintainer review."""

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import http.client
import json
import math
import os
import re
import sys
from contextlib import closing

MODEL = "gpt-6-luna"
QUESTION = "port_triage"
LABELS = ("review", "already_covered", "out_of_scope", "needs_context")
METADATA = ("case_id", "upstream_url", "upstream_sha", "downstream_sha")
PR_URL = re.compile(r"https://github\.com/cursor/plugins/pull/[1-9][0-9]*/?(?:\?[^#\s]*)?(?:#[^\s]*)?")
SHA = re.compile(r"[0-9a-fA-F]{40}")
UNEXPECTED_RESPONSE = "unexpected Decisions API response"
INSTRUCTIONS = (
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


class TriageError(Exception):
    """A diagnostic safe to print without request or response data."""


def reject_constant(_: str) -> None:
    raise ValueError("non-JSON number")


def read_case() -> dict[str, str]:
    try:
        case = json.loads(sys.stdin.buffer.read().decode("utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError, RecursionError):
        raise TriageError("input must be one UTF-8 JSON object") from None
    if not isinstance(case, dict):
        raise TriageError("input must be one UTF-8 JSON object")
    fields = {}
    for field in (*METADATA, "evidence"):
        value = case.get(field)
        if not isinstance(value, str) or not value.strip():
            raise TriageError(f"{field} must be a nonempty string")
        fields[field] = value
    if not PR_URL.fullmatch(fields["upstream_url"]):
        raise TriageError("upstream_url must be a public cursor/plugins pull request URL")
    for field in ("upstream_sha", "downstream_sha"):
        if not SHA.fullmatch(fields[field]):
            raise TriageError(f"{field} must be a 40-character hexadecimal Git SHA")
    return fields


def request_decision(evidence: str, key: str) -> object:
    payload = {
        "model": MODEL,
        "input": evidence,
        "questions": [{
            "type": "choice",
            "name": QUESTION,
            "instructions": INSTRUCTIONS,
            "choices": [{"value": label} for label in LABELS],
        }],
    }
    try:
        with closing(http.client.HTTPSConnection("api.openai.com", timeout=30)) as connection:
            connection.request(
                "POST", "/v1/decisions", body=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            with connection.getresponse() as response:
                if not 200 <= response.status < 300:
                    raise TriageError(f"Decisions API returned HTTP {response.status}")
                body = response.read()
    except TimeoutError:
        raise TriageError("Decisions API request timed out") from None
    except (OSError, http.client.HTTPException, ValueError):
        raise TriageError("Decisions API request failed") from None
    try:
        return json.loads(body.decode("utf-8"), parse_constant=reject_constant)
    except (ValueError, RecursionError):
        raise TriageError("Decisions API returned invalid JSON") from None


def choice_probabilities(entries: object) -> dict[str, float]:
    if not isinstance(entries, list) or len(entries) != len(LABELS):
        raise TriageError(UNEXPECTED_RESPONSE)
    probabilities = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise TriageError(UNEXPECTED_RESPONSE)
        label, probability = entry.get("value"), entry.get("probability")
        if label not in LABELS or label in probabilities:
            raise TriageError(UNEXPECTED_RESPONSE)
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise TriageError(UNEXPECTED_RESPONSE)
        probabilities[label] = probability
    # Rounding four probabilities to hundredths can shift their total by up to 0.02.
    if not math.isclose(math.fsum(probabilities.values()), 1.0, abs_tol=0.02 + math.ulp(1.0)):
        raise TriageError(UNEXPECTED_RESPONSE)
    return probabilities


def choice_result(response: object) -> dict[str, object]:
    if not isinstance(response, dict):
        raise TriageError(UNEXPECTED_RESPONSE)
    answers = response.get("answers")
    if not isinstance(answers, list) or len(answers) != 1 or not isinstance(answers[0], dict):
        raise TriageError(UNEXPECTED_RESPONSE)
    answer = answers[0]
    if answer.get("type") == "refusal":
        raise TriageError("Decisions API refused to classify the evidence")
    if answer.get("name") != QUESTION or answer.get("type") != "choice":
        raise TriageError(UNEXPECTED_RESPONSE)

    choice = answer.get("choice")
    confidence = answer.get("confidence")
    model = response.get("model")
    if choice not in LABELS or not isinstance(model, str) or not model.strip():
        raise TriageError(UNEXPECTED_RESPONSE)
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not -math.inf < confidence < math.inf
    ):
        raise TriageError(UNEXPECTED_RESPONSE)
    return {
        "choice": choice,
        "probabilities": choice_probabilities(answer.get("probabilities")),
        "confidence": confidence,
        "model": model,
    }


def main() -> int:
    try:
        case = read_case()
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise TriageError("OPENAI_API_KEY is required")
        result = choice_result(request_decision(case["evidence"], key))
    except TriageError as error:
        print(f"triage_upstream: {error}", file=sys.stderr)
        return 1

    print(json.dumps({key: case[key] for key in METADATA} | result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
