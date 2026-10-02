# Refactoring
1. Pin current behavior with existing checks or a focused characterization/equivalence check.
2. Name the structural improvement. Remove dead code and redundant layers before adding shapes.
3. Move in coherent units. Migrate callers and references with the changed API, including strings and docs.
4. Keep each unit's behavior check green. Isolate delegated mechanical slices.
5. Verify equivalence on the actual artifact; compilation alone does not establish unchanged behavior.
Return the structural change, held contract, equivalence proof, and any separately discovered product defects.
