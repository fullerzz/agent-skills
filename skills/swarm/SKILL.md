---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
---

# Swarm

Partition coverage, race identical briefs, or mix both. Declare the done predicate and selection rule before spawning. Follow the [native contract](../z-mode/references/native-hosts.md).

Use the smallest useful count. Each brief names slice, read/write scope, exclusive output, checks, and PASS / ISSUES / BLOCKED report with evidence. Measurement/commit checks name exact SHAs, workload, samples, and method.

Run workers through the selected execution method within exposed limits. Herdr agents use the explicitly selected endpoint; do not assume cloud VMs or placement arguments. Isolate worktrees, data, and ports where needed.

Wait for terminal results and inspect receipts. Missing required SHAs/method invalidate measurement: respawn that worker once with a consolidated brief under the [agent lifecycle rules](../z-mode/references/native-hosts.md#agent-lifecycle), then record a gap after a second miss. A first-pass race still cancels or drains remaining writers.

Return a consolidated table, evidenced findings, selection rule, identities if exposed, and explicit gaps. Missing required coverage is not a pass.
