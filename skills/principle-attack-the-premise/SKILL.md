---
name: principle-attack-the-premise
description: "Apply when two or more fixes sharing a premise fail the same gate. Write down and directly test that premise before another fix assumes it."
disable-model-invocation: true
---

# Attack the Premise

When two or more fixes that share one premise have failed the same gate, suspect the premise, not the fixes.

**Why:** Each failure under a shared premise is evidence about the premise.

**Pattern:**
- **Write the premise down.** The premise is the one sentence that every failed fix assumed.
- **Test it directly.** Choose an observation that would differ if the premise were false. Examine failure distribution across relevant actors, inputs, or times; a per-actor census is one possible check. Make the check rerunnable per [Build the Lever](../principle-build-the-lever/SKILL.md).
- **Follow the evidence.** Contradictory evidence redirects the investigation. Supporting evidence calls for the next "why" per [Fix Root Causes](../principle-fix-root-causes/SKILL.md): earlier fixes may have addressed a consequence. An inconclusive check does not settle the premise.
- **Remove the demonstrated cause within scope**, per the [Laziness Protocol](../principle-laziness-protocol/SKILL.md), rather than adding recurring compensation. For example, if a fixed coordinator assignment overloads the same worker, address that assignment.

**Stop:** Write down and test the premise before another fix assumes it. Keep the observation and its limits as evidence.

This principle is distinct from [Redesign from First Principles](../principle-redesign-from-first-principles/SKILL.md), which rebuilds a design around a new requirement. It questions a fact the current design assumes.
