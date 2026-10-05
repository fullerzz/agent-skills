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

## Resolve open questions with prototypes

Use the [Prototype playbook](../../skills/z-mode/playbooks/prototype.md) when running a small experiment can settle a layout, timing, or behavior question. Compare useful variants in scratch space and inspect the rendered output or measurements before picking one. Skip the experiment when the direction is already established.

::: code-group

```text [Claude Code]
/z-mode prototype two settings layouts; show rendered screenshots for comparison
```

```text [Codex]
$z-mode prototype two settings layouts; show rendered screenshots for comparison
```

:::

For a shared package or API, sketch its caller-facing README or tutorial first. That gives the design a concrete usage target. Resolve experimentally answerable uncertainties before polishing a plan; review can still catch scope, dependency, and authority problems before code exists.

When complexity warrants a plan or the user asks, settle the design, then use the [Multi-phase plan playbook](../../skills/z-mode/playbooks/multi-phase-plan.md) to write coherent phases with acceptance and verification checks. The plan is the deliverable; implementation begins only when requested.
