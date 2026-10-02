# Claude Code setup

## Install

From the library checkout, preview the installation, inspect the output, then apply it:

```sh
uv run scripts/install.py --host claude
uv run scripts/install.py --host claude --apply
```

Add `--project "/path/to/project"` for project scope.

::: info
Empty `--home` or `--project` values are rejected before any writes.
:::

## Locations

| Scope | Skills | Agents |
| --- | --- | --- |
| Personal | `$CLAUDE_CONFIG_DIR/skills/<name>` (default `~/.claude/skills/<name>`) | That root's `agents/` |
| Project | `.claude/skills/<name>` | `.claude/agents/` |

Skills are links; native agents are copies. Explicit `--home` uses that root's `.claude`, ignoring the environment override so fixture installations stay isolated. A new session discovers these sources. See the native [configuration-directory setting](https://code.claude.com/docs/en/env-vars#variables).

## Invoke

Invoke `/how` or `/poteto-mode`. Explicit-only skills retain `disable-model-invocation: true`. When the selected mode needs a companion, it reads that installed skill's instructions deliberately.

::: warning
Do not assume an explicit-only skill can be silently auto-selected.
:::

## Agents

Agent roles are `poteto-agent` and `comment-sicko`, with Markdown frontmatter and `model: inherit`. A native role or tool missing from the session gets a disclosed fallback. Queue work within actual nesting and concurrency limits.

::: warning Not a complete sandbox
The comment reviewer excludes Write and Edit and is instructed to avoid all writes, including Bash and MCP. Those exclusions alone are not a complete sandbox.
:::

## Model overrides

Use native model and effort configuration for requested overrides. Modified owned copies are preserved, and future installer runs report collisions.

::: info
The installer does not touch permissions, model settings, hooks, plugins, or MCP configuration.
:::

## Project instructions

Claude Code 2.1.281+ supports native AGENTS.md in the documented configurations. If a parent or project CLAUDE.md takes precedence or AGENTS.md support is disabled, use the documented project-instructions option or an explicit CLAUDE.md containing `@AGENTS.md`. Do not duplicate maintenance rules. This checkout supplies AGENTS.md only.

## Resume

```sh
claude --resume <id>
claude --continue
```

If history cannot be verified, use a labeled digest or handoff. Skill resources resolve from their real directory while target commands retain the project cwd.

## References

- [Skills](https://code.claude.com/docs/en/skills)
- [Subagents](https://code.claude.com/docs/en/sub-agents)
- [Project memory rules](https://code.claude.com/docs/en/memory)
- [Local validation](../validation.md)
