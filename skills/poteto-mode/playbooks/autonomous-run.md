# Autonomous run
1. State the checkable done predicate, scope, budget/stop condition, and available capabilities.
2. Work continuously within the session. Use an existing event watcher or verified native background facility when needed; do not assume a skill supplies an overnight scheduler.
3. Each iteration makes a justified change and verifies it before the next. Revert only unsuccessful edits owned by this run.
4. Record decisions and checkpoints via show-me-your-work. Fix in-scope blockers; park unrelated discoveries locally.
5. Stop on verified done, explicit pause/stop, a real blocker, or the agreed limit. Do not relax the predicate.
If execution cannot persist, write pause-safely's concrete handoff. Return iterations, evidence, predicate state, and remaining work. Autonomy does not expand publication or merge authority.
