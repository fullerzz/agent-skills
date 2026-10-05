# Build and verify

## Build a scoped change

[Follow an example request](visual-guide.md#follow-a-request) through investigation, bug fixing, feature work, or a safe pause.

The [z-mode router](../../skills/z-mode/SKILL.md#routing) picks the matching playbook. Each one needs a different starting point.

| Work | Needs | Playbook |
| --- | --- | --- |
| Bug | A repro and root cause | [bug-fix](../../skills/z-mode/playbooks/bug-fix.md) |
| Feature | Observable acceptance | [feature](../../skills/z-mode/playbooks/feature.md) |
| Refactor | A held behavior contract | [refactoring](../../skills/z-mode/playbooks/refactoring.md) |
| Performance | A repeatable baseline | [perf-issue](../../skills/z-mode/playbooks/perf-issue.md) |

::: code-group

```text [Claude Code]
/z-mode fix duplicate output; reproduce first; keep changes local
```

```text [Codex]
$z-mode fix duplicate output; reproduce first; keep changes local
```

:::

## Keep it clean

| Skill | Use it to |
| --- | --- |
| [tdd](../../skills/tdd/SKILL.md) | Add cheap, meaningful regressions. |
| [no-comments](../../skills/no-comments/SKILL.md) | Run a reporting-only comment reviewer; the parent applies only authorized accepted edits. |
| [unslop](../../skills/unslop/SKILL.md) | Keep the explanation readable. |
| [technical-writing](../../skills/technical-writing/SKILL.md) | Apply the layered writing standard to docs, RFCs, PRs, and commit messages. |

## Verify before publication

Use the project's existing harness first.

- [create-verification-skill](../../skills/create-verification-skill/SKILL.md) generates native project instructions from real launch, doctor, drive, evidence, and cleanup behavior, then executes one mapped path.
- [maintain-verification-skill](../../skills/maintain-verification-skill/SKILL.md) stays within that skill directory and reports product regressions.

Ask for proof you can inspect: real command output, a screenshot of the changed flow, a trace, or a readback of stored state. Match it to the acceptance check. A passing build alone does not prove changed behavior.

If the project already has a `verify-<app>` skill, name its real installed skill in the request. For example, with `verify-export` installed:

::: code-group

```text [Claude Code]
/z-mode reproduce the missing export row on the current main baseline with /verify-export; if it reproduces, fix it locally and show before/after row counts
```

```text [Codex]
$z-mode reproduce the missing export row on the current main baseline with $verify-export; if it reproduces, fix it locally and show before/after row counts
```

:::

Use an isolated baseline checkout to preserve existing work. If the bug no longer reproduces, report that result. A generated verification skill needs an end-to-end proof before use; rerun maintenance when its map or harness drifts. Choose a maintenance cadence only when requested.

## Vet a measured number

[benchmark-checklist](../../skills/benchmark-checklist/SKILL.md) checks the limiter, production tuning, physical limits, correctness, alternating repeated runs, end-to-end relevance, and whether the timed work actually ran. It returns faster, slower, no measurable difference, or inconclusive, with the run count, range, and limitations.

::: code-group

```text [Claude Code]
/benchmark-checklist vet this export speedup before it goes in the PR description
```

```text [Codex]
$benchmark-checklist vet this export speedup before it goes in the PR description
```

:::

The [Perf issue](../../skills/z-mode/playbooks/perf-issue.md) and [Hillclimb](../../skills/z-mode/playbooks/hillclimb.md) playbooks already use the checklist. Invoke it directly for measurements made outside those workflows or for someone else's claim.

## Publish on request

::: warning Each publication step needs its own request
Local edits, commit, push, PR, merge, and deployment are separate requested actions.
:::

| Playbook | Runs when |
| --- | --- |
| [Opening a PR](../../skills/z-mode/playbooks/opening-a-pr.md) | Publication is part of the request. |
| [Babysit](../../skills/z-mode/playbooks/babysit.md) | You ask about status; status questions stay read-only. |
| [Shipping](../../skills/z-mode/playbooks/shipping.md) | You grant explicit landing authority; it needs current-head evidence. |
