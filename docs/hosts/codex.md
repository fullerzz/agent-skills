# Codex setup

## Install

From the library checkout, preview the installation, inspect the output, then apply it:

```sh
uv run scripts/install.py --host codex
uv run scripts/install.py --host codex --apply
```

Add `--project "/path/to/project"` for project installation.

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

Start a new session. Select a skill with `$how`, `$poteto-mode`, or the skill picker. Use a small read-only prompt and verify the host loaded the intended source. Explicit-only skills have `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.

## Agents

Native roles are `poteto-agent` and `comment-sicko`. They use standalone TOML with name, description, and developer_instructions. Model overrides are omitted to inherit native defaults. The comment reviewer uses read-only sandboxing. If custom agents or delegation are disabled, use the disclosed built-in or direct fallback.

::: warning Installation does not grant trust
Project agent discovery requires a trusted project and enabled native agents. Confirm those settings through Codex's native trust flow.
:::

::: warning Version-specific limit
On the tested CLI 0.160.0, delegated runs needed a persistent session: `exec --ephemeral` failed child rollout creation. See the [validation record](../validation.md).
:::

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
