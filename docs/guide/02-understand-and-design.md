# Understand and design

## Understand before changing

| Skill | Use it to |
| --- | --- |
| [how](../../skills/how/SKILL.md) | Trace behavior. |
| [why](../../skills/why/SKILL.md) | Investigate motivation from source records, retaining uncertainty. |
| [teach](../../skills/teach/SKILL.md) | Combine findings into an explanation. |
| [recall](../../skills/recall/SKILL.md) | Reconstruct only scoped history. |
| [session pickup](../../skills/z-mode/playbooks/session-pickup.md) | Resume a specific prior session. |

::: code-group

```text [Claude Code]
/how trace argument parsing; read-only
/why does the retry path back off twice? cite the commits
```

```text [Codex]
$how trace argument parsing; read-only
$why does the retry path back off twice? cite the commits
```

:::

::: warning Unverified history
Missing verified transcripts get a labeled digest, not a claim of historical coverage.
:::

## Design and review

| Skill | Use it to |
| --- | --- |
| [architect](../../skills/architect/SKILL.md) | Design from caller usage and types first. |
| [arena](../../skills/arena/SKILL.md) | Settle contested shapes with independent candidates and synthesis. |
| [swarm](../../skills/swarm/SKILL.md) | Partition coverage across agents. |
| [interrogate](../../skills/interrogate/SKILL.md) | Return adversarial findings without edits. |

::: code-group

```text [Claude Code]
/architect design the cache invalidation API; design only
/interrogate this diff; findings only
/swarm check these three packages; one owned report per package
```

```text [Codex]
$architect design the cache invalidation API; design only
$interrogate this diff; findings only
$swarm check these three packages; one owned report per package
```

:::

::: info
A design request stops at a design unless implementation is already requested.
:::

::: warning Same-model runs
These skills use bounded native agents and report actual identities. Multiple runs may share one model; cross-provider consensus is not promised.
:::
