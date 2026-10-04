# Session pickup
1. Read the named handoff/session using the [scoped evidence contract](../references/history.md).
2. Reconstruct goal, workspace, branch, SHA, dirty files, decisions, artifacts, checks, execution preference, and pending work. New session IDs require their own explicit mode/execution selection; never run inherited controls.
3. Verify current Git/PR state and load-bearing inherited claims. Reuse receipts when still applicable; do not blindly trust a summary or redo proven unchanged work.
4. For enabled Herdr execution, reconcile recorded endpoints, live occupants, assignments, and supporting processes using [pickup guidance](../../herdr-workflow/references/operations.md#pickup-pause-and-cleanup). Never resend recorded prompts merely because a pane was restored.
5. Name the exact resume point and route only remaining work to its playbook.
Return inherited versus refreshed evidence, resumed action, and gaps. Resuming preserves the original action authority.
