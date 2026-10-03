# Codex setup

## Install

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

Start a new session in the target project. Confirm `how` appears in the skill picker, then invoke `$how explain how this command parses arguments; read-only, cite the source`. Verify the response uses the intended skill and target source. Select `$z-mode` when ready to route broader work. Explicit-only skills have `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.

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
- [Local validation results](../validation.md)

Documented discovery is distinct from behavior proven by this checkout's tests.
