---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
disable-model-invocation: true
---

# Arena

Produce independent candidates, choose a base, adapt useful ideas, and verify. Use the [native contract](../z-mode/references/native-hosts.md).

1. Define the artifact and 3-6 success criteria. Choose 2-3 candidates through the selected execution method unless the user specifies another useful count. Follow its model semantics; report actual identities if exposed. If the host rejects a requested model, apply the [model fallback](../z-mode/references/native-hosts.md#delegation) or drop that seat and say so. If dropped seats leave fewer than two candidates, add candidates on a remaining candidate's model, or the inherited default when none remain, and say so.
2. Give each the same task/grounding, exclusive output or worktree, and artifact plus rationale. Queue within host limits.
3. Wait for terminal results and read every artifact. A dropout remains a gap.
4. A fresh read-only judge scores completed candidates. It must not be a writer and must come from a model family other than yours, such as an exposed model override, or another provider's CLI when Herdr is the selected execution method. An inherited or same-family model never judges. Count a judge only when its family is verified; otherwise try the next available option. If no other-family judge runs, skip judging, pick the base alone, and say so.
5. Pick by criteria, comparing with the judge when one ran, and reconcile disagreements. Adapt ideas coherently; convergence needs no forced graft.
6. Verify the synthesis. Record base, grafts, rejections, the judge's identity and verdict or that judging was skipped, gaps, and evidence.

Same-model independent runs are useful but do not satisfy cross-provider comparison. A requested cross-provider comparison requires verified provider identities and available execution capabilities; report missing coverage.
