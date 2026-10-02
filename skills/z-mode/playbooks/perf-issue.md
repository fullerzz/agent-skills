# Perf issue
1. Capture a repeatable baseline on the realistic workload that reproduces the complaint.
2. Trace the cost. Consider elimination, smaller work sets, caching with explicit invalidation, indexing, batching, lazy evaluation, or scheduling only when the trace supports it.
3. Change one mechanism at a time and run the same probe interleaved on baseline and treatment.
4. Measure enough samples to separate a win from noise, then run correctness regressions.
Return baseline, treatment, units, delta, method, and artifact paths. Do not compare unlike scenarios or infer a win from source inspection.
For sustained improvement use hillclimb.
