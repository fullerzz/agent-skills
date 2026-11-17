---
name: architect
description: "Sketch types, signatures, and module structure before code, then stay in the loop while implementation fills in. Use for /architect, 'architect this', 'design this', or non-trivial work where jumping to code would lock in the wrong shape."
disable-model-invocation: true
---

# Architect

A design request produces a design. Implement only if requested, honoring any review checkpoint.

Before writing code, trace every system the change touches through its runtime flow and callers. When the design changes ownership or layering, use why so the existing rationale becomes a constraint. Sketch two different shapes, writing caller usage first and then types, signatures, and module boundaries. Pick the one where each piece of state has one owner, each task has one way to do it, and callers need to know least. A constrained mechanical change needs one sketch and the constraint. Redesign instead of patching when workarounds repeat.

For a large or contested design, run the [arena](../arena/SKILL.md) skill instead of sketching alone. Present the choice and its tradeoffs. Do not publish scaffolding by default.
