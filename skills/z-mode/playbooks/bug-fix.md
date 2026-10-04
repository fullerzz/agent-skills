# Bug fix
1. Reproduce on the reported surface with the project's harness. If unreachable, record the attempted path and missing capability.
2. Trace the mechanism through callers and history. Instrument when evidence is unclear; do not add speculative fixes.
3. Choose the smallest root-cause fix within scope. Use architect only for a non-obvious shape; delegation is optional through the [selected execution method](../references/native-hosts.md#execution-selection).
4. Add a focused failing-then-passing check when it can meaningfully catch this defect.
5. Re-run the original repro and appropriate regressions. Label inconclusive proof.
Return defect, root cause, fix, actual checks, and limits. Publication requires a separate request.
