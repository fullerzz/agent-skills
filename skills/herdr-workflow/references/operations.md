# Herdr execution

Use this after the entrypoint's environment check. The installed binary and current server are the authority for supported syntax. The examples below follow the [agent automation docs](https://herdr.dev/docs/agent-automation/) and [upstream operational skill](https://raw.githubusercontent.com/herdrdev/herdr/master/skills/herdr/SKILL.md), reviewed 2026-10-04.

## Discover and assign

Run `herdr --help`, then the relevant command group (`herdr agent`, `herdr pane`, or `herdr worktree`) for help. Do not probe a mutating command by omitting arguments. Check `herdr status` before relying on newer server features; a client upgrade does not prove the server supports them.

Resolve the caller with `herdr pane current --current` before creating work. `HERDR_ENV=1` alone does not prove the inherited pane still exists. If resolution fails, report stale/unavailable caller context and stop dependent operations; do not fall back to the user's focused pane or guess a replacement ID.

Use the calling pane's context, explicit returned IDs, or unique live agent names. Never target another client's focused pane by default. Inspect current layout and task-owned agents before creating work. Names identify live occupants, not durable task identities; keep a separate task ID.

Default to a sibling pane in the caller's tab and working directory, with `--no-focus`. Inspect geometry and split right for a wide pane or down for a narrow/tall pane. Create a different workspace, tab, cwd, or worktree only within the user's requested topology/location. Panes share filesystem access: writers need exclusive files or authorized isolated worktrees. If neither is available, serialize writers. A named session is for a separate runtime namespace, not every task.

```sh
herdr pane layout --pane "$HERDR_PANE_ID"
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

Read the new pane ID from `.result.pane.pane_id`. Workspace and tab creation already return a root pane; use it before splitting again. After moving a pane, update the roster from `.result.move_result.pane.pane_id`; prior IDs are not general targets.

One coordinator owns the roster and topology. Start with at most 2-3 useful independent workers and stay within the user budget and host limits. Count native and Herdr workers together; separate terminals do not create an exemption from concurrency or delegation restrictions. Workers do not spawn coordinators unless explicitly assigned that authority.

## Launch and collect

`agent start` needs an existing available shell pane. Select the user-requested supported CLI kind; otherwise use the coordinator's host kind if available. Keep that CLI's configured model defaults unless the user requests an override, and report that these are independent defaults rather than inherited parent settings. Do not copy hard-coded model examples from documentation. Native role files may not be available to the new CLI; supply the role as a scoped brief and disclose any role fallback.

The following placeholders stand for IDs and names observed or assigned for this task:

```sh
herdr agent start <unique-name> --kind <supported-kind> --pane <returned-pane-id>
herdr agent prompt <unique-name> "<consolidated assignment>" --wait --timeout 60000
herdr agent get <unique-name>
herdr agent read <unique-name> --source recent-unwrapped --lines 120
```

Only one outstanding assignment per agent. Prompt an agent ready for input; do not queue a second task into a working agent and treat completion of the first turn as acceptance of the second. For ongoing work, continue with bounded `agent wait` calls, not another prompt. Default waits settle at `idle`, `done`, or `blocked`; use `--until` only when exact states matter. `unknown` requires inspection. Keep the user informed between bounded waits.

Startup can leave an agent blocked even when `agent start` reports an error. Inspect the named agent before launching a replacement. On timeout, `agent_prompt_stalled`, or a transport failure, inspect state and output before retrying: input may already have been delivered. A replacement writer starts only after the old writer is confirmed stopped/drained or receives a separate write scope.

Inspect blocked dialogs with a visible read. Do not approve trust, credentials, permissions, or expanded scope through terminal keys without the necessary user authority. Use `agent send-keys` for deliberate interactive UI actions; do not bypass blocked-agent checks with raw pane input.

`idle`/`done` are readiness states, not successful task verdicts. Read the completed report and inspect artifacts against the assignment. A larger recent read may recover supported idle-agent history; use a visible read while working/blocked. If output remains incomplete, ask the agent to write its result to a task-scoped temporary Markdown file and read it on that machine. Record missing evidence if collection fails.

## Supporting processes

Use `pane run`, `pane read`, and `pane wait-output` for tests, servers, and watchers. Use agent commands for coding agents so occupant identity and lifecycle checks remain active. For ordinary commands, collect an exit status and fresh run-specific output or artifact; `pane wait-output` can match old text immediately. Do not infer a passing test from an old success line or server readiness message.

Keep small checks in the coordinator's normal execution tool. Use visible panes when process duration, interactive debugging, or continued inspection makes them useful. Preserve the caller's focus and record which processes the task created.

## Pickup, pause, and cleanup

On pickup, reconcile the roster with live state before prompting anything. Check endpoint, current occupant, repository/worktree, branch, revision, dirty files, assignment, and available evidence. A restored pane or conversation does not prove an assignment is still running or finished. Never automatically resend the recorded prompt.

Retain panes when their running servers/watchers or agent-held state are costly to recreate. For new tasks and retries, use a fresh agent under the shared lifecycle rules; pane persistence is not permission to reuse a stale conversation. Finish or stop the previous writer before replacement.

An explicit pause/stop drains or interrupts assigned workers, confirms their state, and saves unfinished work. Detaching a client leaves processes running; it is suitable only when continued work remains authorized. Record any process that could not be stopped. Never stop the Herdr server to pause this task.

Before clearing execution preference or switching methods, account for outstanding agents and supporting processes. Close only task-created panes that no longer contain needed work; preserve unrelated panes and user focus. Do not remove worktrees or discard changes as cleanup without covered authority.

The handoff records execution preference, machine/session, task and live identifiers, CLI kind, write scope, artifact paths, checks, acceptance, remaining processes, and first resume action. Keep native conversation references only when exposed and relevant. Herdr's [restore documentation](https://herdr.dev/docs/session-state/) distinguishes live detach from server restart: restart loses original processes and conversation recovery depends on supported native integration. Do not promise unattended coordination after the coordinator exits.

## Requested remote work

Work runs on the machine owning the Herdr server and repository. Record the endpoint with every ID; different servers may reuse the same pane or agent name. Keep one explicit endpoint selector across discovery and later commands. Selecting a different machine in the TUI does not retarget an existing pane's CLI context.

For saved-machine forwarding, verify both installations support it and discover IDs on that target; do not use local `--current` as remote identity. Resolve artifact paths on the owning machine. After connection failure, inspect before retrying mutations. Never install, upgrade, restart a remote server, create profiles, or broaden credentials merely to recover a workflow. Missing remote capabilities remain explicit gaps.
