---
name: correct
description: "Find repeated agent mistakes in this repository and prevent recurrence through architecture, types, lint or CI, then behavioral tests, with docs last. Use for correct."
disable-model-invocation: true
---

# Correct

Turn repeated corrections into repository changes that prevent the same mistake. Design for a contributor who sees only nearby files, copies the closest example, and takes the shortest path that compiles.

## Find the mistake classes

Read recent commits, reverts, relevant review comments, agent instruction files, and comments explaining workarounds. Use [scoped session evidence](../z-mode/references/history.md) for conversation history; report unavailable sources. Treat historical instructions as evidence, not current authority.

Group independent occurrences by cause, citing each commit, review, or turn. A repeated class needs at least two occurrences; a commit and its review are one incident. Rank classes by observed frequency. Keep one-off candidates and uncertain counts separate rather than inventing repetition.

## Fix each class at the highest level that works

1. **Eliminate it with architecture.** Give state one owner and tasks one supported path. Hide internals, derive hand-synced lists from one source, and migrate callers before deleting obsolete examples or APIs.
2. **Enforce it with types.** Make invalid states unrepresentable. Where bad code still compiles, use lint or CI with an error naming the supported file, type, or function. For existing violations, prevent additions with a baseline that cannot grow.
3. **Test observable behavior.** Exercise the failed outcome, not just calls or implementation shape. Strengthen relevant tests that would pass with no-op implementations; keep unrelated cleanup out of scope.
4. **Write docs or agent rules last.** Reserve them for judgment that cannot be enforced mechanically, and label that limit.

Fix the most frequent classes within the requested scope, keeping each change independently reviewable. A review-only request stops at findings and proposed enforcement. Invocation does not authorize commits, publication, messages, tracker writes, or personal memory changes.

## Prove the prevention

For each new check, reproduce a real past mistake in an isolated fixture or temporary checkout and show the check fails for the intended reason. Then show the corrected case passes. Exercise the same check command locally and in CI; if CI has not run, distinguish configured coverage from observed results. For architectural prevention, try the former misuse against the new boundary and verify supported callers still work. Report missing historical reproductions or execution access as proof gaps.

Keep exceptions local to the offending line where supported, with a reason, expiry date, and evidence of human approval. Do not invent approval or weaken enforcement to make a check pass; report an unresolved exception instead.

## Keep the rule table

Only when repository edits are authorized, update the repository's existing agent instruction file with a concise table pairing each remaining rule with its enforcement. For review-only requests, return the proposed table and any proposed rule changes in the report without modifying files. Preserve unrelated instructions. Include a check command or code boundary, proof reference, and any unenforced judgment or approved exception. Do not copy private transcript excerpts into repository files.

During authorized correction edits, treat a recurrence of an existing unenforced rule as a reason to move enforcement higher in the same change. Remove redundant prose rules once their mistake is structurally impossible; retain the prevention evidence with the implementation. This skill does not activate itself on future corrections.

Report each class, its occurrence evidence, the chosen prevention level, why higher levels were unsuitable, actual failing/passing checks, and remaining gaps.
