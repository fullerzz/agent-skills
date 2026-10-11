---
name: principle-test-behavior-not-implementation
description: "Apply when you write, change, or keep a test. Call the code the way its users do and assert the result they observe against a literal expected value. If the test would still pass when every imported function returns undefined, rewrite the assertion or delete the test."
disable-model-invocation: true
---

# Test Behavior, Not Implementation

A test calls the code as its users do and asserts the result against a literal expected value. Rewrite or delete any test that would still pass if every imported function returned `undefined` or a wrong value.

These shapes fail that check:

- Loose or no assertion: no `expect`, or only `toBeDefined`, `toBeTruthy`, `not.toThrow`, `toBeInstanceOf`, `toBeGreaterThan(0)`.
- Call or absence only: `toHaveBeenCalled`, `not.toHaveBeenCalled`, `toBeUndefined`, `toEqual([])`, `toHaveLength(0)`, `not.toBe(wrongValue)`.
- Expected value computed by the code under test: `expect(f(a)).toBe(f(a))`, `expect(parsed.url).toBe(buildUrl(...))`.
- Restated constant, config default, table row, or prompt string: `expect(LIMITS.maxTools).toBe(8)`, `expect(PROMPT).toContain("You are")`.
- Assertions on data the test built or computed in `beforeEach`, with no call to the subject.

Fix: call the subject in the test body with one concrete input and assert the literal output or effect, such as `expect(slugify("Hello, World!")).toBe("hello-world")`. For a mock, assert the payload it received or the resulting state. For an absence, also assert the presence on another input in the same test. For a constant, test the mechanism that reads it with one input instead of restating the value. Delete the test when no such assertion exists.

Keep relation checks across table rows (a key in two tables, a parent that exists) and `*.test-d.ts` type checks.
