# Build and verify

## Build a scoped change

The [poteto-mode router](../../skills/poteto-mode/SKILL.md#routing) picks the matching playbook. Each one needs a different starting point.

| Work | Needs | Playbook |
| --- | --- | --- |
| Bug | A repro and root cause | [bug-fix](../../skills/poteto-mode/playbooks/bug-fix.md) |
| Feature | Observable acceptance | [feature](../../skills/poteto-mode/playbooks/feature.md) |
| Refactor | A held behavior contract | [refactoring](../../skills/poteto-mode/playbooks/refactoring.md) |
| Performance | A repeatable baseline | [perf-issue](../../skills/poteto-mode/playbooks/perf-issue.md) |

::: code-group

```text [Claude Code]
/poteto-mode fix duplicate output; reproduce first; keep changes local
```

```text [Codex]
$poteto-mode fix duplicate output; reproduce first; keep changes local
```

:::

## Keep it clean

| Skill | Use it to |
| --- | --- |
| [tdd](../../skills/tdd/SKILL.md) | Add cheap, meaningful regressions. |
| [no-comments](../../skills/no-comments/SKILL.md) | Run a reporting-only comment reviewer; the parent applies only authorized accepted edits. |
| [unslop](../../skills/unslop/SKILL.md) | Keep the explanation readable. |
| [technical-writing](../../skills/technical-writing/SKILL.md) | Keep the explanation readable. |

## Verify before publication

Use the project's existing harness first.

- [create-verification-skill](../../skills/create-verification-skill/SKILL.md) generates native project instructions from real launch, doctor, drive, evidence, and cleanup behavior, then executes one mapped path.
- [maintain-verification-skill](../../skills/maintain-verification-skill/SKILL.md) stays within that skill directory and reports product regressions.

## Publish on request

::: warning Each publication step needs its own request
Local edits, commit, push, PR, merge, and deployment are separate requested actions.
:::

| Playbook | Runs when |
| --- | --- |
| [Opening a PR](../../skills/poteto-mode/playbooks/opening-a-pr.md) | Publication is part of the request. |
| [Babysit](../../skills/poteto-mode/playbooks/babysit.md) | You ask about status; status questions stay read-only. |
| [Shipping](../../skills/poteto-mode/playbooks/shipping.md) | You grant explicit landing authority; it needs current-head evidence. |
