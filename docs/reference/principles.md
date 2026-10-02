# Poteto-mode principles

Principles are decision leaves, not a checklist to load in bulk. After selecting a [playbook](playbooks.md), poteto-mode reads a principle only when it changes a concrete decision: where to fix a defect, whether to add an abstraction, how to represent state, or what counts as proof. The mode’s explicit invocation reads these companions as instructions; it does not change their explicit-only invocation policy.

Use `$poteto-mode Fix the restart crash; trace its root cause.` in Codex or `/poteto-mode Fix the restart crash; trace its root cause.` in Claude Code. The request selects bug-fix; evidence may then select fix-root-causes or make-operations-idempotent. Leaves preserve task scope, permissions and action authority. See the [routing source](https://github.com/fullerzz/agent-skills/blob/main/skills/poteto-mode/SKILL.md).

## Attack the premise {#principle-attack-the-premise}

**Decision affected:** After two fixes sharing an assumption fail the same gate, decide whether the assumption itself is wrong. Write it down and take a rerunnable per-actor census before another fix.

**Example:** Two rebalancing fixes leave the same workers overloaded: measure each worker, find who assigns the fixed coordinator role, and remove the role asymmetry. An even census points elsewhere.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-attack-the-premise/SKILL.md).

## Boundary discipline {#principle-boundary-discipline}

**Decision affected:** Decide where validation, errors and adapters belong: parse external input once into domain types, keep business logic pure, and retain necessary error handling and synchronization.

**Example:** Parse a CLI timeout into a validated duration at the CLI boundary; the scheduling function accepts that duration rather than reparsing strings.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-boundary-discipline/SKILL.md).

## Build the lever {#principle-build-the-lever}

**Decision affected:** For non-trivial work, choose a rerunnable tool that performs or proves it instead of manual repetition; skip only a couple of obvious trivial edits.

**Example:** Migrate one call by hand, then write a small codemod, rerun it on that unit and compare its diff before processing the rest. The lever is an actual file, not a claimed methodology.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-build-the-lever/SKILL.md).

## Encode lessons in structure {#principle-encode-lessons-in-structure}

**Decision affected:** When a correction recurs, choose the strongest enforceable mechanism rather than repeating prose; judgment-only rules still need a clear failure example.

**Example:** Repeated accidental implicit invocation becomes a metadata policy flag checked by validation. A one-off correction remains a local task note; persistent memory and external tickets require authority.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-encode-lessons-in-structure/SKILL.md).

## Exhaust the design space {#principle-exhaust-the-design-space}

**Decision affected:** For a novel interaction or architecture without precedent, compare 2–3 materially different prototypes before implementation.

**Example:** Compare command palette, inline filter and separate search panel with rendered keyboard interactions. Do not prototype alternatives for a mechanical change with one established shape.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-exhaust-the-design-space/SKILL.md).

## Experience first {#principle-experience-first}

**Decision affected:** Choose scope and details by the consumer’s experience, including API users and maintainers, rather than implementation convenience.

**Example:** Ship a polished picker with clear empty and error states before adding ten rarely used controls. Prototype the core loop before production implementation.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-experience-first/SKILL.md).

## Fix root causes {#principle-fix-root-causes}

**Decision affected:** Choose the repair location from reproduction and mechanism rather than a symptom-suppressing guard.

**Example:** A restart failure disappears after deleting serialized state: inspect stale-state validation and repair reconciliation instead of adding nil checks to each consumer. Report out-of-scope siblings.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-fix-root-causes/SKILL.md).

## Foundational thinking {#principle-foundational-thinking}

**Decision affected:** Choose core data structures and sequence shared foundations before dependent logic, after removing dead complexity.

**Example:** For ID lookups, define one keyed session model before adding picker and API consumers; keep three simple statements instead of a premature generic abstraction.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-foundational-thinking/SKILL.md).

## Guard the context window {#principle-guard-the-context-window}

**Decision affected:** Choose targeted reads, summaries and bounded phases when raw payloads threaten useful context.

**Example:** Read the named trace slice and keep a mechanism summary in the main thread. Route independent bulk to native delegates only when authorized and available.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-guard-the-context-window/SKILL.md).

## Laziness protocol {#principle-laziness-protocol}

**Decision affected:** Choose deletion, fewer layers and one source of decisions before introducing abstractions or threading signals through pipelines.

**Example:** Inline a one-caller pass-through and calculate readiness once at the owner rather than forwarding the same signal through four layers.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-laziness-protocol/SKILL.md).

## Make operations idempotent {#principle-make-operations-idempotent}

**Decision affected:** Choose reconciliation so repeated or interrupted state changes converge to the same correct end state.

**Example:** On startup, adopt existing live sessions and clear stale PID locks before creating missing sessions; rerun after each possible interruption point to prove no duplicates.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-make-operations-idempotent/SKILL.md).

## Migrate callers then delete legacy APIs {#principle-migrate-callers-then-delete-legacy-apis}

**Decision affected:** For coordinated internal API changes without external compatibility obligations, migrate every caller and remove the old path in the same wave.

**Example:** Replace internal loadSession(id, flag) calls with the new session request type, update contract tests, then delete the old function rather than retaining an adapter.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md).

## Minimize reader load {#principle-minimize-reader-load}

**Decision affected:** Judge maintainability by layers to trace and mutable state to remember; only add a layer when it reduces understanding cost elsewhere.

**Example:** Inline an adapter that repeats identical arguments and turn a synchronized global selection flag into a value derived locally from selectedId.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-minimize-reader-load/SKILL.md).

## Model the domain {#principle-model-the-domain}

**Decision affected:** Choose a structure that removes repeated rules, branches or invalid states; avoid abstractions that only add indirection.

**Example:** Replace running, stopping and stopped booleans with one lifecycle state machine so impossible combinations cannot arise.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-model-the-domain/SKILL.md).

## Never block on the human {#principle-never-block-on-the-human}

**Decision affected:** Proceed on authorized reversible execution choices; clarify real missing product decisions and respect separate action authority.

**Example:** Fix the requested parser defect and show its checked diff without asking whether to edit. A read-only diagnosis stays read-only, and fixes do not silently authorize a push.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-never-block-on-the-human/SKILL.md).

## Outcome-oriented execution {#principle-outcome-oriented-execution}

**Decision affected:** In a planned migration, converge on the verified target instead of adding throwaway compatibility solely to smooth every intermediate state.

**Example:** Declare a bounded phase where imports may temporarily fail, keep touched-area checks, then require full static and runtime verification at completion.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-outcome-oriented-execution/SKILL.md).

## Prove it works {#principle-prove-it-works}

**Decision affected:** Choose direct observation of the real artifact before declaring completion, preferably a deterministic rerunnable comparison.

**Example:** Run the changed picker and inspect its actual selected value; an agent report, file mtime or successful compile alone cannot prove the interaction.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-prove-it-works/SKILL.md).

## Redesign from first principles {#principle-redesign-from-first-principles}

**Decision affected:** Integrate a new requirement as though it were foundational, reading all affected files and propagating the resulting design through references.

**Example:** When multi-workspace support arrives, redesign the session identity around workspace ownership and update types, examples and docs, then deliver coherent increments.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-redesign-from-first-principles/SKILL.md).

## Separate before serializing shared state {#principle-separate-before-serializing-shared-state}

**Decision affected:** Eliminate unnecessary shared write targets before adding locks; structurally serialize only when one canonical shared object is a real invariant.

**Example:** Give indexer and metrics workers separate owned state files and combine them when reporting. If they truly share one queue, use a single writer or lock rather than a convention.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-separate-before-serializing-shared-state/SKILL.md).

## Sequence verifiable units {#principle-sequence-verifiable-units}

**Decision affected:** Order multi-step edits and delivery into small checked units; do not build further on a broken base.

**Example:** Capture the baseline, add a failing regression, then fix it and rerun the check before the next migration unit. Commit/PR ordering remains subject to publication authority.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-sequence-verifiable-units/SKILL.md).

## Subtract before you add {#principle-subtract-before-you-add}

**Decision affected:** Choose removal of dead code, redundant validation and empty references before constructing the next capability.

**Example:** Delete unused picker adapters and duplicate config validators, then build the new option on the smaller model; do not retain a reference stub with no novel guidance.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-subtract-before-you-add/SKILL.md).

## Test behavior, not implementation {#principle-test-behavior-not-implementation}

**Decision affected:** Choose tests that exercise user-facing behavior and assert literal outcomes, rather than call counts, constant pins or self-referential expectations.

**Example:** Call slugify("Hello, World!") and expect "hello-world". For a mocked transport assert the sent payload or resulting state; a test that survives undefined implementations needs revision or deletion.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-test-behavior-not-implementation/SKILL.md).

## Type system discipline {#principle-type-system-discipline}

**Decision affected:** Use types to remove partiality and illegal states; validate external data, distinguish semantic primitives, exhaust variants and derive schemas rather than lying with casts.

**Example:** Represent a task as open or done-with-time instead of completed plus optional completedAt. Use UserId and OrderId types and parse JSON once; sum still accepts an ordinary possibly empty list.

[Supporting principle](https://github.com/fullerzz/agent-skills/blob/main/skills/principle-type-system-discipline/SKILL.md).
