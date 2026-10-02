# Principles and recipes

## Use principles when they change a decision

The [router's principle index](../../skills/z-mode/SKILL.md#principles) lists all 23 leaves; the [skill catalog](../skills.md#principles) describes each one. Read the relevant leaf instead of reciting every principle for each task.

| Principle | Pushes toward |
| --- | --- |
| [separate-before-serializing-shared-state](../../skills/principle-separate-before-serializing-shared-state/SKILL.md) | Owned outputs |
| [fix-root-causes](../../skills/principle-fix-root-causes/SKILL.md) | Tracing the actual mechanism |
| [prove-it-works](../../skills/principle-prove-it-works/SKILL.md) | Real evidence |

::: warning
No principle expands scope, overrides a read-only request, or authorizes publication.
:::

## Recipes

::: code-group

```text [Claude Code]
/how trace argument parsing; read-only
/interrogate this diff; findings only
/swarm check these three packages; one owned report per package
/z-mode fix duplicate output; reproduce first; keep changes local
/z-mode pause; record the exact resume action
```

```text [Codex]
$how trace argument parsing; read-only
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

Scripts use absolute paths from the real installed skill; Git helpers inspect the target project. Retired automation sources are documented in [provenance](../provenance.md).
