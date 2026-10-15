---
name: principle-make-operations-idempotent
description: "Apply when designing commands, lifecycle steps, or processing loops that run amid crashes, restarts, and retries. Converge to the same end state regardless of partial prior runs."
disable-model-invocation: true
---

# Make Operations Idempotent

Design operations so they converge to the correct state regardless of how many times they run or where they start from. Every state-mutating operation should answer: "What happens if this runs twice? What happens if the previous run crashed halfway?"

**Why:** Commands, lifecycle operations, and processing loops run where crashes, restarts, and retries are normal. If partial state changes the next run's outcome, every restart becomes a debugging session.

**The idea:** Read the current state, compare it with the desired state, and apply the required delta: additions, updates to incorrect values, and safe removals of surplus resources within authorized scope. Derive the next step from what exists, not what a previous run intended. Repeating completed work should find nothing left to change.

Leftover locks, temporary files, partial records, and claimed jobs need evidence that lets a later run distinguish stale artifacts from live work. That evidence must remain valid across possible interruption points and execution environments. A PID alone may not identify the owner across hosts or process reuse. Uncertain ownership is not permission to delete an artifact.

Choose mechanisms that fit the operation: compare content rather than creation order, or publish a completed temporary file with an atomic rename where supported. Keep reconciliation and cleanup within the authorized scope.

**The test:**
1. What happens if this runs twice in a row?
2. What happens if the previous run crashed at every possible point?
3. Does re-execution converge to the same end state?

If any answer is "it depends on what state was left behind," the operation needs a reconciliation step.
