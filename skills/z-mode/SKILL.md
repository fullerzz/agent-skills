---
name: z-mode
description: "Evidence-driven engineering with scoped native agents, portable principles, and task-sized verification. Use for z-mode."
disable-model-invocation: true
---

# Z Mode

Use this engineering style until the user says "stop z-mode" or chooses another style. Include the mode in a resume note; persistence depends on conversation context.

Read the [native host contract](references/native-hosts.md) before delegation or bundled commands. Simple tasks run directly. Use a task-sized plan when complexity warrants it or the user asks. A plan-only request stays read-only; implement within the requested scope.

## Working posture

Ground changes in the actual runtime flow and callers. Favor deletion, native features, and the smallest correct change. Keep read-only investigations and reviews read-only. Preserve dirty and concurrent work. Verify the real outcome and label missing proof.

Use the project's existing harness or relevant installed verification skill. Name a missing capability when it prevents required proof. Companion plugins are optional, never assumed.

Delegate when the selected workflow requests it and the host permits it. Use inherited models, bounded concurrency, and exclusive write scopes. Wait for terminal results and inspect artifacts. Independent native runs do not establish cross-provider consensus.

Local edits, commits, pushes, PRs, messages, tickets, merges, deployment, and checkout resets are distinct actions governed by the user's request.

## Routing

Read only the selected playbook. Resolve companion skills through the catalog or real sibling directories. Explicit-only companions may be read as instructions for this user-selected workflow; that does not enable automatic selection.

- [Investigation](playbooks/investigation.md)
- [Bug fix](playbooks/bug-fix.md)
- [Feature](playbooks/feature.md)
- [Refactoring](playbooks/refactoring.md)
- [Perf issue](playbooks/perf-issue.md)
- [Hillclimb](playbooks/hillclimb.md)
- [Runtime forensics](playbooks/runtime-forensics.md)
- [Trace forensics](playbooks/trace-forensics.md)
- [Prototype](playbooks/prototype.md)
- [Visual parity](playbooks/visual-parity.md)
- [Skill authoring](playbooks/authoring-a-skill.md)
- [Eval](playbooks/eval.md)
- [PR status and remediation](playbooks/babysit.md)
- [Authorized landing](playbooks/shipping.md)
- [Bounded autonomous task](playbooks/autonomous-run.md)
- [Program coordination](playbooks/orchestrate.md)
- [Independent queue](playbooks/autopilot-full.md)
- [Dependent queue](playbooks/autopilot-stack.md)
- [Session pickup](playbooks/session-pickup.md)
- [Pause safely](playbooks/pause-safely.md)
- [Multi-phase plan](playbooks/multi-phase-plan.md)
- [Worktree audit and cleanup](playbooks/worktree-cleanup.md)
- [Requested PR publication](playbooks/opening-a-pr.md)

If no playbook fits, read the installed figure-it-out skill and design a scoped workflow.

When running a benchmark or reporting a measured speedup or regression, read [benchmark-checklist](../benchmark-checklist/SKILL.md) before trusting or acting on the number. For measured eval results, read [explain the number](../principle-explain-the-number/SKILL.md).

## Principles

Load a leaf when it changes a decision. Principles remain inside task scope and host permissions.

- [attack the premise](../principle-attack-the-premise/SKILL.md)
- [boundary discipline](../principle-boundary-discipline/SKILL.md)
- [build the lever](../principle-build-the-lever/SKILL.md)
- [encode lessons in structure](../principle-encode-lessons-in-structure/SKILL.md)
- [exhaust the design space](../principle-exhaust-the-design-space/SKILL.md)
- [explain the number](../principle-explain-the-number/SKILL.md)
- [experience first](../principle-experience-first/SKILL.md)
- [fix root causes](../principle-fix-root-causes/SKILL.md)
- [foundational thinking](../principle-foundational-thinking/SKILL.md)
- [guard the context window](../principle-guard-the-context-window/SKILL.md)
- [laziness protocol](../principle-laziness-protocol/SKILL.md)
- [make operations idempotent](../principle-make-operations-idempotent/SKILL.md)
- [migrate callers then delete legacy apis](../principle-migrate-callers-then-delete-legacy-apis/SKILL.md)
- [minimize reader load](../principle-minimize-reader-load/SKILL.md)
- [model the domain](../principle-model-the-domain/SKILL.md)
- [never block on the human](../principle-never-block-on-the-human/SKILL.md)
- [outcome oriented execution](../principle-outcome-oriented-execution/SKILL.md)
- [prove it works](../principle-prove-it-works/SKILL.md)
- [redesign from first principles](../principle-redesign-from-first-principles/SKILL.md)
- [separate before serializing shared state](../principle-separate-before-serializing-shared-state/SKILL.md)
- [sequence verifiable units](../principle-sequence-verifiable-units/SKILL.md)
- [subtract before you add](../principle-subtract-before-you-add/SKILL.md)
- [test behavior not implementation](../principle-test-behavior-not-implementation/SKILL.md)
- [type system discipline](../principle-type-system-discipline/SKILL.md)

## Report

Lead with the outcome, reason, and evidence. State actual checks and practical limits. Cite real artifacts. Explain meaningful tradeoffs and omit ceremony for small changes. Comments explain non-obvious constraints and public contracts rather than narrate code.
