---
name: architect
description: "Sketch types, signatures, and module structure before code, then stay in the loop while implementation fills in. Use for /architect, 'architect this', 'design this', or non-trivial work where jumping to code would lock in the wrong shape."
disable-model-invocation: true
---

# Architect

Design the smallest coherent shape before code. A design request produces a design. Implement only if requested, honoring any review checkpoint.

## Phase A: Ground the problem

Trace runtime flow and callers with how where useful. Use why when changing ownership risks discarding a historical constraint. Greenfield work still has boundaries.

## Phase B: Sketch

Write caller usage first, then derive types, signatures, ownership, and invariants. For contested/novel designs compare structurally distinct candidates with arena and the [runner prompt](references/runner-prompt.md). A constrained mechanical change needs one sketch and the constraint.

Use the [rationale template](references/rationale-template.md) at the task's scale; screen [red flags](references/design-red-flags.md). Assume the next contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. Prefer the design where a change that looks right from one file is right for the whole repo. Prefer a small interface hiding meaningful complexity. Separate shared writes before synchronizing.

## Phase C: Agree

Present the choice and tradeoffs. Honor a requested checkpoint. Do not publish scaffolding by default.

## Phase D: Implement

When authorized, fill the sketch and verify caller behavior. Deviations are evidence to revisit design or requirements.

## Phase E: Scrap

Repeated workarounds, casts, synchronization, or caller knowledge of internals can refute a design. Re-ground and simplify around observed constraints.

Follow the [native contract](../z-mode/references/native-hosts.md) for delegated candidates.
