# Claude Code setup

## Native plugin

This checkout is also a Claude Code plugin. `.claude-plugin/plugin.json` registers the shared `skills/`, the `hooks/hooks.json` session hook, and the two `agents/claude/` roles. `.claude-plugin/marketplace.json` lists it as `zstack@zstack-local` with source `./`, so Claude Code loads the plugin in place from this checkout. There is no packaging step. The hook needs uv on the execution host.

If you already installed linked skills, preview and apply removal using the original scope first:

```sh
uv run scripts/install.py uninstall --host claude
uv run scripts/install.py uninstall --host claude --apply
```

Include the original `--home` or `--project` option if used, and preserve the same `CLAUDE_CONFIG_DIR` value for both commands if used. Keeping both installations enabled duplicates every skill and agent role.

From this checkout, register the local marketplace and install the plugin:

```sh
claude plugin marketplace add "$PWD"
claude plugin install zstack@zstack-local
```

Start a new session. Skills appear as `/zstack:how`, `/zstack:z-mode`, and so on; agent roles appear as `zstack:z-agent` and `zstack:comment-sicko`. Every skill except `setup-zstack` keeps `disable-model-invocation: true`, so `how`, `why`, z-mode, and the other workflows remain explicit in Claude Code; `setup-zstack` permits automatic selection there. Installation does not activate z-mode.

### Session hook

Claude Code runs the shared `SessionStart` Python helper through `hooks/hooks.json`. Its exec-form command passes `${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py` directly to uv as one argument, without shell expansion, including on Windows without Git Bash. Codex uses its own launcher in `hooks/codex.json`. Claude Code runs an enabled plugin's hooks without a separate trust review, so read `hooks/hooks.json` and `hooks/session_start.py` before installing. See Claude's [exec-form hook reference](https://code.claude.com/docs/en/hooks#exec-form-and-shell-form).

The hook supplies session-specific enable/disable commands. On explicit z-mode invocation the skill runs enable; on `stop z-mode` or a style switch it runs disable. Activation is restored on resume and compaction. Forked sessions (`--fork-session`, `/branch`) get child-scoped controls and do not inherit activation. Clearing resets it. Later user instructions take precedence over stored state.

The launcher explicitly selects the Claude host, so state lives in `CLAUDE_PLUGIN_DATA/z-mode/<session-id>.json`, by default `~/.claude/plugins/data/zstack-zstack-local/`, even when the environment contains an unrelated `PLUGIN_DATA`. Uninstalling the plugin deletes that directory unless you pass `--keep-data`.

The hook supplies labeled POSIX sh and PowerShell enable/disable commands. Use the variant matching the executing tool: POSIX sh for Bash, PowerShell for the PowerShell tool. This preserves paths containing apostrophes in either shell without guessing which tool is active. Claude can use PowerShell on Windows without Git Bash and can enable it on other platforms; see the [PowerShell tool reference](https://code.claude.com/docs/en/tools-reference#powershell-tool). Controls write outside the project, so Claude Code may ask for permission first. Missing or corrupt state means inactive. The hook does not authorize delegation or external actions.

### Optional xray recording

Start the host with `ZSTACK_XRAY=1` to retain minimal supported event metadata under `CLAUDE_PLUGIN_DATA/xray/claude/`. Recording is independent of mode activation and disabled by default. The user-only xray-session skill combines those records with transcript evidence. See [collection setup and limits](../reference/workflow-skills.md#optional-event-collection).

### Plugin update and removal

Because the plugin loads in place, checkout edits take effect at the next session start or after `/reload-plugins`. No version bump is needed. Keep the checkout at a stable path, because the marketplace records it.

```sh
claude plugin uninstall zstack@zstack-local
claude plugin marketplace remove zstack-local
```

Removing the marketplace also uninstalls its plugins. These commands manage the native plugin; the Python uninstall command manages the linked installation.

### Check the plugin and troubleshoot

```sh
claude plugin validate . --strict
claude plugin list
```

Confirm `zstack@zstack-local` is enabled. In a new session, run `/agents` to confirm the namespaced roles and check the command list for namespaced skills.

| Symptom | Check |
| --- | --- |
| Duplicate `/how` and `/zstack:how` | Remove the old linked installation in its original scope. |
| `claude plugin details zstack` reports `Agents (0)` | On Claude Code 2.1.288 the inventory omits agents listed in the manifest. Check `/agents`; the session still loads both roles. |
| Skills load but mode persistence is unavailable | Check that uv is on `PATH`, then look for hook errors in `/plugin` or a `claude --debug` log. |
| New agent file is missing | `plugin.json` must list every `agents/claude/*.md` file; `uv run scripts/validate.py` reports omissions. |

Enabled status proves registration, not skill execution. See the [validation record](../validation.md) for observed host behavior and remaining gaps.

## Install

The linked installation remains available for hosts without plugin support and for project-scoped installs. Use one method, not both.

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
