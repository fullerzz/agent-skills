---
name: principle-never-block-on-the-human
description: "Apply when tempted to ask 'should I do X?' on reversible work. Proceed, present the result, let the human course-correct after the fact; stay within authorized scope and reserve clarification for real missing decisions."
disable-model-invocation: true
---

# Never Block on the Human

The human supervises asynchronously. Agents must stay unblocked. Make reasonable decisions, proceed, and let the human course-correct after the fact.

**Why:** Every permission pause stalls the pipeline and makes the human the bottleneck. Since code changes are reversible and reviewable, a wrong decision usually costs less than blocking.

**Pattern:**
- **Proceed, then present.** Do the work, show the result. Don't ask "should I do X?" Do X, explain why.
- **Resolve in-scope blockers.** Record unrelated discoveries locally; do not widen the task to fix them.

**Boundaries:**
- **Authority follows the request.** Commit, push, PR, messages, tracker writes, merge, deployment, and destructive operations need authorization covering that action. Do not ask again when it is already explicit.
- **Authorized reversible actions** (write scoped code, edit requested notes, split work) proceed without blocking. Read-only requests remain read-only.
- **Product direction** comes from the human. *Execution* should not block.
