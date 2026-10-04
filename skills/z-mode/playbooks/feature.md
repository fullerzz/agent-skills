# Feature
1. Ground entry points, caller contracts, and existing patterns.
2. Name the data shape and simplest interface. Compare alternatives only where the design is contested.
3. Identify prerequisites, independent seams, and shared writes. Keep a small task direct; delegate exclusive slices through the [selected execution method](../references/native-hosts.md#execution-selection) when useful.
4. Implement within scope, adapting all affected consumers rather than leaving a parallel legacy path.
5. Verify observable behavior with the existing harness and appropriate checks. Use live proof when the behavior requires it.
Return user-visible result, meaningful design choices, proof, and open decisions. Commit or publish only as requested.
