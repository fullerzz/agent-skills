---
name: automate-me
description: "Draft or update a personal mode skill from stated conventions and explicitly scoped history."
disable-model-invocation: true
---

# Automate me

Draft or update a personal mode skill from stated conventions. Produce a local reviewable artifact.

1. Find the existing named mode in the host catalog/requested source. Preserve its canonical location and confirmed rules.
2. Mine history only when requested, following [scoped evidence](../z-mode/references/history.md). Cite recurring patterns. If unavailable use explicit preferences and label the basis.
3. Ask only for meaningful missing preferences. Current corrections outrank inferred patterns; one incident is not a universal rule.
4. Write short kebab-case SKILL.md metadata and decision-changing instructions using available authoring guidance or the [authoring playbook](../z-mode/playbooks/authoring-a-skill.md).
5. Project paths are .agents/skills/<name> for Codex, .claude/skills/<name> for Claude Code. For both keep one canonical directory and collision-safe link the other. Personal paths are ~/.agents/skills or ~/.claude/skills when requested.
6. A new personal mode is explicit-only unless requested otherwise: Claude disable-model-invocation: true; Codex agents/openai.yaml policy.allow_implicit_invocation: false.
7. Show the draft, iterate, and validate. Subjective modes need user review rather than invented benchmarks.

Reference available companions rather than copying them. Authoring does not authorize commits, pushes, messages, or PRs.
