---
name: principle-fix-root-causes
description: "Apply when debugging. Trace the first wrong decision or missing handling of a legitimate state, and fix it there; do not hide invalid states at the symptom."
disable-model-invocation: true
---

# Fix Root Causes

Trace a symptom to the first wrong decision or failure to handle a legitimate state. Fix that cause rather than hiding where it surfaced.

**Why:** Symptom fixes accumulate. Each workaround makes the system harder to reason about, and the real bug remains. Root-cause fixes are slower upfront but reduce total debugging time.

**Pattern:**
- Reproduce first
- Ask "why" until you hit the root cause
- Decide whether the triggering state is legitimate. If it can validly occur, a guard that handles it can be the root-cause fix. If it violates an invariant, trace what produced it; guards, retries, clamping, swallowed errors, or discarded state can conceal that fault. Keep required validation and safe failure handling.
- If a workaround needs a paragraph-long comment to justify it, the code is wrong (fix the code, not the comment)
- Check for the pattern, not just the instance (grep for the same pattern, fix all affected instances within scope, and report out-of-scope siblings)
- When stuck, instrument. Don't guess (add logging, read the actual error)
- If the deciding fact took a deep dig to find, propose the cheap, always-on signal that would have shown it at first look. Proposing it does not authorize adding it outside task scope.

**Restart bugs: suspect state before code**

When something "fails after restart," suspect stale persistent state first: config files, caches, lock files, serialized state. If clearing a state file restores behavior, investigate how the state was produced and whether recovery should handle it; clearing it alone does not establish the fix.
