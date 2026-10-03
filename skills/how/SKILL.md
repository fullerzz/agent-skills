---
name: how
description: "Read-only explanations of how a named code subsystem works: entry points, callers, runtime flow, package ownership, and layering. Use for code walkthroughs and architecture questions. Use why for historical design rationale; do not select for implementation or debugging requests."
disable-model-invocation: true
---

# How

Explain the named subsystem without writes.

1. Anchor the question in entry points, callers, data structures, and boundaries.
2. Trace a narrow question directly. For broad scope delegate 2-3 independent read-only angles using the [native contract](../z-mode/references/native-hosts.md) and [explorer prompt](references/explorer-prompt.md).
3. Wait for required slices, reconcile contradictions against code, and synthesize with the [explainer prompt](references/explainer-prompt.md). Missing slices remain gaps.
4. Present overview, key concepts, runtime flow, file locations, and gotchas as useful, with file/symbol citations.

Use why for historical motivation; code alone does not establish intent. No changes or publication.
