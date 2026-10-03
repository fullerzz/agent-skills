# Claude Code setup

## Install

Install Git, uv, and Claude Code, then [clone to a stable location](../guide/01-setup.md#first-time-setup). From the library checkout, preview the personal installation, inspect the output, then apply it:

```sh
uv run scripts/install.py --host claude
uv run scripts/install.py --host claude --apply
```

For an existing project, use the same scope in both commands:

```sh
uv run scripts/install.py --host claude --project "/absolute/path/to/project"
uv run scripts/install.py --host claude --project "/absolute/path/to/project" --apply
```

Use `--host both` to include Codex. Collisions stop installation before any writes; back up custom files and resolve the named conflicts or choose another scope. The installer cannot adopt another checkout's receipt.

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

Start a new session in the target project. Confirm `how` appears in the command list, then invoke `/how explain how this command parses arguments; read-only, cite the source`. Verify the response uses the intended skill and target source. Invoke `/z-mode` when ready to route broader work. Explicit-only skills retain `disable-model-invocation: true`. When the selected mode needs a companion, it reads that installed skill's instructions deliberately.

::: warning
Do not assume an explicit-only skill can be silently auto-selected.
:::

## Update and remove

From the original checkout, run `git pull --ff-only`, then repeat the preview/apply installation commands with the original scope. Skills update through their links; unchanged owned agent copies update on reinstall, while edited copies collide. Restart the session afterward.

To remove, preview `uv run scripts/install.py uninstall --host claude`, then repeat with `--apply`. Include the original `--project` or `--home` option and preserve the same `CLAUDE_CONFIG_DIR` value if used. Only this checkout's links and unchanged owned agent copies are removed; modified files remain. [Uninstall all scopes before moving the checkout](../guide/01-setup.md#uninstall-or-move-the-checkout).

## Agents

Agent roles are `z-agent` and `comment-sicko`, with Markdown frontmatter and `model: inherit`. A native role or tool missing from the session gets a disclosed fallback. Queue work within actual nesting and concurrency limits.

::: warning Not a complete sandbox
The comment reviewer excludes Write and Edit and is instructed to avoid all writes, including Bash and MCP. Those exclusions alone are not a complete sandbox.
:::

New tasks, fix rounds, and retries use fresh agents with consolidated briefs. Reuse requires costly agent-held state; stop or drain an old writer before assigning its files to a replacement. See the [native lifecycle contract](../../skills/z-mode/references/native-hosts.md#agent-lifecycle).

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
