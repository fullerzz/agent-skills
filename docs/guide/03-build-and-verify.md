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

## Publish on request

::: warning Each publication step needs its own request
Local edits, commit, push, PR, merge, and deployment are separate requested actions.
:::

| Playbook | Runs when |
| --- | --- |
| [Opening a PR](../../skills/z-mode/playbooks/opening-a-pr.md) | Publication is part of the request. |
| [Babysit](../../skills/z-mode/playbooks/babysit.md) | You ask about status; status questions stay read-only. |
| [Shipping](../../skills/z-mode/playbooks/shipping.md) | You grant explicit landing authority; it needs current-head evidence. |
