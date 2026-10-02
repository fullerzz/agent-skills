---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
disable-model-invocation: true
---

# How

Explain the named subsystem without writes.

1. Anchor the question in entry points, callers, data structures, and boundaries.
2. Trace a narrow question directly. For broad scope delegate 2-3 independent read-only angles using the [native contract](../z-mode/references/native-hosts.md) and [explorer prompt](references/explorer-prompt.md).
3. Wait for required slices, reconcile contradictions against code, and synthesize with the [explainer prompt](references/explainer-prompt.md). Missing slices remain gaps.
4. Present overview, key concepts, runtime flow, file locations, and gotchas as useful, with file/symbol citations.

Use why for historical motivation; code alone does not establish intent. No changes or publication.
