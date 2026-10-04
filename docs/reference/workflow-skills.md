# Workflow skills

These entries describe the 27 workflow and style skills in this library. Each example is a chat prompt after installation. Codex uses `$skill-name`; Claude Code uses `/skill-name`. For the native plugins, use the namespaced equivalent: select `zstack:how` through the Codex skill picker or invoke `/zstack:how` in Claude Code. Replace the task details with your own files, feature, or repository.

Codex permits automatic selection only for the read-only `how` and `why` skills; every other skill, including `setup-zstack`, requires explicit invocation. Claude Code retains explicit-only flags for `how` and `why`; `setup-zstack` permits implicit invocation there. Reading a companion inside an explicitly selected workflow does not change that companion’s invocation policy.

Delegated workflows use native host agents by default, or [Herdr execution](#herdr-workflow) when explicitly enabled. Native agents inherit model configuration; Herdr-launched CLIs use their own settings. Both retain bounded concurrency and isolated write ownership. Independent runs are not proof of provider diversity. Reports disclose unavailable agents and incomplete coverage. A workflow request does not independently authorize commits, publication, messages, or tracker writes.

## Herdr workflow {#herdr-workflow}

You want existing workflows to run their agents and useful long-running supporting processes visibly in Herdr.

Start with the [Herdr walkthrough](../guide/herdr.md) for setup, execution behavior, pause/resume, and troubleshooting, or visit the upstream [Herdr documentation](https://herdr.dev/docs/).

| Host | Example invocation |
| --- | --- |
| Codex | `$z-mode Use Herdr execution for this session, then fix the reconnect bug.` |
| Claude Code | `/zstack:z-mode Use Herdr execution for this session, then fix the reconnect bug.` |
| Hermes | `Load zstack:z-mode with skill_view and enable Herdr execution for this session.` |

For execution selection without activating z-mode, invoke `herdr-workflow` explicitly and ask to enable it. A one-off request such as `$herdr-workflow Inspect the agents assigned to this task` does not persist a session preference.

### How it works

Z-mode selects the normal task playbook, then loads this companion when Herdr is enabled. The playbook determines work, ownership, and acceptance; Herdr supplies agent launch, prompt submission, lifecycle waits, terminal inspection, and useful supporting panes. A small task still runs directly. The coordinator maintains task-to-agent/pane assignments and accepts artifacts only after the workflow's checks.

The session hook supplies Herdr and Native controls alongside Enable and Disable. Herdr changes execution only; Native disables Herdr while preserving z-mode. Enable selects z-mode and retains an existing execution preference; Disable clears both. These are preference writes, not process controls. Explicit pause drains or stops assigned workers; client detach leaves processes running.

### Expected result

The original workflow's deliverable, visible task-owned agents/processes, verified results, and a reconciled roster or handoff. Reports distinguish agent readiness from task acceptance and name incomplete evidence.

### Dependencies and limits

Herdr control requires `HERDR_ENV=1`, a compatible CLI/server, and the selected agent CLI. The installed CLI's help determines syntax. Missing capabilities require a disclosed, user-selected fallback; host restrictions and combined worker limits still apply. The upstream [agent guide](https://herdr.dev/agent-guide.md), [concepts](https://herdr.dev/docs/concepts/), [working guide](https://herdr.dev/docs/how-to-work/), and [automation docs](https://herdr.dev/docs/agent-automation/) describe Herdr itself.

New CLI sessions do not inherit the coordinator's context, model settings, permissions, or activation. Panes alone do not isolate filesystem writes. Use existing task authority for exclusive files or requested worktrees, and supply consolidated briefs. Server restart is different from detach: conversation restoration depends on native integrations and does not prove work continued.

The preference is a marker beside mode state in each native host's plugin data directory and restored only for the same session ID. Stopping or switching away from active z-mode and clear/reset remove both; a Herdr-only selection survives a style switch; new children and rotated IDs start without either. Without the new hooks, record selection and opt-out conversationally. No installation, permission changes, server restarts, publication, or extra delegation follow merely from enabling it.

[Full herdr-workflow instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/herdr-workflow/SKILL.md)

## Benchmark checklist {#benchmark-checklist}

Use this before reporting or acting on a measured speedup or regression.

| Host | Example invocation |
| --- | --- |
| Codex | `$benchmark-checklist Vet the before/after export benchmark and its measurement script.` |
| Claude Code | `/benchmark-checklist Vet the before/after export benchmark and its measurement script.` |

### How it works

Checks the limiter, production tuning, physical limits, failures, repeatability, end-to-end relevance, and whether the timed work happened. Comparative runs use at least five samples per side with counterbalanced or balanced randomized ordering, equivalent starting state, and independent warmup where needed. Record the order and state preparation, and report the median and range. A requested single-run ballpark still checks errors and completed work and is labeled as one run.

### Expected result

A faster, slower, no measurable difference, or inconclusive verdict with units, run count, spread, limiter evidence, and artifact paths.

### Dependencies and limits

Uses [Explain the number](principles.md#principle-explain-the-number). Z-mode's performance and hillclimb playbooks read this companion without changing its explicit-only policy. Missing evidence stays a gap; the skill does not expand the requested runtime budget or authorize publication.

[Full benchmark-checklist instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/benchmark-checklist/SKILL.md)

## Architect {#architect}

You need types, ownership, or module boundaries before a non-trivial implementation.

| Host | Example invocation |
| --- | --- |
| Codex | `$architect Design the queue admission API. Stop after the design for review.` |
| Claude Code | `/architect Design the queue admission API. Stop after the design for review.` |

### How it works

The agent traces callers and runtime flow, sketches caller usage, derives types and invariants, and compares distinct designs when the choice warrants an arena. It presents tradeoffs before implementation. Authorized implementation tests the sketch against real caller behavior and revisits designs that require repeated workarounds.

### Expected result

A grounded design with signatures, ownership, invariants, and tradeoffs. Code follows only when requested.

### Dependencies and limits

Uses how for flow, why for historical constraints, and arena for contested designs. A design request does not authorize scaffolding or implementation.

[Full architect instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/architect/SKILL.md)

## Arena {#arena}

Several plausible approaches could produce materially different designs or artifacts.

| Host | Example invocation |
| --- | --- |
| Codex | `$arena Compare three designs for queue coalescing and synthesize the strongest result.` |
| Claude Code | `/arena Compare three designs for queue coalescing and synthesize the strongest result.` |

### How it works

The agent defines the artifact and 3–6 criteria, then assigns the same brief to 2–3 independent native candidates unless you request another useful count. Each candidate has isolated output. After every candidate finishes, a fresh read-only judge scores the artifacts. The coordinator chooses a base, adapts useful ideas, and verifies the synthesis.

### Expected result

A verified artifact plus the chosen base, adopted ideas, rejected ideas, reviewer identities, and coverage gaps.

### Dependencies and limits

Requires native delegation for independent candidates. Concurrency stays within host limits. Missing candidates remain gaps. A parent-only judgment is labeled. Same-model runs do not establish cross-provider comparison.

[Full arena instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/arena/SKILL.md)

## Automate me {#automate-me}

You want a personal mode that records stated conventions or patterns from explicitly scoped history.

| Host | Example invocation |
| --- | --- |
| Codex | `$automate-me Draft a project mode named review-first from my stated preferences in this chat.` |
| Claude Code | `/automate-me Draft a project mode named review-first from my stated preferences in this chat.` |

### How it works

The agent locates an existing named mode, preserves confirmed rules, and mines history only when requested. It writes concise SKILL.md metadata and instructions, references companions, and validates a local draft. For both hosts, one canonical directory has a collision-safe link into the other discovery directory.

### Expected result

A reviewable personal-mode skill, with its evidence basis and registration status. Subjective rules remain open to your review.

### Dependencies and limits

Defaults to explicit-only invocation. Project paths are .agents/skills for Codex and .claude/skills for Claude Code. Personal paths require that scope in your request. History access can be unavailable. Authoring does not authorize publication.

[Full automate-me instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/automate-me/SKILL.md)

## Blast radius {#blast-radius}

You need to know what a change can break beyond its immediate callers or diff.

| Host | Example invocation |
| --- | --- |
| Codex | `$blast-radius Review the blast radius of the cache eviction diff and prove its key safety assumption.` |
| Claude Code | `/blast-radius Review the blast radius of the cache eviction diff and prove its key safety assumption.` |

### How it works

The agent reads the diff and history, identifies the fact that makes the change safe, and follows indirect contracts through pinned dependencies, wire formats, database state, and timing. It separates confirmed risks from cleared cases and runs the cheapest real-code proof available. Wide reviews can use independent read-only reviewers.

### Expected result

A cited account of the change, its safety fact and proof level, confirmed risks, cleared cases, and the cheapest pre-merge check. Unproven facts are labeled.

### Dependencies and limits

Uses how, why, and unslop. A read-only request creates no files. Missing execution permission remains a proof gap. Source inspection is weaker evidence than a runnable check or live reproduction.

[Full blast-radius instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/blast-radius/SKILL.md)

## Bro {#bro}

The previous assistant reply is too dense or full of jargon.

| Host | Example invocation |
| --- | --- |
| Codex | `$bro` |
| Claude Code | `/bro` |

### How it works

The agent restates its last message in concise, ordinary language.

### Expected result

A clearer version of the previous reply.

### Dependencies and limits

This is a rewrite of the last reply, not a new investigation or implementation.

[Full bro instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/bro/SKILL.md)

## Correct {#correct}

You keep correcting agents for the same repository mistakes and want enforceable prevention.

| Host | Example invocation |
| --- | --- |
| Codex | `$correct Find repeated mistakes in this repo's recent history and implement prevention. Leave changes uncommitted.` |
| Claude Code | `/correct Find repeated mistakes in this repo's recent history and implement prevention. Leave changes uncommitted.` |

### How it works

Groups cited, independent incidents into classes with at least two occurrences, then addresses the most frequent within scope. Prefers architecture, types, lint or CI, and behavioral tests, with docs reserved for judgment calls. Reproduces past mistakes in isolation to demonstrate failing checks and corrected cases, and pairs remaining rules with enforcement in the repository's agent instruction file.

### Expected result

Reviewable prevention changes and a report of each class, evidence, selected level, reasons higher levels were unsuitable, actual checks, and proof gaps. A review-only request produces findings and proposals.

### Dependencies and limits

Uses scoped history access and the repository's existing checks. Missing history or unexecuted CI is disclosed. Explicit-only on both hosts; future corrections do not automatically activate it. Commits, publication, personal memory, messages, and tracker writes require their own authorization.

[Full correct instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/correct/SKILL.md)

## Create a verification skill {#create-verification-skill}

The project lacks a reusable way to launch, drive, and prove real user behavior.

| Host | Example invocation |
| --- | --- |
| Codex | `$create-verification-skill Create a verification skill for this CLI using its existing PTY tests.` |
| Claude Code | `/create-verification-skill Create a verification skill for this CLI using its existing PTY tests.` |

### How it works

The agent inspects the project’s real launch commands, interaction tools, observables, and isolation requirements. It creates a project-local `verify-<app>` skill with Launch, Doctor, Drive, Evidence, and Cleanup instructions, plus a feature index and initial feature files. It runs one mapped feature end to end and invokes bundled helpers from a different working directory to check portability.

### Expected result

A verification skill and feature map with a demonstrated launch, health check, user action, evidence capture, and cleanup. Evidence survives teardown.

### Dependencies and limits

Prefers existing project tooling. If the checkout cannot build or start, the agent reports the blocker before generating executable instructions. A draft can remain unverified until that blocker is resolved. Product fixes need authorization. Discovery-directory restrictions leave registration pending. An unexecuted generated skill is a draft.

[Full create-verification-skill instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/create-verification-skill/SKILL.md)

## Figure it out {#figure-it-out}

A large migration or multi-part task has no narrower playbook and needs an auditable workflow.

| Host | Example invocation |
| --- | --- |
| Codex | `$figure-it-out Plan and carry out this API migration in independently verifiable units, preserving existing behavior.` |
| Claude Code | `/figure-it-out Plan and carry out this API migration in independently verifiable units, preserving existing behavior.` |

### How it works

The agent frames a falsifiable definition of done, scope, blockers, and rigor. It writes a phase list, captures a baseline, and builds verification before features. Each unit follows a hypothesis, small change, measurement, and keep-or-revert loop. Decisions enter a show-me-your-work trail as they occur, followed by a whole-product check.

### Expected result

The designed playbook, rigor rationale, decision-trail path, verified outcomes, and remaining work.

### Dependencies and limits

Starts from z-mode principles. Uses architect for consequential unresolved designs and native workers only across isolated seams. Explicit planning checkpoints remain binding. INCONCLUSIVE is not a passing result. Trail publication requires authorization.

[Full figure-it-out instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/figure-it-out/SKILL.md)

## How {#how}

You need runtime behavior, an onboarding explanation, or a decision about where code belongs.

| Host | Example invocation |
| --- | --- |
| Codex | `$how Explain how webhook admission reaches the execution queue, with entry points and ownership.` |
| Claude Code | `/how Explain how webhook admission reaches the execution queue, with entry points and ownership.` |

### How it works

The agent anchors the question in entry points, callers, data structures, and boundaries. Narrow questions trace directly. Broad questions use 2–3 independent read-only angles, then reconcile the returned slices against code.

### Expected result

A cited overview, key concepts, runtime flow, relevant files, and gotchas at the question’s scale.

### Dependencies and limits

Read-only. Missing delegated slices remain gaps. Uses why for historical motivation because code alone does not prove intent.

[Full how instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/how/SKILL.md)

## Interrogate {#interrogate}

You want an adversarial review of a defined diff, set of files, or design.

| Host | Example invocation |
| --- | --- |
| Codex | `$interrogate Review the working-tree queue changes for correctness. Return findings only.` |
| Claude Code | `/interrogate Review the working-tree queue changes for correctness. Return findings only.` |

### How it works

The agent pins scope and intended behavior, prepares the review rubric, and runs 2–3 independent native read-only reviewers. It waits, deduplicates, verifies actionable paths, and applies lead judgment.

### Expected result

Intent and coverage, findings categorized as Act on, Consider, Noted, or Dismissed, with evidence, locations, reviewers, rationale, and disagreements.

### Dependencies and limits

Review does not apply fixes. Unrelated dirty work is preserved. A supported security or correctness finding matters without consensus. If native agents are unavailable, the review is labeled parent-only.

[Full interrogate instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/interrogate/SKILL.md)

## Maintain a verification skill {#maintain-verification-skill}

An existing verification skill or feature map may have drifted from the application.

| Host | Example invocation |
| --- | --- |
| Codex | `$maintain-verification-skill Audit this project’s verify-admin skill and exercise every mapped feature.` |
| Claude Code | `/maintain-verification-skill Audit this project’s verify-admin skill and exercise every mapped feature.` |

### How it works

The agent locates the canonical verification directory, reconciles its feature index, and assigns bounded read-only source readers per feature. The coordinator merges recipes and owns all live driving. It health-checks instances, captures evidence for every feature, cleans failed attempts, and re-drives every harness correction.

### Expected result

A clean, changed, or blocked outcome, with source and live coverage, proven local corrections, unreachable prerequisites, and product gaps.

### Dependencies and limits

Edits stay inside the verification skill directory. Product regressions are reported, not repaired or hidden in docs. Every feature needs a live pass. Several candidate skills require target selection. No target routes to create-verification-skill.

[Full maintain-verification-skill instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/maintain-verification-skill/SKILL.md)

## No comments {#no-comments}

You want to review redundant comments, correctness suppressions, or workarounds.

| Host | Example invocation |
| --- | --- |
| Codex | `$no-comments Review unnecessary comments in the parser. Do not edit files.` |
| Claude Code | `/no-comments Review unnecessary comments in the parser. Do not edit files.` |

### How it works

A native comment-sicko or disclosed read-only fallback returns locations, proposed removals, refactor targets, evidence, and exceptions. The parent checks claims and investigates ambiguous constraints through how or why. Authorized edits fix root causes before removing suppressions and then verify replacements.

### Expected result

Accepted and rejected findings, any explicitly authorized edits, proof, and unresolved constraints.

### Dependencies and limits

Protects legal headers, public contracts, external constraints, and necessary suppression explanations. Review alone does not authorize deletion or unrelated refactors.

[Full no-comments instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/no-comments/SKILL.md)

## Z mode {#z-mode}

You want evidence-driven engineering for the current conversation.

| Host | Example invocation |
| --- | --- |
| Codex | `$z-mode Fix the reconnect bug using the project’s existing harness.` |
| Claude Code | `/z-mode Fix the reconnect bug using the project’s existing harness.` |

### How it works

The mode grounds work in runtime flow and callers, selects only the relevant playbook, and loads principles when they change a decision. Simple tasks run directly. Requested delegation uses the selected execution method with exclusive write scopes, terminal results, and artifact inspection. Enable [Herdr](#herdr-workflow) once for the session to use it alongside existing playbooks; native execution remains the default. Checks target the real outcome.

### Expected result

Task-sized changes or a scoped investigation, with actual evidence, meaningful tradeoffs, and explicit proof gaps.

### Dependencies and limits

Persists until you say stop z-mode or choose another style, subject to retained conversation context. Plan-only requests remain read-only. Commits, pushes, messages, merges, and deployments remain separate requested actions. Optional plugins are not assumed.

[Full z-mode instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/z-mode/SKILL.md)

## Recall {#recall}

You need current context across recent sessions before starting or resuming work.

| Host | Example invocation |
| --- | --- |
| Codex | `$recall Recall my queue work in this repository from the last week and identify the next step.` |
| Claude Code | `/recall Recall my queue work in this repository from the last week and identify the next step.` |

### How it works

The agent pins workspace, topic, and time window before reading scoped session evidence. It extracts goals, decisions, open threads, corrections, and artifact pointers, then checks live branch, SHA, dirty state, and relevant PR status.

### Expected result

A short context capsule, accurate per-thread status, recurring blockers, and one next action.

### Dependencies and limits

Unavailable history and digest-based evidence are labeled. Adjacent work is excluded unless it blocks the task. A single-session resume belongs to session-pickup. Habit mining belongs to automate-me.

[Full recall instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/recall/SKILL.md)

## Reflect {#reflect}

The active session contains lessons worth proposing as durable skill guidance.

| Host | Example invocation |
| --- | --- |
| Codex | `$reflect Reflect on this session and propose skill changes. Do not apply them yet.` |
| Claude Code | `/reflect Reflect on this session and propose skill changes. Do not apply them yet.` |

### How it works

Independent read-only judgment, tooling, and divergent reviewers examine scoped session evidence. The coordinator verifies moments, reads target skills, prefers existing homes, and separates missing guidance from missed invocation. It presents Accepted, Rejected, and Backlog proposals. Approved edits receive metadata, link, and relevant scenario validation.

### Expected result

Grounded proposals or authorized local edits, with the evidence basis and remaining gaps.

### Dependencies and limits

Applying edits requires approval or an existing explicit request that covers them. Filing backlog, writing memory, commits, and PRs are separate actions. Digest fallback and unavailable native reviewers remain visible.

[Full reflect instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/reflect/SKILL.md)

## Setup zstack {#setup-zstack}

You need to inspect zstack discovery or configure requested native agent models.

| Host | Example invocation |
| --- | --- |
| Codex | `$setup-zstack Inspect Codex zstack discovery and report installed versus loaded agents without changing settings.` |
| Claude Code | `/setup-zstack Inspect Claude Code zstack discovery and report installed versus loaded agents without changing settings.` |

### How it works

The agent checks the selected host’s discovery and installation collisions. For a requested model change, it verifies current native configuration and documentation, previews exact fields, and preserves unrelated settings. A fresh session checks explicit invocation and a delegated read-only investigation.

### Expected result

An installed-versus-loaded report, requested configuration changes, collision reports, and actual host verification or its gap.

### Dependencies and limits

Defaults to native model inheritance. Bundled roles are z-agent and comment-sicko. Modified agent copies survive installer reruns. Model entitlement, unsupported identifiers, and effort-suffixed IDs are never inferred. Delegation may be unavailable.

[Full setup-zstack instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/setup-zstack/SKILL.md)

## Show me your work {#show-me-your-work}

A long-running task needs a durable record of decisions and their evidence.

| Host | Example invocation |
| --- | --- |
| Codex | `$show-me-your-work Keep a local decision trail for this migration at .audit/api-migration.tsv.` |
| Claude Code | `/show-me-your-work Keep a local decision trail for this migration at .audit/api-migration.tsv.` |

### How it works

The agent maintains one append-only TSV with ts, phase, decision, why, evidence, and result. It logs decisions and checkpoints rather than every command. Each run tracks its own start boundaries. Before handoff, it audits its rows against scoped session evidence and obtains an independent read-only trail review when available.

### Expected result

A canonical local log and an Attention section identifying the reviewer and flags, or no flags. Wrong entries receive superseding rows.

### Dependencies and limits

Defaults to an uncommitted working artifact. The bundled log helper resolves from the loaded skill’s real directory and sanitizes tabs, newlines, and spreadsheet formula prefixes. History gaps and parent-only review are labeled. Commit requires authorization.

[Full show-me-your-work instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/show-me-your-work/SKILL.md)

## Swarm {#swarm}

The task needs partitioned parallel coverage, independent races, or a mixture.

| Host | Example invocation |
| --- | --- |
| Codex | `$swarm Use three read-only workers to trace API, database, and UI effects of this change.` |
| Claude Code | `/swarm Use three read-only workers to trace API, database, and UI effects of this change.` |

### How it works

The agent declares the done predicate and selection rule, then creates the smallest useful native worker set. Briefs define slices, write limits, exclusive output, checks, and PASS, ISSUES, or BLOCKED receipts. It waits for terminal results, inspects receipts, and drains or cancels remaining writers after a race.

### Expected result

A consolidated table, evidenced findings, the selection rule, actual identities when exposed, and gaps.

### Dependencies and limits

Workers stay within host concurrency and isolate worktrees, data, and ports where needed. Cloud placement is not assumed. Measurements require exact SHAs, workloads, samples, and methods. Missing required coverage is not a pass.

[Full swarm instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/swarm/SKILL.md)

## TDD {#tdd}

You requested a failing regression test, or the bug has an obvious cheap local test target.

| Host | Example invocation |
| --- | --- |
| Codex | `$tdd Add a failing regression test for duplicate admission, then fix it and show the before-and-after result.` |
| Claude Code | `/tdd Add a failing regression test for duplicate admission, then fix it and show the before-and-after result.` |

### How it works

The agent identifies intended behavior and the smallest reproduction, selects an existing narrow test path, and runs the new test before changing production code. It verifies the failure cause, applies a focused fix, and reruns the regression and relevant nearby checks.

### Expected result

Named failing-before and passing-after evidence, or the reason that a practical failing test was unavailable and the closest executable check used.

### Dependencies and limits

Does not create broad harnesses, brittle mocks, expensive infrastructure, or unrelated fixtures to force TDD. Existing assertions are not weakened to match a bug. Deterministic checks are preferred for flaky behavior.

[Full tdd instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/tdd/SKILL.md)

## Teach {#teach}

You want to understand a subsystem or body of work at your own pace.

| Host | Example invocation |
| --- | --- |
| Codex | `$teach Teach me how queue coalescing works and why this project uses it.` |
| Claude Code | `/teach Teach me how queue coalescing works and why this project uses it.` |

### How it works

The agent uses how for mechanisms and scoped why research for rationale, then combines their findings in plain language. It starts with a small complete explanation and adds depth as you ask. Diagrams grow progressively when the flow or layout benefits from them.

### Expected result

The explanation itself, grounded in the real code and retaining why’s confidence language.

### Dependencies and limits

Read-only teaching does not change code. Narrow questions need less research. Broad questions may use bounded read-only slices. Unavailable diagram tools get a disclosed textual fallback. No quizzes or forced pacing.

[Full teach instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/teach/SKILL.md)

## Technical writing {#technical-writing}

You need documentation, an RFC, a README, or a review of technical prose.

| Host | Example invocation |
| --- | --- |
| Codex | `$technical-writing Review docs/install.md for clear reference structure and unambiguous instructions.` |
| Claude Code | `/technical-writing Review docs/install.md for clear reference structure and unambiguous instructions.` |

### How it works

The agent selects a Diátaxis mode, applies Google developer style, limits each sentence to a clear thought or instruction, and removes ambiguous syntax with Global English rules. It uses actual repository symbols and applies unslop to the writing.

### Expected result

Clearer technical writing with a consistent document purpose, concrete names, readable sentences, and preserved meaning.

### Dependencies and limits

The rules serve clarity rather than mechanical compliance. Product UI copy follows product guidelines. New jargon offenders are proposed with the diff, not silently added to unslop. Counts and trees must match the repository state.

[Full technical-writing instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/technical-writing/SKILL.md)

## TypeScript best practices {#typescript-best-practices}

You want TypeScript changes or review guided by explicit domain and boundary types.

| Host | Example invocation |
| --- | --- |
| Codex | `$typescript-best-practices Review src/admission.ts for invalid states, unsafe casts, and boundary validation.` |
| Claude Code | `/typescript-best-practices Review src/admission.ts for invalid states, unsafe casts, and boundary validation.` |

### How it works

The agent applies discriminated unions, validated brands, constructive types, and the simplest total representation where they improve correctness. It treats external data as unknown, prefers installed schemas and derived types, uses narrowing and exhaustiveness, and verifies behavior through real tests.

### Expected result

Scoped TypeScript findings or requested changes that encode valid states and validate data at entry points.

### Dependencies and limits

Uses principle-type-system-discipline when it changes a decision. New stronger types are justified where loose types force casts or impossible-state failures. Object arguments have hot-path exceptions. Shipped telemetry uses structured logging.

[Full typescript-best-practices instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/typescript-best-practices/SKILL.md)

## Unslop {#unslop}

Requested writing contains filler, jargon, repetitive phrasing, or other AI patterns.

| Host | Example invocation |
| --- | --- |
| Codex | `$unslop Rewrite this PR description in plain English while preserving its technical claims.` |
| Claude Code | `/unslop Rewrite this PR description in plain English while preserving its technical claims.` |

### How it works

The agent scans the stable pattern catalog and rewrites wording, structure, punctuation, and tone. It removes vague attribution and generic conclusions, preserves meaning, and keeps concrete mechanisms and necessary confidence qualifiers.

### Expected result

Edited text that matches the intended tone without changing its claims.

### Dependencies and limits

A style rewrite does not establish facts or authorize editing unrelated files. Pattern rules are stable identifiers used by companion skills.

[Full unslop instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/unslop/SKILL.md)

## Xray session {#xray-session}

You want to inspect observable zstack skills, plugin operations, hooks, and bundled helpers in the current session.

| Host | Example invocation |
| --- | --- |
| Codex | `$xray-session Show this session's zstack activity in chronological order with an ASCII diagram.` |
| Claude Code | `/xray-session Show this session's zstack activity in chronological order with an ASCII diagram.` |
| Hermes | `Load zstack:xray-session with skill_view and show this session's zstack activity in chronological order with an ASCII diagram.` |

For native plugins, select `zstack:xray-session` through the Codex skill picker or invoke `/zstack:xray-session` in Claude Code.

### How it works

The agent reviews available evidence from this session through your invocation, which becomes the report cutoff. It builds a chronological ledger with stable event IDs, positions, actors, outcomes, and sanitized evidence references. It preserves repeated occurrences and failed attempts, then renders an ASCII diagram whose parent links require recorded causal evidence. Report-generation operations fall after the cutoff.

### Expected result

A coverage statement, chronological ledger, ASCII diagram, and explicit gaps. This abbreviated example is illustrative; an actual report includes only supported events:

```text
Scope: current session, through xray-session invocation
Coverage: partial; earlier turns unavailable

ID   Position  Kind    Action                Outcome / evidence
E01  turn 4    skill   z-mode invoked        observed / turn 4 request
E02  turn 5    helper  bundled helper        failed   / turn 5 call 1
E03  turn 5    helper  bundled helper retry  success  / turn 5 call 3
E04  turn 8    skill   xray-session invoked  observed / turn 8 request

CURRENT SESSION
+-- E01 skill: z-mode
|   +-- E02 helper: attempt [failed]
|   \-- E03 helper: retry [success]
\-- E04 skill: xray-session [report cutoff]

Gap: no evidence available for turns 1-3.
```

### Dependencies and limits

Strictly explicit-only on every host, including inside z-mode: only a direct user request naming xray-session activates it. Generic session questions and transcript mentions do not. The report is read-only and stays in chat; invoking it does not enable collection, persist a transcript, or authorize delegation.

Uses z-mode's scoped history evidence guidance for this one current session. Complete coverage requires the full transcript through the cutoff; digests and compaction summaries cannot establish exhaustive counts. Unrecorded hooks and unavailable child-session detail remain gaps. Skill file reads, reported applications, hook context, and confirmed execution retain distinct labels. Sensitive arguments and hidden reasoning are excluded from the report.

### Optional event collection

For a native plugin installation, launch the host with `ZSTACK_XRAY=1` to record future supported hook events independently of z-mode. For example, in a POSIX shell:

```sh
ZSTACK_XRAY=1 codex
ZSTACK_XRAY=1 claude
ZSTACK_XRAY=1 hermes
```

In PowerShell, set `$env:ZSTACK_XRAY = '1'` before starting the host. A desktop or remote host must receive the variable in its actual execution environment; setting it in an unrelated terminal does not update an already-running app. Review the updated Codex hook definition through its native trust flow. Linked skills alone do not install these hooks.

Collection stores sanitized event metadata locally under the host's plugin data directory, in `xray/<host>/<session-id>/events/`. Hermes uses `plugin_data_dir("zstack")` in the active profile. It does not store raw prompts, commands, arguments, tool results, or transcripts. Generic tool records retain identifiers for later correlation; their presence does not make them zstack operations. Claude's direct command expansion and model `Skill` calls are separate paths; unsupported paths remain coverage gaps. Hermes attributes qualified `skill_view` names, records native lifecycle/tool/subagent metadata, and observes compression LLM requests. These auxiliary requests do not prove completed compaction; see [Hermes hook boundaries](../hosts/hermes.md#session-hooks).

Startup context provides a current-session read command when collection is enabled, or a compact reference when long paths would exceed the context budget. Xray merges records with available transcript evidence, pairs tool starts/results by native call IDs, and avoids counting the same operation twice. It reports partial capture, unsupported paths, malformed records, and unresolved calls. Missing actor or turn identity is separately flagged as ambiguous. Record timestamps describe capture time; they do not establish a global execution order.

To stop future collection, unset `ZSTACK_XRAY` and restart the host. Existing records remain available to xray. Delete only the intended `xray/<host>/<session-id>` directory in the verified plugin data root to remove a session's records; no automatic deletion occurs on clear or z-mode opt-out. Collection begins when enabled and cannot recover earlier activity. Codex recorder hooks check the opt-in in the shell before starting uv or Python. Claude tool-event recorder hooks run asynchronously, preserving shell-free Windows support: they still incur background process startup costs, but do not wait for the recorder before continuing tools. Other Claude lifecycle hooks remain synchronous. Disabled recorders exit without reading input or writing records. Async records can arrive after a report read, out of order, or be cancelled at host shutdown; transcript evidence and coverage gaps remain necessary. A collector error must not block the user's tool operation.

Hermes observers run in process and skip recording before inspecting event fields unless collection is enabled. Their callbacks return no tool-policy directives and catch capture failures so they cannot block a tool. The subprocess recorder limits each input to 256 KiB; all hosts limit each stored record to 4 KiB, with a soft cap of 10,000 event files per host/session. Concurrent writes can exceed that cap by the number of simultaneous handlers. Hitting the cap leaves a coverage marker. Interrupted writes and malformed records are reported on read. Other failures warn without raw payloads; an unwritable store cannot reliably record its own failure, so a clean read never proves complete capture. Files request owner-only permissions; Windows access also depends on the host's ACLs. Symlinked data paths are refused.

[Full xray-session instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/xray-session/SKILL.md)

## Why {#why}

You need design rationale, regression history, postmortem context, or evidence for a threshold.

| Host | Example invocation |
| --- | --- |
| Codex | `$why Why does the queue retain tied timestamps? Scope research to Git history and relevant PRs.` |
| Claude Code | `/why Why does the queue retain tied timestamps? Scope research to Git history and relevant PRs.` |

### How it works

The agent traces blame, renamed files, substantive commits, and PR discussion. It maps available evidence sources to relevant categories within the requested topic and time window. Broad independent sources may use read-only investigators. It reconciles citations and contradictions while separating direct evidence, conclusions, inference, speculation, and unknowns.

### Expected result

Cited facts, inferences, competing hypotheses when useful, source gaps, and actual sources searched. Before a change, it derives Preserve, Change, Avoid, and Risk constraints.

### Dependencies and limits

Uses how for runtime behavior. Authentication and connectors are not assumed. Unavailable and unsearched categories are reported. Research does not authorize contacting people or editing records.

[Full why instructions](https://github.com/fullerzz/agent-skills/blob/main/skills/why/SKILL.md)
