# Use Herdr with existing workflows

Herdr-core (`hc`) runs terminals and coding agents; herdr-app presents them. When you explicitly enable Herdr execution in zstack, the selected playbook uses it for authorized workers and useful long-running tests, servers, and watchers. Feature work still follows the feature playbook; investigation, orchestration, and pause/pickup keep their own scope and acceptance checks. Small tasks and brief checks stay direct.

## Enable it for a session

1. Install and configure herdr-core / herdr-app and the [herdr-zstack plugin](https://github.com/fullerzz/herdr-zstack), and make the intended coding-agent CLI available on the machine where work will run.
2. Start your coordinating agent inside a live hc terminal in the target repository. Native detection requires `HC_TERMINAL_ID`, a live caller resolved by `hc get "$HC_TERMINAL_ID"`, and an answering `hc server status` on the same core. `HERDR_ENV` is legacy diagnostic context only. Use the companion’s read-only preflight; hc discovery can start an absent core. Enabling the preference does not attach an existing outside session to Herdr.
3. Load z-mode explicitly and request Herdr execution. With the Codex plugin, select `zstack:z-mode` in the skill picker and say “Use Herdr execution for this session, then fix the reconnect bug.” In Claude Code, use `/zstack:z-mode` with that request. In Hermes, ask to load `zstack:z-mode` through `skill_view` and enable Herdr execution.

For linked installations, use `$z-mode` in Codex or `/z-mode` in Claude Code. To select execution without z-mode, explicitly invoke `herdr-workflow` and ask to enable Herdr execution. Inspecting Herdr once, discussing this integration, or installing zstack does not enable it for future work.

The native plugin hooks remember the selection for the same session ID. Linked installations and older hooks preserve it through conversation and handoff notes instead; see the [Codex](../hosts/codex.md#herdr-execution), [Claude Code](../hosts/claude-code.md#herdr-execution), and [Hermes](../hosts/hermes.md#session-hooks) setup pages for host details.

## Companion discovery

Zstack retains the single session hook, Enable / Disable / Herdr / Native controls, and stored `.herdr` preference. Herdr-zstack adds no second selection hook. The hook resolves `herdr-zstack:hc-workflow` for the current host; z-mode and its shared contract load that companion for native operations.

Codex discovery checks `$CODEX_HOME/plugins/cache/*/herdr-zstack/*/skills/hc-workflow/SKILL.md` (default `~/.codex`) and linked `~/.agents/skills/hc-workflow`. Claude discovery uses `installed_plugins.json` under `$CLAUDE_CONFIG_DIR/plugins` (default `~/.claude`), including directory-marketplace sources, and linked `skills/hc-workflow` in that configuration directory. Paths are canonicalized; multiple distinct candidates are reported as ambiguous rather than choosing a cached version. Other installation layouts, including Hermes, require resolution through the host’s installed skill catalog.

If the companion is missing or ambiguous, report the capability gap and stop dependent Herdr work. Never fall back to the legacy `herdr pane` / `herdr agent` commands. Installation or configuration changes need their own authorization. Neither the hook nor preference controls run hc discovery or launch processes.

## What changes during work

| Part of the workflow | With Herdr enabled |
| --- | --- |
| Routing | Z-mode chooses the normal playbook and loads herdr-zstack:hc-workflow alongside it. |
| Delegation | Authorized workers run as independent CLI sessions in task-owned hc terminals. Enabling Herdr alone does not request extra workers. |
| Ownership | The coordinator records assignments, terminal addresses, machine/session, repository or worktree, write scope, and acceptance evidence. Terminals share the filesystem; they do not isolate writes. |
| Supporting commands | Long-running tests, servers, and watchers can use visible terminals. Brief checks remain in the coordinator's normal tools. |
| Completion | The coordinator reads worker output, inspects artifacts, and performs the playbook's checks before accepting the result. |

For example, “Use z-mode with Herdr to fix the reconnect bug and verify recovery” keeps the bug-fix workflow. If that workflow delegates an investigation, its worker receives a scoped brief in an hc terminal. A useful long-running test may get another terminal. The coordinator still verifies the fix and reports the tested revision and any evidence gaps.

Workers need their own context, role, allowed actions, stop condition, and reporting instructions. They do not inherit the coordinator's conversation, model settings, permissions, tools, or mode/execution selection. Host restrictions and concurrency limits still apply. The coordinator preserves user focus and follows the companion’s caller topology and working-directory rules; different layouts, locations, or worktrees follow the requested scope.

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

These controls change preferences, not processes. Before changing execution methods, the coordinator accounts for assigned workers and supporting processes. A pause drains or interrupts task workers, confirms their state, and saves unfinished work. It does not stop the entire Herdr server or close unrelated terminals.

Closing an app view can leave core processes running; follow the companion’s lifecycle guidance. It is appropriate only when continued work remains authorized, and does not keep an exited coordinator working. A server restart loses the original processes; conversation recovery depends on supported native integrations. See the [native worker lifecycle](https://github.com/fullerzz/herdr-zstack/blob/main/docs/worker-lifecycle.md).

On pickup, reconcile the saved roster with live endpoints, occupants, branches, dirty files, and evidence before sending another prompt. Do not automatically resend an old assignment. The handoff records the execution preference, outstanding work, remaining processes, artifact paths, and first resume action. See [long work and handoffs](04-long-work.md).

## When execution cannot continue

If the hc companion is missing, the session is outside hc, the caller terminal is stale, or the selected CLI/server capability is unavailable, the coordinator reports the missing capability and asks for an explicit fallback for affected work. It does not silently dispatch native workers or target whichever terminal the user has focused. Independent direct work can continue.

A blocked agent may need input or approval; inspect its dialog within the existing task authority. After a prompt timeout or transport failure, inspect state and output before retrying because the assignment may already have arrived. A ready terminal does not prove task success. Test results need a fresh run and exit status; a matching terminal line may be old output.

The [validation record](../validation.md#native-hc-companion-routing) distinguishes tested hook and packaging behavior from live orchestration checks that remain unverified.

## Further reading

- [Native execution contract](https://github.com/fullerzz/herdr-zstack/blob/main/docs/execution-contract.md) for capability preflight and runtime limits.
- [Herdr workflow reference](../reference/workflow-skills.md#herdr-workflow) for invocation and dependencies.
- [Operational instructions](../../skills/herdr-workflow/references/operations.md) for launch, collection, cleanup, and requested remote work.
