# Upstream provenance

This library adapts Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack), copied from the Cursor plugins repository. The copied manifest declared version `0.15.5`. The exact copied commit was not recorded and has not been established. The MIT license and original copyright are retained in [LICENSE](../LICENSE).

The port keeps the portable engineering principles, reference prompts, decision logger, orchestration bookkeeping, and GitHub PR watcher. Workflow instructions now target Codex and Claude Code with native agents and local skill discovery.

The Cursor plugin manifest, branding assets, `make-bot-ui`, and dormant `automations/benny` pack are retired. The latter two require Cursor routines, secret cards, webhooks, or an automation runtime unavailable in this library. Recover their original sources from upstream if a replacement runtime becomes a concrete project. They are not installed or advertised as working here.

Cross-provider orchestration, marketplace packaging, and a replacement agent daemon remain outside this release.
