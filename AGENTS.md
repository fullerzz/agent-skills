# Repository maintenance

Keep shared skills in `skills/`. Native agent formats live in `agents/codex/` and `agents/claude/`. Resolve bundled resources relative to the real skill location and run Git helpers in the target repository. Preserve invocation policy, license attribution, and unrelated workspace changes.

Use `xh` instead of `curl`. Use `uv` for Python. Install tools with `mise` or `brew`.
For file searches and greps in this git-indexed repository, use fff MCP tools.

Use ordinary web search for static documentation. Use Camofox for interactive, authenticated, or JavaScript websites; use Obscura for lightweight extraction or compatible-site fallback. Open, snapshot, act, snapshot after changes, and close tabs. Do not import cookies or expose authenticated sessions unless explicitly requested.

Run `bun scripts/validate.mjs` and `node --test scripts/*.test.mjs` after structural changes. For changes to bundled Bun tools, run their test and typecheck scripts. Record actual host checks in `docs/validation.md`. A static pass is not a live behavior result.

Skill authoring does not authorize commits, publication, messages, or tracker writes. Spawn agents only when the user or an applicable instruction requests delegation. Keep installer tests isolated from real personal configuration.
