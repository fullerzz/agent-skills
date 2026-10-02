# Use this library in Claude Code

From the library checkout run `uv run scripts/install.py --host claude`, inspect the preview, then repeat with `--apply`. Add `--project "/path/to/project"` for project scope. Empty `--home` or `--project` values are rejected before any writes.

Personal skills link into `$CLAUDE_CONFIG_DIR/skills/<name>` (default `~/.claude/skills/<name>`); native agents copy into that root's `agents/`. Project installation uses `.claude/skills/<name>` and `.claude/agents/`. Explicit `--home` uses that root's `.claude`, ignoring the environment override so fixture installations stay isolated. A new session discovers these sources. See the native [configuration-directory setting](https://code.claude.com/docs/en/env-vars#variables).

Invoke `/how` or `/poteto-mode`. Explicit-only skills retain `disable-model-invocation: true`. When the selected mode needs a companion, it reads that installed skill's instructions deliberately. Do not assume an explicit-only skill can be silently auto-selected.

Agent roles are `poteto-agent` and `comment-sicko`, with Markdown frontmatter and `model: inherit`. The comment reviewer excludes Write and Edit and is instructed to avoid all writes including Bash/MCP; those exclusions alone are not a complete sandbox. A native role or tool missing from the session gets a disclosed fallback. Queue work within actual nesting/concurrency limits.

Use native model/effort configuration for requested overrides. Modified owned copies are preserved and future installer runs report collisions. The installer does not touch permissions, model settings, hooks, plugins, or MCP configuration.

Claude Code 2.1.281+ supports native AGENTS.md in the documented configurations. If a parent/project CLAUDE.md takes precedence or AGENTS.md support is disabled, use the documented project-instructions option or an explicit CLAUDE.md containing `@AGENTS.md`. Do not duplicate maintenance rules. This checkout supplies AGENTS.md only.

Resume with `claude --resume <id>` or `claude --continue`. If history cannot be verified, use a labeled digest/handoff. Skill resources resolve from their real directory while target commands retain the project cwd.

See [skills](https://code.claude.com/docs/en/skills), [subagents](https://code.claude.com/docs/en/sub-agents), [project memory rules](https://code.claude.com/docs/en/memory), and [local validation](../validation.md).
