# Long work and conventions

## Run long work

Give [autonomous-run](../../skills/z-mode/playbooks/autonomous-run.md) a checkable predicate, scope, and budget. It works while the session is alive.

::: info No replacement daemon
Native background or scheduling features can be used when verified and requested; this library supplies no replacement daemon.
:::

[Orchestrate](../../skills/z-mode/playbooks/orchestrate.md) scales native workers around owned task state. [show-me-your-work](../../skills/show-me-your-work/SKILL.md) keeps an append-only TSV trail.

## Save a handoff

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

Keep one canonical skill source. Use linked installation or rebuild and refresh the native Codex plugin when that source changes. Preserve invocation policy, validate metadata and resources, and exercise behavior changes in isolated native sessions.
