# Long work and conventions

## Run long work

Give [autonomous-run](../../skills/z-mode/playbooks/autonomous-run.md) a checkable predicate, scope, and budget. It works while the session is alive.

::: info No replacement daemon
Native background or scheduling features can be used when verified and requested; this library supplies no replacement daemon.
:::

[Orchestrate](../../skills/z-mode/playbooks/orchestrate.md) coordinates workers around owned task state, using native execution by default or [Herdr when explicitly enabled](herdr.md). [show-me-your-work](../../skills/show-me-your-work/SKILL.md) keeps an append-only TSV trail.

## Earn trust before unattended work

Before leaving a repeated workflow running:

- Do the task once yourself or watch an agent complete it, so the success condition is concrete.
- Give the agent the tools and signals needed to verify it: the app harness, logs, profiler, or stored state.
- Require evidence at every stage and let a failed check stop the run.
- Inspect a few run records and turn repeated failures into tools or automated checks.

Until those checks hold, supervise the run. Give unattended work an isolated write scope, an explicit action budget, a checkable finish condition, a decision log, and a stop condition. Stepping away grants no extra commit, publication, or merge authority. Requested native scheduling still needs verified host support; this library does not keep a terminated session alive.

## Save a handoff

With Herdr enabled, include the execution preference, machine/session, task-to-agent/pane assignments, write scopes, artifact evidence, and remaining processes. Reconcile live state before resuming; a saved prompt is not permission to resend it. [Pause and resume behavior](herdr.md#turn-it-off-pause-or-resume) explains why client detach does not pause workers.

If durable execution is unavailable, [pause safely](../../skills/z-mode/playbooks/pause-safely.md) saves:

- Branch and SHAs
- Dirty files
- Evidence and decisions
- Granted authority
- The exact next action

::: code-group

```text [Claude Code]
/z-mode pause; record the exact resume action
```

```text [Codex]
$z-mode pause; record the exact resume action
```

:::

## Capture your working conventions

| Skill | Use it to |
| --- | --- |
| [automate-me](../../skills/automate-me/SKILL.md) | Draft a named personal mode from explicit preferences and requested scoped history. |
| [reflect](../../skills/reflect/SKILL.md) | Propose durable lessons and apply only approved changes. |
| [correct](../../skills/correct/SKILL.md) | Prevent repeated repository mistakes with architecture or automated checks, then maintain a rule-to-enforcement table. |

::: tip
These skills do not silently write memory or file external backlog.
:::

For a repeated mistake, name the failure rather than prescribing a new prose rule:

::: code-group

```text [Claude Code]
/correct agents keep adding config flags without registering them in the schema; keep fixes local
```

```text [Codex]
$correct agents keep adding config flags without registering them in the schema; keep fixes local
```

:::

The skill needs at least two independent incidents and proves that the chosen architecture or check prevents a real past mistake.

Keep one canonical skill source. Use linked installation, rebuild and refresh the native Codex plugin, or reload the in-place Claude Code plugin when that source changes. Preserve invocation policy, validate metadata and resources, and exercise behavior changes in isolated native sessions.
