# Hillclimb
1. Fix a metric, realistic workload, target, sampling method, correctness floor, and bounded attempt/time budget.
2. Prove the probe distinguishes workloads and vet it with [benchmark-checklist](../../benchmark-checklist/SKILL.md) before holding it stable. Make it report errors and work completed, then capture baseline.
3. Keep an append-only trail via the installed show-me-your-work skill.
4. For each attempt state one hypothesis, make one isolated change, measure before/after, and run the correctness gate. For a perf metric, order hypotheses by the performance mantras in step 2 of [Perf issue](perf-issue.md); borrow only their order, not that step's stop rule.
5. Keep wins above noise. Discard only the run's own unsuccessful edits, preserving other work. Record rejected attempts as well as accepted ones.
6. Stop on the target, explicit stop, exhausted agreed budget, or a documented blocker. Reframe a plateau without weakening the predicate.
Return the metric, baseline/final, attempts, kept changes, trail, and remaining hypotheses. No automatic commit or PR.
