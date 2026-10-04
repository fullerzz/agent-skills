# Upstream provenance

zstack, Zach's updated skillset, adapts Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack), copied from the Cursor plugins repository. The copied manifest declared version `0.15.5`. The exact copied commit was not recorded and has not been established. The MIT license and original copyright are retained in [LICENSE](../LICENSE).

The port keeps the portable engineering principles, reference prompts, decision logger, orchestration bookkeeping, and GitHub PR watcher. Workflow instructions now target Codex and Claude Code with native agents and local skill discovery.

The Cursor plugin manifest, branding assets, `make-bot-ui`, and dormant `automations/benny` pack are retired. The latter two require Cursor routines, secret cards, webhooks, or an automation runtime unavailable in this library. Recover their original sources from upstream if a replacement runtime becomes a concrete project. They are not installed or advertised as working here.

The native Codex plugin packages shared skills and a session hook through a local marketplace. The Claude Code plugin loads the same skills, hook, and agent roles in place through its own local marketplace. Public marketplace publication and a replacement agent daemon remain outside this release.

The Herdr integration is zstack-specific coordination guidance based on Herdr's [agent guide](https://herdr.dev/agent-guide.md), [concepts](https://herdr.dev/docs/concepts/), [working guide](https://herdr.dev/docs/how-to-work/), [automation documentation](https://herdr.dev/docs/agent-automation/), and [upstream operational skill](https://raw.githubusercontent.com/herdrdev/herdr/master/skills/herdr/SKILL.md), reviewed 2026-10-04. It references upstream operations rather than vendoring that skill. Explicit Herdr execution applies across existing playbooks; launching a requested CLI does not establish cross-provider consensus or inherited host configuration.

The personal naming migration uses `zstack`, `z-mode`, `setup-zstack`, and `z-agent`. Upstream names and URLs remain in attribution and historical baseline records.

The benchmark-checklist and principle-explain-the-number skills were adapted from pstack 0.15.6, commit [23e4138](https://github.com/cursor/plugins/commit/23e4138daa01c42d4969f7a5465f82704e64f798). Their routing targets z-mode, preserves explicit invocation on both hosts, and uses portable host checks. This is a selective port, not a full update to that release.

The same commit supplies the fresh-agent lifecycle policy, adapted to native host limits and exclusive write ownership. Reuse remains available for costly agent-held state.

Its PR workflow updates are also adapted: built-in tools take precedence for supported operations, descriptions use concise section headings, and stack bases and readiness are read back. Repository templates, requested draft status, and publication authority still govern the workflow.

The correct skill is adapted from pstack 0.15.7, commit [9511e603](https://github.com/cursor/plugins/commit/9511e60321f7e533a187d62854a3d53a53752874). It preserves repeated-mistake classification, the architecture/types/lint/tests/docs ordering, historical failure proofs, and the rule-to-enforcement table. The port adds scoped native history, explicit-only metadata for both hosts, isolated reproductions, and observed-versus-configured CI reporting. Upstream's automatic commits and future-correction trigger are replaced by task-specific authority and invocation scope. This is a selective skill port; the upstream version bump is not applied to zstack. The retained MIT license covers the adaptation.
