# Perf issue
1. Capture a repeatable baseline on the realistic workload that reproduces the complaint. Establish a measurable target for that workload before optimizing; if the request supplies none, agree on one with the user. Vet the baseline and each later number with [benchmark-checklist](../../benchmark-checklist/SKILL.md).
2. Trace the cost. Try the performance mantras in order, cheapest first, when the trace supports them:
   1. Don't do it. Stop work whose result nothing uses rather than cheapening it.
   2. Do it, but don't do it again.
   3. Do it less.
   4. Do it later.
   5. Do it when they're not looking.
   6. Do it concurrently.
   7. Do it cheaper.

   When an earlier mantra meets the agreed target, stop.
3. Change one mechanism at a time and run the same probe interleaved on baseline and treatment.
4. Measure enough samples to separate a win from noise, then run correctness regressions.
Return baseline, treatment, units, delta, method, and artifact paths. Do not compare unlike scenarios or infer a win from source inspection.
For sustained improvement use hillclimb.
