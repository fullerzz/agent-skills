# Perf issue
1. Capture a repeatable baseline on the realistic workload that reproduces the complaint. Establish a measurable target for that workload before optimizing; if the request supplies none, agree on one with the user. Vet the baseline and each later number with [benchmark-checklist](../../benchmark-checklist/SKILL.md).
2. Trace the cost. Evaluate the performance mantras in order, cheapest first. Skip unsupported mantras; for each supported mantra, complete steps 3–4 before advancing:
   1. Don't do it. Stop work whose result nothing uses rather than cheapening it.
   2. Do it, but don't do it again. For reused results, define invalidation for mutable inputs or demonstrate that the inputs remain immutable throughout the cache's scoped lifetime.
   3. Do it less.
   4. Do it later.
   5. Do it when they're not looking.
   6. Do it concurrently.
   7. Do it cheaper.

3. Change one mechanism at a time and run the same probe interleaved on baseline and treatment.
4. Measure enough samples to separate a win from noise, then run correctness regressions. Stop only when the treatment meets the agreed target and passes correctness checks. Otherwise, revert failed or unproven treatments; retain verified improvements as the next baseline. Return to step 2 for the next supported mantra. If none remain, report the unmet target and evidence.
Return baseline, treatment, units, delta, method, and artifact paths. Do not compare unlike scenarios or infer a win from source inspection.
For sustained improvement use hillclimb.
