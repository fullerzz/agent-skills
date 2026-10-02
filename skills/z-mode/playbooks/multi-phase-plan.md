# Multi-phase plan
Planning produces a plan; implementation begins only when requested.
1. Ground the affected flow and actual constraints. Prototype only unresolved facts that need an experiment.
2. Write a task-sized plan at the user's path or docs/<slug>-plan.md. Use this contract:
   - H1 title.
   - H2 Outcome with a falsifiable done condition.
   - H2 Scope with boundaries and action authority.
   - H2 Phases, with one H3 per coherent unit.
   - Each phase includes Depends on, Files, Acceptance, and Verification as nonempty bullet fields.
   - H2 Risks with real uncertainties or an explicit "None identified".
   - H2 Handoff with current state, resume point, and who handles publication/merge.
3. Name realistic verification commands, surface, and expected evidence for each phase. Include live, performance, screenshots, and independent reviewers only when they prove a relevant requirement. Explain a missing required capability.
4. Resolve and run the bundled scripts/check-plan.mjs from this skill's real directory, preserving target cwd.
5. Return the path, dependencies, tradeoffs, and validator result. Stop at a requested review checkpoint.
No fixed lane counts, overnight runtime promises, or automatic PRs.
