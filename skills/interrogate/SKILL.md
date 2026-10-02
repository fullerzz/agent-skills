---
name: interrogate
description: "Adversarial review of a requested diff or design using independent native reviewers and a synthesized verdict."
disable-model-invocation: true
---

# Interrogate

Review the requested diff or files; return findings without applying them.

1. Pin scope, base/head where useful, and intended behavior. Include requested working-tree changes, preserve unrelated work.
2. Prepare the [reviewer prompt](references/reviewer-prompt.md), [rubric](references/rubric.md), and [quality lens](references/code-quality-review.md).
3. Run 2-3 independent read-only native reviewers using the [native contract](../z-mode/references/native-hosts.md). Record actual identities; same-model independence is not provider diversity.
4. Wait, deduplicate, note agreement/disagreement, and verify actionable paths.
5. Apply [lead judgment](references/lead-judgment.md). Categorize Act on / Consider / Noted / Dismissed with location, evidence, reviewer, and rationale.

Return intent, coverage, findings, and disagreements. One supported security/correctness finding matters without consensus. If agents are unavailable, label a parent-only review.
