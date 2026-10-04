# Z-mode playbooks

Invoke the installed mode explicitly: `$z-mode` in Codex or `/z-mode` in Claude Code, followed by a concrete request. These are natural-language requests, not subcommand syntax. The mode routes the request to one playbook and reads only that leaf; if none fits, it uses the installed figure-it-out skill to design a scoped workflow. It loads a [principle](principles.md) only when that leaf changes a decision.

The mode remains active in conversation until stopped or replaced; it does not provide a scheduler. Simple work runs directly. Delegated workflows use native agents by default, or [Herdr execution](workflow-skills.md#herdr-workflow) when explicitly enabled for the session. Herdr applies alongside every playbook below, including its companions, rather than adding a separate route. Both paths preserve bounded concurrency, exclusive ownership, artifact verification, and action authority. Native settings are inherited; independently launched CLIs have their own configuration. Missing independent coverage must be disclosed. See the [mode source](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/SKILL.md) and [execution contract](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/references/native-hosts.md#execution-selection).

Bundled tools are optional capabilities, not a runtime supplied by the mode. Resolve the real installed skill directory, use quoted absolute script paths, and retain the target repository as cwd. Run the plan validator (`check_plan.py`), worktree audit (`worktree_audit.py`), GitHub watcher (`watch-pr/watch_pr.py`), and orchestration CLI (`orch/orch.py`) with `uv run`. They require Python 3.12+ and use the standard library without installing dependencies beside the skill scripts. The existing shell launchers forward to uv. Consult each tool’s usage guidance; forge access, Graphite metadata, native delegation and durable background execution are separate prerequisites.

## Investigation {#playbook-investigation}

Answer a read-only question about a runtime flow or design decision.

```text
Codex: $z-mode Explain how session reuse works and why it skips startup commands.
Claude Code: /z-mode Explain how session reuse works and why it skips startup commands.
```

Trace the flow with how, consult why for motivation, compare relevant alternatives, and return a cited answer with gaps.

**Prerequisites and limits:** Read-only scope excludes edits, prototypes, and publication.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/investigation.md).

## Bug fix {#playbook-bug-fix}

Repair a reproduced defect.

```text
Codex: $z-mode Fix the restart crash in the session loader.
Claude Code: /z-mode Fix the restart crash in the session loader.
```

Reproduce on the reported surface, trace callers and history, make the smallest root-cause fix, add a focused regression, and rerun the original repro. Return mechanism, fix, checks, and limits.

**Prerequisites and limits:** A missing runtime or harness must be reported as missing proof; publication needs its own request.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/bug-fix.md).

## Feature {#playbook-feature}

Implement a scoped user-visible capability.

```text
Codex: $z-mode Add filtering to the session picker.
Claude Code: /z-mode Add filtering to the session picker.
```

Ground entry points and contracts, choose a simple data shape, implement all affected consumers, and verify observable behavior. Return result, meaningful choices, proof, and open decisions.

**Prerequisites and limits:** Small tasks stay direct; native delegation is optional for exclusive independent seams. Commit and publication require covered authority.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/feature.md).

## Refactoring {#playbook-refactoring}

Change structure while holding behavior steady.

```text
Codex: $z-mode Simplify the picker API without changing behavior.
Claude Code: /z-mode Simplify the picker API without changing behavior.
```

Pin behavior, remove redundant layers, migrate callers and references in coherent units, and verify equivalence on the actual artifact. Return the structural change and held contract.

**Prerequisites and limits:** Compilation alone is not equivalence; separately discovered product defects remain separate.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/refactoring.md).

## Performance issue {#playbook-perf-issue}

Investigate and improve one measured performance complaint.

```text
Codex: $z-mode Reduce picker latency on a 10000-session workload.
Claude Code: /z-mode Reduce picker latency on a 10000-session workload.
```

Capture a repeatable baseline, vet each number with [benchmark-checklist](workflow-skills.md#benchmark-checklist), trace cost, change one mechanism, interleave baseline and treatment samples, and run correctness regressions. Return units, delta, method, and artifacts.

**Prerequisites and limits:** Use the same realistic workload; source inspection cannot prove a win. Use hillclimb for sustained optimization.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/perf-issue.md).

## Hillclimb {#playbook-hillclimb}

Run bounded measured optimization attempts.

```text
Codex: $z-mode Hillclimb picker latency below 50 ms with a 30-minute budget.
Claude Code: /z-mode Hillclimb picker latency below 50 ms with a 30-minute budget.
```

Fix metric, workload, target, correctness floor, sampling and budget; vet the probe with [benchmark-checklist](workflow-skills.md#benchmark-checklist) before freezing it, including error and completed-work counts; record one hypothesis per isolated attempt in show-me-your-work; keep wins above noise. Return baseline/final, accepted and rejected attempts, and trail.

**Prerequisites and limits:** Requires a stable probe and decision trail. Stop at target, stop request, budget, or blocker; discard only this run's failed edits.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/hillclimb.md).

## Runtime forensics {#playbook-runtime-forensics}

Diagnose a live runtime signal.

```text
Codex: $z-mode Diagnose the worker memory growth using a live heap capture.
Claude Code: /z-mode Diagnose the worker memory growth using a live heap capture.
```

Capture project instrumentation, reduce hot paths or retainers, confirm the mechanism with bounded instrumentation, and map to source. Return observations, hypotheses, evidence, and gaps.

**Prerequisites and limits:** Needs an accessible instrumented instance. Diagnosis does not authorize a fix or hot-patching production.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/runtime-forensics.md).

## Trace forensics {#playbook-trace-forensics}

Diagnose a supplied profile, trace, or heap artifact.

```text
Codex: $z-mode Explain the hot path in the supplied CPU profile.
Claude Code: /z-mode Explain the hot path in the supplied CPU profile.
```

Identify format, use an existing parser, query frames or retainers, map symbols to source, and compare paired captures when available. Return a cited diagnosis and artifact paths.

**Prerequisites and limits:** No fix or new production capture unless requested; without corroboration label the strongest supported hypothesis.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/trace-forensics.md).

## Prototype {#playbook-prototype}

Settle an uncertain design decision with a throwaway experiment.

```text
Codex: $z-mode Prototype two keyboard navigation layouts for the picker.
Claude Code: /z-mode Prototype two keyboard navigation layouts for the picker.
```

Name the decision, build minimal variants in scratch space, observe interaction or timing, and return evidence, tradeoffs, recommendation, and scratch path.

**Prerequisites and limits:** Visual choices need rendered evidence when available; scratch output is not production integration.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/prototype.md).

## Visual parity {#playbook-visual-parity}

Preserve rendered behavior during a migration.

```text
Codex: $z-mode Migrate the dialog while preserving pixel-exact visual parity.
Claude Code: /z-mode Migrate the dialog while preserving pixel-exact visual parity.
```

Pin immutable baselines, states, viewport, fonts, and environment; migrate shared primitives first; compare with the image-diff harness and inspect interactions. Return per-state results and artifacts.

**Prerequisites and limits:** Needs stable baselines and a rendered comparison harness. Pixel-exact requests use zero tolerance; appearance alone is not proof.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/visual-parity.md).

## Skill authoring {#playbook-authoring-a-skill}

Create or revise a portable skill.

```text
Codex: $z-mode Author a skill for inspecting our release checks.
Claude Code: /z-mode Author a skill for inspecting our release checks.
```

Read callers and policy, keep one canonical folder, put conditional procedures in resources, resolve real installed paths, validate metadata and helpers, and run a realistic scoped scenario for behavior changes. Return local artifact and validation.

**Prerequisites and limits:** Preserve explicit-only host policy. Project discovery uses .agents/skills or .claude/skills; authoring does not authorize global installation, commits, messages, tickets, or PRs.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/authoring-a-skill.md).

## Evaluation {#playbook-eval}

Compare skill variants on real host behavior.

```text
Codex: $z-mode Evaluate these two skill variants on the same bug-fix request.
Claude Code: /z-mode Evaluate these two skill variants on the same bug-fix request.
```

Define 3–6 held-out criteria, isolate candidate directories, issue identical unlabeled requests in native sessions, capture actual evidence, and use a fresh blind judge. Return rubric, receipts, verdict, and recommendation.

**Prerequisites and limits:** Needs supported native sessions and scoped history access. Without an independent judge mark parent-only evaluation; self-reports do not prove a skill was read.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/eval.md).

## PR status and remediation {#playbook-babysit}

Check PR state or drive explicitly requested remediation.

```text
Codex: $z-mode Check PR 42 status in one read-only pass.
Claude Code: /z-mode Check PR 42 status in one read-only pass.
```

Choose check, drive, threads-only, or requested background mode; resolve exact heads and reviews; triage findings against code; verify requested fixes and re-query the new head. Return state, remediation, checks, and blockers.

**Prerequisites and limits:** GitHub watcher is an optional Python tool launched with uv and requiring forge access; use its --help and absolute installed path. Read-only status excludes fixes and replies; merge-ready is not merged. Background requires a supported live runtime.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/babysit.md).

## Authorized landing {#playbook-shipping}

Land changes explicitly authorized for merge.

```text
Codex: $z-mode Merge PR 42 when its current-head checks pass, using squash.
Claude Code: /z-mode Merge PR 42 when its current-head checks pass, using squash.
```

Pin dependencies and receipts, re-check current-head CI and reviews, land only the contiguous verified frontier, wait for confirmed merge, then refresh trunk and the next head. Return actual merges and remaining ceiling.

**Prerequisites and limits:** Requires explicit landing authority and forge access. Substantial behavior changes need independent verification where supported; no bypassing approvals or unsolicited verdict posts.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/shipping.md).

## Bounded autonomous task {#playbook-autonomous-run}

Complete one bounded task continuously in the current session.

```text
Codex: $z-mode Work until the failing import check passes, with a 30-minute limit.
Claude Code: /z-mode Work until the failing import check passes, with a 30-minute limit.
```

State done predicate, scope, budget and capabilities; make justified verified iterations; retain checkpoints via show-me-your-work; stop at verified done, stop, blocker, or limit. Return predicate state and remaining work.

**Prerequisites and limits:** Does not supply overnight scheduling or wider publication authority. If persistence ends, write the pause-safely handoff.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/autonomous-run.md).

## Program coordination {#playbook-orchestrate}

Coordinate a program larger than one simple run.

```text
Codex: $z-mode Coordinate the parser and UI migration with exclusive owners and verified handoffs.
Claude Code: /z-mode Coordinate the parser and UI migration with exclusive owners and verified handoffs.
```

Pin units and dependencies, pilot the brief, store user-owned state and receipts, run bounded native owners, wait for terminal reports, inspect artifacts, relay verified dependencies, and reconcile every child. Return counts, frontier, blockers, and state directory.

**Prerequisites and limits:** Needs native delegation; absent independent coverage must be disclosed. The optional Python orch CLI runs with uv and provides bookkeeping only; frontier needs Graphite metadata. One coordinator owns topology, and no durable runtime means handoff.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/orchestrate.md).

## Independent queue {#playbook-autopilot-full}

Execute independent work items with explicit done predicates.

```text
Codex: $z-mode Complete these three independent fixes and deliver local verified artifacts.
Claude Code: /z-mode Complete these three independent fixes and deliver local verified artifacts.
```

Pin scope, gates and authority; assign exclusive native owners; independently verify exact heads; publish or merge only covered items; reconcile children on stop. Return item, owner, status, head, evidence, and remaining gates.

**Prerequisites and limits:** Host concurrency and native reviewers bound coverage. The name grants no merge authority or permission to bypass operator gates.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/autopilot-full.md).

## Dependent queue {#playbook-autopilot-stack}

Build an ordered chain of dependent changes for review.

```text
Codex: $z-mode Build the schema then API then UI changes as a review stack; do not merge.
Claude Code: /z-mode Build the schema then API then UI changes as a review stack; do not merge.
```

Pin order and acceptance, assign exclusive owners, relay verified parent context, let one coordinator own topology, and verify each base/head patch. Return ordered artifacts and per-unit SHAs/verdicts.

**Prerequisites and limits:** Publication must be authorized: root targets trunk and children target parents. No merge or auto-merge; authorized rebases require fresh evidence.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/autopilot-stack.md).

## Session pickup {#playbook-session-pickup}

Resume from a named handoff or prior session.

```text
Codex: $z-mode Resume from .agent-work/import-fix/handoff.md.
Claude Code: /z-mode Resume from .agent-work/import-fix/handoff.md.
```

Read only named session evidence, reconstruct goal and state, refresh live Git/PR facts and load-bearing claims, then route remaining work. Return inherited versus refreshed proof and exact resume action.

**Prerequisites and limits:** Needs the named handoff or supported scoped history access; inherited summaries are not live evidence and authority does not expand.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/session-pickup.md).

## Pause safely {#playbook-pause-safely}

Preserve a resumable task at an explicit pause or runtime limit.

```text
Codex: $z-mode Pause now and save a concrete resume note for the import fix.
Claude Code: /z-mode Pause now and save a concrete resume note for the import fix.
```

Stop at an atomic boundary, drain children, preserve all files, and write goal, active mode, authority, heads, dirty state, checks, decisions, blockers, and the first resume action. Return note and on-disk state.

**Prerequisites and limits:** No side-effect commit, push, or discard. Default note lives under `.agent-work/<slug>`; verify it survives teardown and refresh live state on resume.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/pause-safely.md).

## Multi-phase plan {#playbook-multi-phase-plan}

Produce a verifiable phased plan before implementation.

```text
Codex: $z-mode Plan the parser migration in docs/parser-plan.md; stop before implementation.
Claude Code: /z-mode Plan the parser migration in docs/parser-plan.md; stop before implementation.
```

Ground constraints, write Outcome, Scope, Phases, Risks and Handoff; give each phase Depends on, Files, Acceptance and Verification; run the bundled plan validator. Return path, dependencies, tradeoffs, and validator result.

**Prerequisites and limits:** Planning stays read-only apart from the requested plan. Validator needs Node and its real installed script path; no automatic implementation, fixed lane count, or overnight promise.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/multi-phase-plan.md).

## Worktree audit and cleanup {#playbook-worktree-cleanup}

Audit worktrees and remove only specifically authorized candidates.

```text
Codex: $z-mode Audit this repository worktrees without removing any.
Claude Code: /z-mode Audit this repository worktrees without removing any.
```

Run the bundled audit for the explicit target repository, inspect each candidate's files, diffs, activity and history, then remove only authorized clean unused trees without force. Return held candidates and reclaimed space.

**Prerequisites and limits:** Audit needs Bash, Node and Git; optional --with-prs needs GitHub access. Buckets are advice, CLOSED is not merged, unknown history is not safe, and caches need separate scope.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/worktree-cleanup.md).

## Requested PR publication {#playbook-opening-a-pr}

Publish a scoped change when asked.

```text
Codex: $z-mode Commit these task files and open a draft PR against main.
Claude Code: /z-mode Commit these task files and open a draft PR against main.
```

Verify repository, branch, base and dirty state; check requirements; stage intended files; commit and publish within authority; write a concrete body and read back head, base and URL. Return publication link and validation.

Use the host's built-in PR tool for supported operations and forge or stack tooling for the rest. With no built-in tool, GitHub falls back to gh with a body file. Complete any required host attachment even when creation used a CLI.

Descriptions use `## Why`, `## What changed`, `## Scope`, optional `## Tradeoffs` and `## Blast Radius`, and `## Verification`, unless the repository template or user specifies another format. Keep each stack layer's description scoped to its own diff; root targets trunk and children target their parent branch.

**Prerequisites and limits:** Requires publication authority. Honor requested draft/ready status and repository policy; otherwise open ready and verify actual state. Opening a PR does not authorize merge, auto-merge, or background babysitting.

[Supporting playbook](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/playbooks/opening-a-pr.md).
