---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
disable-model-invocation: true
---

# Arena

Produce independent candidates, choose a base, adapt useful ideas, and verify. Use the [native contract](../z-mode/references/native-hosts.md).

1. Define the artifact and 3-6 success criteria. Choose 2-3 native candidates unless the user specifies another useful count. Inherit models; report actual identities if exposed.
2. Give each the same task/grounding, exclusive output or worktree, and artifact plus rationale. Queue within native limits.
3. Wait for terminal results and read every artifact. A dropout remains a gap.
4. A fresh read-only judge scores completed candidates. It must not be a writer. If unavailable, label the judgment parent-only.
5. Pick by criteria and reconcile disagreements. Adapt ideas coherently; convergence needs no forced graft.
6. Verify the synthesis. Record base, grafts, rejections, reviewer identities, gaps, and evidence.

Same-model independent runs are useful but do not satisfy cross-provider comparison, which is outside this release.
