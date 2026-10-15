---
name: principle-test-behavior-not-implementation
description: "Apply when you write, change, or keep a test. Assert observable behavior so the test catches a broken contract and survives internal refactors."
disable-model-invocation: true
---

# Test Behavior, Not Implementation

A test checks a contract observable by a caller, end user, or another service: return values, errors, readable state, or external effects. Private helpers, intermediate data, and internal call order are implementation details unless exposed by that contract.

Judge a test against two imagined edits:

- **Break the contract.** Return the wrong result, omit a required effect, or repeat it incorrectly. The test should fail. Loose assertions, expectations computed by the subject, and checks on fixture data alone can miss the defect.
- **Refactor the internals.** Preserve every observable result while changing helpers or internal structure. The test should still pass.

Drive the subject through its users' interface with concrete inputs. Derive expectations from the requirement rather than the implementation, and assert exactly what the contract promises. Within task scope, rewrite or delete tests that miss broken behavior or reject behavior-preserving refactors.

Assertion shape alone is not a verdict. A mocked external service's payload is observable behavior; a private helper's call count usually is not. If an empty cart must never charge, asserting no payment call is appropriate. Pair it with a chargeable case to show the test can observe a call. Empty-result assertions are valid when no matching records is the promised answer. Assert error types or wording only to the extent callers rely on them.

Invariants can also be contracts: keys shared across tables, externally consumed status codes, and `*.test-d.ts` type checks. Keep tests that enforce these contracts; a constant or prompt-string check that never exercises its consumer or establishes an invariant is not behavioral proof.
