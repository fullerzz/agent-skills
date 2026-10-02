---
name: why
description: "Use for 'why does X work this way', 'why we picked Y', design rationale, regressions, postmortems, or data-backed thresholds. Discovers available MCPs and queries each evidence category (source control, issue tracker, long-form docs, real-time chat, infrastructure observability, error tracking, product analytics warehouse) in parallel, then returns a cited read on decisions and tradeoffs. Use how for runtime behavior."
disable-model-invocation: true
---

# Why

Investigate the forces that shaped code. Read [epistemics](references/epistemics.md) and separate direct evidence, supported conclusions, inference, speculation, and unknowns.

1. Anchor files and symbols with blame, history through renames, substantive commits, and relevant PR discussion.
2. Map available sources to [categories](references/source-playbook.md). Search only the relevant workspace/topic/time window. Start with Git and available PR history, then relevant tickets, docs, chat, observability, errors, or analytics. Do not assume gh auth or every connector exists.
3. Broad independent sources can be delegated using the [native contract](../z-mode/references/native-hosts.md) and [investigator prompt](references/investigator-prompt.md). Give each the relevant category playbook; defensive code may need incident-postmortem. Narrow questions run directly.
4. Reconcile with the [synthesizer prompt](references/synthesizer-prompt.md). Spot-check citations, keep contradictions, and report unavailable/unsearched categories.

Return documented facts, inferences, competing hypotheses when useful, gaps, and actual sources. Before a change derive Preserve / Change / Avoid / Risk constraints. Research does not authorize contacting people or editing records.
