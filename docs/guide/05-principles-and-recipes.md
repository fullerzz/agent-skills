# Principles and recipes

## Use principles when they change a decision

The [router's principle index](../../skills/z-mode/SKILL.md#principles) lists all 24 leaves; the [skill catalog](../skills.md#principles) describes each one. Read the relevant leaf instead of reciting every principle for each task.

| Principle | Pushes toward |
| --- | --- |
| [separate-before-serializing-shared-state](../../skills/principle-separate-before-serializing-shared-state/SKILL.md) | Owned outputs |
| [fix-root-causes](../../skills/principle-fix-root-causes/SKILL.md) | Tracing the actual mechanism |
| [prove-it-works](../../skills/principle-prove-it-works/SKILL.md) | Real evidence |

::: warning
No principle expands scope, overrides a read-only request, or authorizes publication.
:::

## Write a useful prompt

State the goal, a pass/fail done check, the proof you want to inspect, known facts such as repro steps or logs, and real constraints such as read-only investigation or a review checkpoint. Leave room for the agent to choose the implementation unless the method itself is a requirement. For a noisy report, ask for a plain-language restatement before editing; share a theory of the cause after that first reading to avoid anchoring the search.

Save z-mode for work that needs rigor. Use verified native model and effort settings when requesting a smaller budget, and bound review panels to useful independent coverage under the [native host contract](../../skills/z-mode/references/native-hosts.md#delegation). Installed skills do not create a separate model-routing configuration.

## Recipes

::: code-group

```text [Claude Code]
/how trace argument parsing; read-only
/z-mode read this report; restate the underlying issue and investigate the evidence; don't change any code yet
/interrogate this diff; findings only
/swarm check these three packages; one owned report per package
/z-mode fix duplicate output; reproduce first; keep changes local
/z-mode pause; record the exact resume action
```

```text [Codex]
$how trace argument parsing; read-only
$z-mode read this report; restate the underlying issue and investigate the evidence; don't change any code yet
$interrogate this diff; findings only
$swarm check these three packages; one owned report per package
$z-mode fix duplicate output; reproduce first; keep changes local
$z-mode pause; record the exact resume action
```

:::

## Pitfalls

- Overlapping writers.
- Stale head receipts.
- Unscoped history mining.
- Assuming a started agent completed.
- Leading with a theory before the issue is understood.
- Accepting a design while experimentally answerable questions remain.
- Polishing an abstract plan instead of testing its uncertain assumptions.
- Repeating unchecked work before the workflow earns trust.
- Reporting a speedup without vetting the measurement.
- Correcting the same mistake in chat instead of preventing it in the repository.

Scripts use absolute paths from the real installed skill; Git helpers inspect the target project. Retired automation sources are documented in [provenance](../provenance.md).
