# Plan: optional zstack Herdr plugin

Status: implemented and locally verified through Phase 9 plus a final review, 2026-10-07. This document authorizes no installation or publication.

## Outcome

Give an explicitly enrolled zstack run a visible task board in Herdr, contextual actions, and lifecycle bookkeeping. A user should be able to identify which task owns each worker, find blocked or interrupted work, and open its report and verification evidence without inspecting every terminal.

Done when an isolated live run demonstrates these behaviors, including recovery from stale bindings, while preserving unrelated panes and keeping observed agent status separate from coordinator acceptance. Existing zstack workflows must continue to work without the plugin.

## Scope

Build a small companion to [herdr-workflow](../skills/herdr-workflow/SKILL.md), not a replacement for z-mode, native host plugins, or the coordinating agent. Herdr plugins use the existing CLI/API; their value is registered entrypoints, supplied invocation context, lifecycle triggers, terminal views, and distribution.

The first version includes:

- Explicit enrollment of a run and bindings between its tasks, workers, panes, repositories/worktrees, and report paths.
- Actions to inspect the current run, open its board, and focus a validated task-owned worker or coordinator.
- A terminal board and optional metadata labels for task, role, and phase.
- Event/startup reconciliation and board refresh that update observed runtime state without dispatching new assignments or accepting results.

Defer worker launching, automatic retries, dependency scheduling, cross-machine aggregation, URL-triggered workflows, and unattended controllers. More reliable launching alone can be implemented as a shared helper without a Herdr plugin.

Installation or Herdr-wide enablement must not activate z-mode, select Herdr execution, or enroll unrelated sessions. Preserve explicit session selection, concurrency limits, write ownership, and separate authorization for commits, publication, messages, and cleanup. This request creates only the plan document.

## Integration design

Keep three responsibilities distinct:

| Component | Responsibility |
| --- | --- |
| Skills and native host hooks | Playbook selection, session preferences, worker briefs, and host-specific capabilities. |
| Herdr adapter | Resolve context, correlate task identity with live occupants, observe lifecycle, and present run state. |
| Coordinator and existing task artifacts | Assign work, own acceptance decisions, verify artifacts, and record evidence. |

Reuse [the orchestration helper](../skills/z-mode/scripts/orch/orch.py) and its units, inbox pointers, gates, and evidence ledger when a workflow already uses them. Map these records into the board's task-data contract; add only missing Herdr bindings, and display unmapped acceptance as not recorded. Do not duplicate acceptance or evidence into a second database.

For workflows without an orchestration store, use a versioned `herdr-run.json` in the existing coordinator-owned task directory. Define its schema in Phase 1: run ID, coordinator identity, update timestamp, and task records containing task ID/title, Herdr binding, repository/worktree, report references, acceptance (`not recorded`, `accepted`, or `rejected`), and verification evidence references with the tested revision when applicable. This record is the source of task data; do not parse conversation or free-form Markdown to infer acceptance.

The coordinator creates and atomically updates this record through explicit enrollment/update helper operations after assignment, report registration, and acceptance decisions. Workers supply reports or report pointers; they do not update acceptance. Missing acceptance displays as not recorded, and malformed or unavailable records produce a visible data gap. Board reads and lifecycle hooks never change coordinator-owned records.

Use non-mutating helper methods or validated file reads for orchestration stores. Do not use `orch status --json`, which takes a write lock and rewrites `status.md`, or `inbox drain`, which consumes pointers. Verify that inspection creates, modifies, or deletes no coordinator artifacts.

Bindings need a durable run/task ID, owning endpoint/session, repository/worktree, pane and observed occupant identity, and report references. Live agent names and pane IDs are not durable task identity. Namespace plugin-owned bindings by endpoint/session and run because plugin installation and its data directories are shared across Herdr sessions.

Display lifecycle state and acceptance independently: an idle worker can still have an unverified result. Record uncertainty explicitly when a pane is missing, an occupant changed, or evidence is unavailable. Persist bindings and evidence pointers, not copied conversations or terminal transcripts.

Refresh task artifacts and authoritative Herdr snapshots on board open and every five seconds while the board is open, with bounded API timeouts and no overlapping refreshes. Show the last successful read time for each source; retain a visibly stale snapshot on read failure rather than presenting it as current. Closing the board stops its refresh loop. Events may trigger earlier reconciliation, but artifact updates and missed events must be discovered without a lifecycle hook or restart. Startup hooks do not run on client attach, plugin link, or plugin enable.

## Phases

### 1. Establish task records, bindings, and read-only inspection

- Depends on: Review of this proposal and explicit authorization to implement.
- Files: Proposed `integrations/herdr/` adapter, enrollment/update helper, and focused tests; existing `skills/z-mode/scripts/orch/` read interfaces; coordinator-owned `herdr-run.json` for non-orchestration runs. All implementation paths here are proposed.
- Acceptance: The task-data schema and coordinator update operations are defined and validated. Explicit enrollment associates a run with live resources. Both orchestration and ordinary runs expose task, acceptance, and evidence without prose parsing or duplicated authoritative state. Inspection rejects ambiguous or stale targets and never mutates coordinator artifacts.
- Verification: Temporary fixtures cover enrollment/update roundtrips, missing or malformed acceptance, evidence references, endpoint/session collisions, reused names, changed occupants, moved panes, missing reports, and unrelated runs. Compare coordinator files and directory contents before and after inspection to detect writes, lock creation, or consumed pointers. Use the repository's unittest harness; no personal configuration or live worker dispatch.

### 2. Register contextual actions and a terminal board

- Depends on: Phase 1's identity and inspection contract.
- Files: Proposed root `herdr-plugin.toml` and `integrations/herdr/` entrypoints; `docs/guide/herdr.md` for optional setup. Confirm installation includes referenced shared resources before fixing the package layout.
- Acceptance: Actions resolve an explicitly enrolled run from invocation context. The board shows task, worker, worktree, lifecycle, acceptance, evidence, and source freshness. Refresh-on-open and the five-second refresh loop read both runtime snapshots and task artifacts. Failed reads are visibly stale; closing the board stops refresh. Focus actions validate the current binding. Metadata reporting preserves user styling and unrelated tokens.
- Verification: Link the candidate in a disposable Herdr environment. Exercise the board, focus actions, no-enrollment behavior, and multiple runs. With a worker remaining idle, update its acceptance/evidence and report file without a Herdr event; verify the open board reflects the change on its next successful refresh. Exercise read failures and refresh shutdown. Use a normal pane placement for a persistent board; reserve popups for temporary inspection because popups are outside agent/pane APIs. Confirm underlying caller context and preserve user focus unless a focus action was selected.

### 3. Add lifecycle and startup reconciliation

- Depends on: Phases 1 and 2.
- Files: Proposed manifest hooks and adapter reconciliation code; focused fixtures for repeated events and recovery.
- Acceptance: Supported status, exit, move, and close hooks affect only enrolled bindings and plugin-owned observations. Startup reconciliation queries current snapshots. Board refresh recovers missed events without requiring restart. Duplicate or missed events cannot produce duplicate assignments, false acceptance, or changes to coordinator records or unrelated work.
- Verification: Fixtures exercise duplicate events, stale state, concurrent observations, and snapshot reconciliation. Drop a worker's final lifecycle event and verify the open board recovers from a snapshot refresh. In a disposable session, exercise blocked/idle transitions, pane movement/closure, detach/reattach, and restart. Reconcile before interpreting restored panes; never automatically resend an assignment. Hooks are triggers, not a durable event journal or a supervised daemon.

### 4. Validate packaging and document actual coverage

- Depends on: Phases 1 through 3.
- Files: Optional Herdr packaging integration, `docs/guide/herdr.md`, and `docs/validation.md`; existing native packaging and installation code only if demonstrated necessary.
- Acceptance: A clean package resolves resources from its installed location, including paths with spaces. Native zstack installation and plugin-free workflows still work. Record demonstrated minimum Herdr capabilities, tested host versions, live results, and gaps.
- Verification: Run `uv run scripts/validate.py`, `node --test scripts/*.test.mjs`, and `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'` after structural changes. Use isolated install/package fixtures and live checks from Phases 2 and 3. The Node documentation tests include a site build. Record actual host checks in `docs/validation.md`; static passes do not establish live behavior. Publication and personal installation remain separate actions.

## Risks

- Events may be missed, repeated, or interrupted by reconnect/handoff; task artifacts can change without any Herdr event. Refresh both sources, expose freshness/read failures, and retain uncertainty rather than replaying assumed history.
- Invocation context can become stale, and different servers can reuse identifiers. Validate endpoint, live occupant, and task ownership before targeting anything.
- Native session identity and lifecycle coverage vary by agent integration. Use exposed identity when available; report gaps instead of inferring conversation continuity.
- Plugin v1 provides terminal entrypoints, not arbitrary native sidebar widgets. Metadata labels require user configuration; the initial board should remain a simple terminal view.
- Plugin commands run as the user, and storage schemas/cleanup belong to the plugin. Keep the initial adapter observational and avoid automatic deletion or transcript collection.
- Existing local validation does not establish a complete live Herdr orchestration result. A disposable session with a valid caller pane is required for the proposed live checks.

## Handoff

Current state: Phases 1–4 are implemented in the working tree on branch `herdr-plugin` (base `29f5bfa`), uncommitted. The coordinator accepted each phase after rerunning the repository checks; live checks ran on isolated Herdr 0.9.3 servers with simulated agents. See the [validation record](validation.md#herdr-board-plugin-—-2026-10-06) for actual coverage and gaps, and the [guide](guide/herdr.md#optional-board-plugin-experimental) for setup.

Continuation: missing orchestration resources now produce a data gap, and `coordinator bind` provides restart recovery. An independent review's four findings were repaired: enrollment identity drift, stale board labels after missed hooks, oversized metadata identifiers, and the reserved coordinator task ID. Fresh checks passed all 165 Python tests, 15 Node tests, structural validation, Ruff, and whitespace checks; the personal plugin registry hash matched its baseline.

Phase 7 ran from a verified managed Herdr caller with fresh Codex agents launched using `codex --no-daemon`. An isolated Herdr 0.9.3 server demonstrated real working/idle hooks, board lifecycle with acceptance still `not recorded`, labels and focus, and a real restart that rejected the stale coordinator until explicitly rebound to a fresh native session. Run/registry bytes and timestamps were preserved between coordinator writes. Every disposable process stopped; the personal server/configuration remained unchanged. No product defect required a code change. See the [Phase 7 validation record](validation.md#phase-7-real-codex-and-coordinator-restart-checks-—-2026-10-06). Phase 8 ran a real Claude Code worker on another isolated server. It drove working/idle hooks, the board, labels and worker focus, and a real Claude permission dialog produced a `blocked` state observed by the hook, observation, and board before the dialog was cancelled, never approved. See the [Phase 8 validation record](validation.md#phase-8-real-claude-and-blocked-state-checks-—-2026-10-06). Phase 9 bound a real Claude coordinator: board `c` and the focus action reached it, a real restart left it `occupant changed` and unfocusable, and an explicit `coordinator bind` to a fresh Claude restored it. Herdr kept reporting the pre-restart session for the fresh process, so rebinds now record no session when a new terminal reports the previous binding's session. A final review's six findings were repaired with regression tests. See the [validation record](validation.md#herdr-plugin-pre-landing-review-and-repairs-—-2026-10-07). Question/trust dialogs as blocked sources and native resume remain unverified; remote/install/detach checks remain outside the completed assignments.

The user controls commits, personal installation, publication, and merge; this plan grants none of those actions. Reconsider deferred features only after real use shows a concrete need.

## References

- [Herdr plugin contract](https://herdr.dev/docs/plugins/): manifests, actions, context, hooks, terminal entrypoints, storage, and trust.
- [Agent automation](https://herdr.dev/docs/agent-automation/): occupant identity, prompting, waits, and lifecycle limitations.
- [Socket event subscriptions](https://herdr.dev/docs/socket-api/#event-subscriptions): event loss and reconciliation.
- [Custom status labels](https://herdr.dev/docs/integrations/#custom-status-labels): metadata reporting alongside official agent integrations.
- [Session state and restore](https://herdr.dev/docs/session-state/): detach, restart, native resume, and handoff boundaries.
