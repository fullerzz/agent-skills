# Orchestrate
Coordinate a program too large for one simple run. A single task uses autonomous-run instead.

1. State units, dependencies, acceptance criteria, scope, budget, and action authority. Start with a pilot to prove the brief and checks.
2. Keep state in a user-owned task directory such as .agent-work/<slug>, outside delegated writes. Store standing orders, briefs, status, head SHAs, receipts, and decision trail.
3. Use native agents under the host contract with a rolling bounded window. Each brief names goal, scope/ownership, context, acceptance, verification, stop condition, and report. Tell writers to preserve concurrent edits.
4. Wait for terminal results, inspect artifacts, relay verified upstream context into dependent briefs, and account for every child. A missing child is a gap.
5. The optional bundled orch CLI manages TSV/JSON bookkeeping only. Resolve its absolute installed path and consult --help. Its frontier command requires Graphite metadata; if that is absent, do not use it. Record the dependency frontier directly from explicit branches/PRs instead.
6. One coordinator owns topology. Workers do not rebase shared branches, push, merge, or post without explicit delegated authority.
7. Verification scales with risk. Record exact head SHAs and methods; stale/failed/blocked receipts are not passes. Reconcile changes before integrating.
8. Retry a failed unit once with evidence, then replan or report the gap. Liveness comes from native status/terminal output, not transcript mtime.
9. Reconcile all children before completion or pause. No durable runtime means a usable handoff, not promised wakeups.
Return unit counts, current frontier, evidence, abandoned work, blockers, and state directory. Keep state intact for resume.
