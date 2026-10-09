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

## Optional board plugin (experimental)

The repository root ships an optional Herdr plugin, `zstack.herdr`, with a terminal board, focus actions, and lifecycle hooks for runs a coordinator has explicitly enrolled. Linking it activates nothing: it does not select z-mode or Herdr execution, enroll runs, or write coordinator records. It was checked against Herdr 0.9.3 in an isolated server; treat it as experimental.

Requirements: Linux or macOS (the hooks lock with `fcntl`), Herdr 0.9.3 or later, `uv`, and Python 3.12 or later on the Herdr server's `PATH`. The board pane runs with [rich](https://rich.readthedocs.io/), which `uv` fetches the first time a board opens and caches; hooks and actions don't use it. Link the checkout itself, because orchestration-backed runs read `skills/z-mode/scripts/orch` relative to the plugin root:

```sh
herdr plugin link /path/to/zachs-agent-skills
herdr plugin action list --plugin zstack.herdr
```

Linking is global to your user and applies to every Herdr session. Remove it with `herdr plugin unlink zstack.herdr`. Whether to link or install it on your own Herdr, and whether to publish it, is your decision; zstack's installer never links, installs, or publishes it.

The board shows only runs enrolled with `integrations/herdr/herdr_run.py`: `init` creates and enrolls a run record, `enroll` registers an existing one, and `task add`, `task bind`, and the other `task` updates maintain it. Inside Herdr, for runs without an orchestration store, `task accept`, `task reject`, and `task evidence` run only from the pane bound as the run's coordinator, and never from a pane that is also bound to one of its tasks; after a restart, rebind it first with `coordinator bind`. A run with no coordinator binding refuses only panes bound to its workers. Orchestration-backed runs record acceptance and evidence in the orch store instead. The plugin finds enrollments in the same registry as that helper: `$ZSTACK_HERDR_REGISTRY`, else `$XDG_STATE_HOME/zstack/herdr/runs`, else `~/.local/state/zstack/herdr/runs`. If the Herdr server runs with a different environment from the coordinator's shell, set the variable for both.

Run and task IDs use 1–80 ASCII letters, digits, dots, underscores, colons, or hyphens, beginning with a letter or digit. The task ID `coordinator` is reserved for the coordinator role. These limits also apply to orchestration unit IDs mapped as tasks; unsupported IDs produce a data gap and are never shortened into an ownership token. Enrollment identity is rechecked before board updates and focus; a changed run ID or endpoint keeps the previous board data visibly stale until the original enrollment is restored or a new board is opened for the new run.

| Action (plugin `zstack.herdr`) | Invoke from | Effect |
| --- | --- | --- |
| `open-board` | The coordinator's or a worker's pane | Opens the board in a new tab of that workspace without moving focus. From an unenrolled pane it shows a notification and opens nothing. |
| `focus-coordinator` | A worker pane | Re-validates the coordinator binding, then focuses it. |
| `focus-worker` | The coordinator pane of a run with one bound task | Focuses that worker. With several tasks, open task details in the board and press Enter. |

Invoke one from a shell with `herdr plugin action invoke open-board --plugin zstack.herdr`, or bind actions to keys with `type = "plugin_action"` entries, as described in Herdr's [plugin documentation](https://herdr.dev/docs/plugins/#keybindings). The board resolves its run from the pane `open-board` was invoked from, which it receives as `ZSTACK_BOARD_PANE` because Herdr tab panes take no target pane. If no run or more than one run binds that pane, it says so; with several runs, choose one by number. It never guesses.

The board refreshes the run record, any orchestration store, and the Herdr snapshot when it opens and every five seconds after that. Its Rich overview panel separates acceptance counts (accepted, rejected, pending) from observed lifecycle counts (working, blocked), and shows the coordinator and last hook reconcile. A highlighted problems panel calls out broken bindings, rejected or blocked tasks, missing reports, and data gaps. It previews up to three problems; longer lists appear below the task table.

The pane keeps a compact task table and an inspector visible together. At 110 columns or wider they sit side by side; narrower panes stack them. The table shows task IDs and titles, observed lifecycle, and acceptance. The pinned header shows run counts, coordinator, last successful read time in UTC, and prominent problems. Failed reads retain the last good view marked `STALE`. Full diagnostics follow the table and remain scrollable.

Select a row to inspect its full task ID, title, repository and worktree paths, binding and durable identity, separate lifecycle/orchestrator/reported/acceptance states, report references and availability, and evidence references with full revisions. Long values wrap. Supplied text is literal with terminal controls removed; report contents and remote references are not fetched. Selection follows the task ID through refreshes and reordering; removing that task clears selection.

| Key | Action |
| --- | --- |
| Row key (`1`–`9`, then letters excluding `c`, `q`, `r`) | Select a task |
| ↑ / ↓ or `[` / `]` | Previous / next task, including tasks beyond shortcut keys |
| Enter | Focus the selected task's worker |
| Tab | Switch scrolling between tasks and inspector |
| `+` / `-` | Scroll the active region down / up one line |
| Escape | Clear selection and reset scrolling |
| `c` | Focus the coordinator |
| `r` | Refresh now |
| `q` / Ctrl-C | Quit |

The board uses Rich's alternate-screen display. Each region has a line-position indicator, the active region is marked, and the key line stays visible. Selecting a task brings its row into view. Closing the pane also stops the board. Lifecycle observations and worker reports do not establish acceptance; acceptance remains a separate coordinator-owned record.

Focus is checked against a fresh snapshot first. It is allowed when a binding is `ok`, or `moved` with the same terminal and agent session. Herdr 0.9.3 focuses a pane by ID only while that pane hosts an agent, so a plain shell pane can't be focused from the board.

For validated bindings, the board also reports display-only pane metadata tokens under the source `zstack.herdr`: `zstack_run`, `zstack_role`, `zstack_task`, and `zstack_phase`. It never sets titles, agent names, or state labels, and it leaves other sources' tokens alone. To show the tokens, add `$zstack_task` or `$zstack_phase` to your Agent sidebar rows. See Herdr's [custom status labels](https://herdr.dev/docs/integrations/#custom-status-labels).

### Lifecycle hooks

Once linked, Herdr runs these hooks automatically: a startup hook after each server start, and event hooks on `pane.agent_status_changed`, `pane.exited`, `pane.moved`, `pane.closed`, and `workspace.closed` for every pane, enrolled or not. For an unenrolled pane a hook is a no-op that still pays one `uv` and Python startup (about 0.1 s). Each hook only triggers a reconcile: one Herdr snapshot, then an inspection of each enrolled run on that server whose bound or last observed panes (or workspace) the event names. Events for other panes write nothing. A reconcile never writes run records, the registry, or orchestration stores, never prompts, starts, or resends anything to an agent, and never records acceptance. Every Herdr call has a five-second timeout, and the hook exits when the reconcile ends.

Results are stored as plugin-owned observations in `$HERDR_PLUGIN_STATE_DIR/<endpoint key>/<run id>.json`: the last reconcile time and trigger, each binding's observed status, pane, workspace, and agent status, and the panes that carry the run's tokens. If any read fails, the observation keeps its previous state and records the error as `stale`. The board shows the last reconcile time and trigger, but it does not depend on hooks: its own five-second refresh shows missed events.

After each successful reconcile or board refresh, the run's tokens appear only on panes with an `ok` or `moved` binding. The plugin compares against the pane's live tokens, so a repeated event or refresh sends nothing. When a binding becomes `occupant changed` or the pane disappears, the plugin clears its own token keys with `--clear-token` under the source `zstack.herdr`. When a pane's role changes, for example a former worker pane rebound as the coordinator, it also clears the keys the new role doesn't use, such as `zstack_task`. It clears only panes whose `zstack_run` token names that run, and it leaves other token keys alone. A pane that holds more than one of a run's bindings, such as the coordinator and a task or two tasks, gets none of that run's tokens. If a source read fails, it changes no labels.

Overlapping hooks share a lock in the state directory. A hook that finds the lock held skips its run, and the next event or the board catches up. Startup hooks run after a server start or live handoff, not when a client attaches or the plugin is linked or enabled. After a server restart, Herdr gives restored panes new terminals, so their bindings show `occupant changed` until the coordinator binds them again (`task bind` for workers); the plugin never rebinds. Rebind the coordinator with `uv run --script integrations/herdr/herdr_run.py coordinator bind RUN_FILE --pane P`, for ordinary or orchestration-backed runs. Herdr 0.9.3 can report a restored pane's pre-restart agent session for the fresh agent it hosts; when a rebind sees a new terminal with the previous binding's session, it records no session and prints a warning, so that binding is checked by terminal and agent kind only. Herdr does not restore metadata tokens after a restart.

When a run ends, run `uv run --script integrations/herdr/herdr_run.py unenroll RUN_FILE`. It clears the plugin's labels from every pane whose `zstack_run` token names the run, then deletes the registry entry; if Herdr can't be read or a clear fails, it keeps the entry. Until then, hooks and boards keep reconciling the run and can relabel panes whose bindings still validate. A hook already running can relabel a pane just after the clear; running `unenroll` again clears leftover labels even after the entry is gone. Nothing deletes observations. Afterwards, remove `$HERDR_PLUGIN_STATE_DIR/<endpoint key>/<run id>.json`, or the whole `<endpoint key>/` directory after unlinking (by default on macOS, under `~/.local/state/herdr/plugins/zstack.herdr/`). That directory holds only plugin observations and a lock file. A pane bound by two enrolled runs keeps the labels of whichever run labeled it first until that run's binding there stops validating or the run is unenrolled. Labels naming a run that is no longer enrolled don't block another run from labeling the pane.
