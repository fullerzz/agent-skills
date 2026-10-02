# Install and route work

## Install

1. Preview the installation and check for collisions.
2. Apply it.
3. Start a new session and invoke how on a small read-only question.

::: code-group

```sh [Claude Code]
uv run scripts/install.py --host claude
uv run scripts/install.py --host claude --apply
```

```sh [Codex]
uv run scripts/install.py --host codex
uv run scripts/install.py --host codex --apply
```

:::

::: code-group

```text [Claude Code]
/how explain how this command parses arguments; read-only, cite the source
```

```text [Codex]
$how explain how this command parses arguments; read-only, cite the source
```

:::

Skills remain linked to this checkout. Native agents are owned copies; model overrides use the host's configuration. [setup-pstack](../../skills/setup-pstack/SKILL.md) checks installation and requested settings without inventing model IDs.

## Host differences

| | Claude Code | Codex |
| --- | --- | --- |
| Invoke | `/how` | `$how` or the skill picker |
| Personal skills | `~/.claude/skills/<name>` | `~/.agents/skills/<name>` |
| Personal agents | `~/.claude/agents/` | `~/.codex/agents/` |
| Project skills | `.claude/skills/<name>` | `.agents/skills/<name>` |
| Project agents | `.claude/agents/` | `.codex/agents/` |
| Agent format | Markdown frontmatter, `model: inherit` | Standalone TOML |
| Explicit-only marker | `disable-model-invocation: true` | `policy.allow_implicit_invocation: false` |
| Details | [Claude Code setup](../hosts/claude-code.md) | [Codex setup](../hosts/codex.md) |

## Route work through poteto-mode

The [router](../../skills/poteto-mode/SKILL.md) reads only relevant playbooks and principle leaves. Small work runs directly. The first prompt below selects a feature workflow; the second selects investigation.

::: code-group

```text [Claude Code]
/poteto-mode add a --json flag; keep text output unchanged and verify both forms
/poteto-mode explain the retry path; no edits
```

```text [Codex]
$poteto-mode add a --json flag; keep text output unchanged and verify both forms
$poteto-mode explain the retry path; no edits
```

:::

::: tip Mode persistence
The mode lasts within conversational context until "stop poteto-mode". A resume note carries it to a new session.
:::
