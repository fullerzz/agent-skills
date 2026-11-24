---
name: reframe
description: "Find the expert terms for what the user wants to build, verify examples, and rewrite their brief. Use for reframe."
disable-model-invocation: true
---

Run only when the user explicitly asks for reframe. Start with their own description and relevant files.

If the brief fits several problems, name the two or three most plausible ones. Give each its technical term and one observable sign that distinguishes it. Explain which interpretation best fits the available evidence and why. If the deciding fact is missing, keep that assumption visible in the rewrite.

1. Aim for 8–12 terms, ranked by how much each would change what gets built. Define each in one plain sentence, point to the part of the brief or file it names, and show what the user can now ask for.
2. Ground each term in a real project, paper, or system. Open the source and confirm it uses the term in that sense. Link the example. Omit terms whose examples you cannot verify, even if that yields fewer than eight. If source access is unavailable, say so.
3. Draw on two or three neighboring fields that have tackled the same problem. Identify the terms worth borrowing, what carries over, and where each analogy breaks. Call out any consequential consideration missing from the brief.
4. Return a rewritten brief in the user's voice. Preserve their goal, constraints, and open choices. Stop after the rewrite. The user can invoke sharpen separately or send the brief themselves.
