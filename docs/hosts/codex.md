# Codex setup

## Native plugin

The staged Codex package contains `.codex-plugin/plugin.json`, shared `skills/`, `hooks/`, and the license. It needs uv for the hook and the existing Node/Bun dependencies for optional helpers. Installation does not install those runtimes or grant hook trust.

If you already installed linked skills, preview and apply removal using the original scope before enabling the plugin:

```sh
uv run scripts/install.py uninstall --host codex
uv run scripts/install.py uninstall --host codex --apply
```

Include the original `--home` or `--project` option if used. Modified agent copies stay; inspect removal output. Avoid keeping both linked and plugin copies of the same skills enabled.

From this checkout, register the local marketplace and install its package:

```sh
uv run scripts/package_plugin.py
codex plugin marketplace add "$PWD"
codex plugin add zstack@zstack-local
```

The packaging command refreshes `dist/zstack` without Git history, installed dependencies, or personal configuration. The marketplace installs that staged directory. Optional Bun tools install their locked dependencies at their installed resource location when used.

The source and staged package use the native manifest because CLI 0.160.0 discovered its hook there, while a portable root manifest's OpenAI extension did not expose the hook on that tested host.

Start a new session. Plugin skills appear with names such as `zstack:how` and `zstack:z-mode`; select them through the skill picker. CLI 0.160.0 discovered all 48 skills in an isolated installation; see [validation](../validation.md) for the tested behavior and remaining live checks.

The plugin enables automatic selection only for `how` and `why`, limited to read-only code explanation and historical rationale. Codex uses their `agents/openai.yaml` policies; their shared `disable-model-invocation` flags retain explicit invocation in Claude Code. Select z-mode through the installed skill picker when you want its engineering style; installation does not activate it.

### Session hook

Review and trust the bundled hook through Codex's hook trust flow. A trusted `SessionStart` hook supplies brief orientation and session-specific enable/disable commands. On explicit z-mode invocation the skill runs the supplied enable command; on `stop z-mode` or a style switch it runs disable. The hook restores that session's activation on resume or compaction, with later user instructions taking precedence.

State lives in `PLUGIN_DATA/z-mode/<session-id>.json`; it is never shared between session IDs. Clearing a session removes its activation; a failed removal is reported because later resumes may still see stale state. Missing or corrupt state means inactive. Hook execution requires uv on the execution host. Without a trusted hook, mode persistence uses conversation context and resume notes. The hook does not authorize delegation or external actions.

The hook uses only the Python standard library. Its launcher skips uv configuration discovery and Python site initialization, ignores Python environment customizations, and imports control-only modules only when needed. Both startup and emitted mode controls use the same isolated launch options.

### Native agents

This package does not register `agents/codex/` as plugin roles. Existing native agent copies may still be used; otherwise workflows disclose a built-in or direct fallback. Use the linked installation below if you need the installer-managed native roles, and disable/remove the plugin to avoid duplicate skills. See [OpenAI's conversion guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin) for the distinction between reusable plugin skills and agent files.

### Plugin update and removal

For a local marketplace, update the checkout, rerun `uv run scripts/package_plugin.py`, then remove and add the plugin to refresh its cached package:

```sh
codex plugin remove zstack@zstack-local
codex plugin add zstack@zstack-local
```

Restart the session and review hook trust afterward. To uninstall, run only the removal command. Remove its marketplace separately with `codex plugin marketplace remove zstack-local` if no longer needed. These commands manage the native plugin; the Python uninstall command manages the linked installation.

## Install

The linked installation remains available for hosts without native plugin support and for installer-managed native roles.

Install Git, uv, and Codex, then [clone to a stable location](../guide/01-setup.md#first-time-setup). From the library checkout, preview the personal installation, inspect the output, then apply it:

```sh
uv run scripts/install.py --host codex
uv run scripts/install.py --host codex --apply
```

For an existing project, use the same scope in both commands:

```sh
uv run scripts/install.py --host codex --project "/absolute/path/to/project"
uv run scripts/install.py --host codex --project "/absolute/path/to/project" --apply
```

Use `--host both` to include Claude Code. Collisions stop installation before any writes; back up custom files and resolve the named conflicts or choose another scope. The installer cannot adopt another checkout's receipt.

::: info
Empty `--home` or `--project` values are rejected before any writes.
:::

## Locations

| Scope | Skills | Agents |
| --- | --- | --- |
| Personal | `~/.agents/skills/<name>` | `$CODEX_HOME/agents/` (default `~/.codex/agents/`) |
| Project | `.agents/skills/<name>` | `.codex/agents/` |

Skills are links; native agents are copies. An explicit `--home` uses that root's `.codex` for isolated testing. These are separate discovery locations.

## Invoke

Start a new session in the target project. Confirm `how` appears in the skill picker, then invoke `$how explain how this command parses arguments; read-only, cite the source`. Verify the response uses the intended skill and target source. Select `$z-mode` when ready to route broader work. Explicit-only skills have `agents/openai.yaml` with `policy.allow_implicit_invocation: false`; `how` and `why` permit automatic selection in Codex.

## Update and remove

From the original checkout, run `git pull --ff-only`, then repeat the preview/apply installation commands with the original scope. Skills update through their links; unchanged owned agent copies update on reinstall, while edited copies collide. Restart the session afterward.

To remove, preview `uv run scripts/install.py uninstall --host codex`, then repeat with `--apply`. Include the original `--project` or `--home` option and preserve the same `CODEX_HOME` value if used. Only this checkout's links and unchanged owned agent copies are removed; modified files remain. [Uninstall all scopes before moving the checkout](../guide/01-setup.md#uninstall-or-move-the-checkout).

## Agents

Native roles are `z-agent` and `comment-sicko`. They use standalone TOML with name, description, and developer_instructions. Model overrides are omitted to inherit native defaults. The comment reviewer uses read-only sandboxing. If custom agents or delegation are disabled, use the disclosed built-in or direct fallback.

::: warning Installation does not grant trust
Project agent discovery requires a trusted project and enabled native agents. Confirm those settings through Codex's native trust flow.
:::

::: warning Version-specific limit
On the tested CLI 0.160.0, delegated runs needed a persistent session: `exec --ephemeral` failed child rollout creation. See the [validation record](../validation.md).
:::

New tasks, fix rounds, and retries use fresh agents with consolidated briefs. Reuse requires costly agent-held state; stop or drain an old writer before assigning its files to a replacement. See the [native lifecycle contract](../../skills/z-mode/references/native-hosts.md#agent-lifecycle).

## Model overrides

For requested overrides, edit native agent `model` and `model_reasoning_effort` fields supported by your version, keeping them separate. User-modified copies are preserved; a later installer run reports the collision.

::: info
The installer does not enable agents, change permissions, or rewrite your configuration.
:::

## Resume

```sh
codex resume <id>
```

Use a saved task handoff when native history is unavailable. Resources resolve from the real installed skill file; Git commands stay in the target project. A read-only review does not authorize edits, messages, or PRs.

## References

- [Skills documentation](https://learn.chatgpt.com/docs/build-skills)
- [Native subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Plugin packaging and hook trust](https://developers.openai.com/plugins/build/plugins)
- [Local validation results](../validation.md)

Documented discovery is distinct from behavior proven by this checkout's tests.
