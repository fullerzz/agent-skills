---
name: principle-type-system-discipline
description: "Apply when designing types, reviewing a function signature, or writing code in any statically-typed language. Make illegal states unrepresentable, brand semantic primitives, parse external data at boundaries, refuse to lie to the compiler, exhaust variants, derive from authoritative schemas."
disable-model-invocation: true
---

# Type System Discipline

Make the compiler reject impossible states, mismatched primitives, and unhandled variants. For TypeScript syntax, see [typescript-best-practices](../typescript-best-practices/SKILL.md).

- **Make illegal states unrepresentable.** Model variants as sum types (discriminated unions, enums with payloads, sealed classes) instead of optional-field bags that admit contradictory combinations: `{ kind: 'open' } | { kind: 'done'; at: Date }`.
- **Types are constructions, not restrictions.** Build valid shapes instead of carving values out of a looser type with checks. A non-empty list is a head plus a rest; a valid time range is a start plus a duration. Expose the interface callers need.
- **Brand semantic primitives.** Give `UserId` and `OrderId` distinct brands or newtypes even if both are strings. If arguments share a primitive type but mean different things, brand them. Validate once at creation; trust the type downstream.
- **External data is untyped until parsed.** Parse RPC payloads, JSON, IPC messages, CLI args, config, environment variables, and database rows into domain types at every boundary. See [boundary-discipline](../principle-boundary-discipline/SKILL.md) for validation placement.
- **Don't lie to the type system.** Validate, narrow, or refine the model instead of bypassing the compiler with unsafe casts, coercions, or assertions. Trace each `any`, `as`, or `assertNotNull` to the boundary and validate there.
- **Exhaustive matching is the compiler's job.** Matches on sum types must fail compilation when a new variant is unhandled. Use the language's exhaustiveness idiom, such as a `never`-typed binding in TypeScript.
- **Derive types from authoritative schemas.** Derive from whichever protocol, API schema, database migration, or design-token file owns the shape instead of maintaining a parallel type. See [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md).
- **Strengthen a type only where partiality appears.** Push runtime assertions, null checks, or impossible-state throws into the type, then stop. Track cases callers must handle, not maximum data precision. Prefer total functions: `sum` of an empty list is 0, so it takes a plain list; `head` needs a non-empty one. If nothing would otherwise panic, keep the plain type.
