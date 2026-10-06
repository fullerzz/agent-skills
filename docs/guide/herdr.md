# Use Herdr with existing workflows

[Herdr](https://herdr.dev/docs/) manages terminal workspaces, panes, and coding agents. When you explicitly enable Herdr execution in zstack, the selected playbook uses it for authorized workers and useful long-running tests, servers, and watchers. Feature work still follows the feature playbook; investigation, orchestration, and pause/pickup keep their own scope and acceptance checks. Small tasks and brief checks stay direct.

## Enable it for a session

1. Install and configure Herdr using its [documentation](https://herdr.dev/docs/), and make the intended coding-agent CLI available on the machine where work will run.
2. Start your coordinating agent inside a live Herdr pane in the target repository. The integration requires `HERDR_ENV=1` and a resolvable caller pane, plus a compatible CLI/server. Enabling the preference does not attach an existing outside session to Herdr.
3. Load z-mode explicitly and request Herdr execution. With the Codex plugin, select `zstack:z-mode` in the skill picker and say “Use Herdr execution for this session, then fix the reconnect bug.” In Claude Code, use `/zstack:z-mode` with that request. In Hermes, ask to load `zstack:z-mode` through `skill_view` and enable Herdr execution.

For linked installations, use `$z-mode` in Codex or `/z-mode` in Claude Code. To select execution without z-mode, explicitly invoke `herdr-workflow` and ask to enable Herdr execution. Inspecting Herdr once, discussing this integration, or installing zstack does not enable it for future work.

The native plugin hooks remember the selection for the same session ID. Linked installations and older hooks preserve it through conversation and handoff notes instead; see the [Codex](../hosts/codex.md#herdr-execution), [Claude Code](../hosts/claude-code.md#herdr-execution), and [Hermes](../hosts/hermes.md#session-hooks) setup pages for host details.

### Known Codex shared-daemon issue

Codex 0.157+ can run hooks and tool commands in a shared background app-server daemon that retains the `HERDR_*` environment of the terminal that started it. Later sessions can receive stale pane or workspace IDs, producing `pane_not_found`, or target another pane or server. In a [maintainer comment on Herdr issue #4649](https://github.com/herdrdev/herdr/issues/4649#issuecomment-5869269080), Herdr's maintainer explains that the project is waiting for a Codex fix and recommends the workaround below.

Until then, launch each coordinating or worker Codex CLI inside its intended Herdr pane with `--no-daemon`, including when resuming:

```sh
codex --no-daemon
codex --no-daemon resume <session-id>
```

This bypasses an already-running daemon. Disabling `daemon_auto_start` alone does not bypass it. Keep the caller-resolution check; do not substitute the user's focused pane when it fails.

## What changes during work

| Part of the workflow | With Herdr enabled |
| --- | --- |
| Routing | Z-mode chooses the normal playbook and loads the Herdr companion alongside it. |
| Delegation | Authorized workers run as independent CLI sessions in task-owned panes. Enabling Herdr alone does not request extra workers. |
| Ownership | The coordinator records assignments, agent/pane IDs, machine/session, repository or worktree, write scope, and acceptance evidence. Panes share the filesystem; they do not isolate writes. |
| Supporting commands | Long-running tests, servers, and watchers can use visible panes. Brief checks remain in the coordinator's normal tools. |
| Completion | The coordinator reads worker output, inspects artifacts, and performs the playbook's checks before accepting the result. |

For example, “Use z-mode with Herdr to fix the reconnect bug and verify recovery” keeps the bug-fix workflow. If that workflow delegates an investigation, its worker receives a scoped brief in a Herdr pane. A useful long-running test may get another pane. The coordinator still verifies the fix and reports the tested revision and any evidence gaps.

Workers need their own context, role, allowed actions, stop condition, and reporting instructions. They do not inherit the coordinator's conversation, model settings, permissions, tools, or mode/execution selection. Host restrictions and concurrency limits still apply. The coordinator preserves user focus and uses the caller's existing tab and working directory by default; different workspaces, locations, or worktrees follow the requested scope.

## Turn it off, pause, or resume

| Request or event | Preference behavior |
| --- | --- |
| “Enable Herdr execution” | Selects Herdr without activating z-mode. |
| “Use z-mode with Herdr” | Selects both. |
| “Disable Herdr execution” | Returns to native execution while retaining z-mode. |
| “Stop z-mode” or switch away from active z-mode | Clears both preferences. A Herdr-only selection is independent of a style switch. |
| Resume with the same session ID | Updated native hooks restore the stored preferences. |
| New child, fork, or rotated session ID | Starts without inherited selection; explicitly select again. |
| Session clear/reset | Clears both for the affected session. |

These controls change preferences, not processes. Before changing execution methods, the coordinator accounts for assigned workers and supporting processes. A pause drains or interrupts task workers, confirms their state, and saves unfinished work. It does not stop the entire Herdr server or close unrelated panes.

Detaching a Herdr client leaves processes running. It is appropriate only when continued work remains authorized, and does not keep an exited coordinator working. A server restart loses the original processes; conversation recovery depends on supported native integrations. See Herdr's [session state and restore documentation](https://herdr.dev/docs/session-state/).

On pickup, reconcile the saved roster with live endpoints, occupants, branches, dirty files, and evidence before sending another prompt. Do not automatically resend an old assignment. The handoff records the execution preference, outstanding work, remaining processes, artifact paths, and first resume action. See [long work and handoffs](04-long-work.md).

## When execution cannot continue

If the session is outside Herdr, the caller pane is stale, or the selected CLI/server capability is unavailable, the coordinator reports the missing capability and asks for an explicit fallback for affected work. It does not silently dispatch native workers or target whichever pane the user has focused. Independent direct work can continue.

A blocked agent may need input or approval; inspect its dialog within the existing task authority. After a prompt timeout or transport failure, inspect state and output before retrying because the assignment may already have arrived. Herdr's `idle` and `done` states indicate readiness, not verified task success. Test results need a fresh run and exit status; a matching terminal line may be old output.

The [validation record](../validation.md#herdr-execution-integration-—-2026-10-04) distinguishes tested hook and packaging behavior from live orchestration checks that remain unverified.

## Further reading

- [Herdr documentation](https://herdr.dev/docs/), including [concepts](https://herdr.dev/docs/concepts/), [how to work](https://herdr.dev/docs/how-to-work/), and [agent automation](https://herdr.dev/docs/agent-automation/).
- [Herdr workflow reference](../reference/workflow-skills.md#herdr-workflow) for invocation and dependencies.
- [Operational instructions](../../skills/herdr-workflow/references/operations.md) for launch, collection, cleanup, and requested remote work.
