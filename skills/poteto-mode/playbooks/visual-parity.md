# Visual parity
1. Capture or identify immutable baselines, states, viewport, fonts, and rendering environment before migration.
2. Hold the baseline and harness stable. Investigate an invalid baseline rather than changing it to pass.
3. Migrate shared primitives first, then isolated components.
4. Compare rendered output with the project's image-diff harness and its agreed tolerance (zero for pixel-exact requests). Inspect the deltas and drive interactions as needed.
Return states covered, per-state results, artifacts, and missing proof. Do not claim parity from appearance alone.
