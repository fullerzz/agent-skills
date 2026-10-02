# Install and route work

## First-time setup

Install Git, [uv](https://docs.astral.sh/uv/), and the host you intend to use: Codex or Claude Code. Use mise or brew for missing tools. The installer requires Python 3.14+; `uv run` resolves that version and its inline Rich dependency. Node.js 20+ is needed for helper tests and the documentation site; Bun is needed only for bundled orchestration and PR tools.

Clone the library to a stable location, then run all installer commands from that checkout:

```sh
git clone https://github.com/fullerzz/agent-skills.git "$HOME/Code/agent-skills"
cd "$HOME/Code/agent-skills"
```

Skills link back to this checkout. Keep it available at the same path for as long as the installation is in use.

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

The commands above install for your personal account. Use `--host both` to install both hosts together. For an existing target project, preview and apply with the same scope:

```sh
uv run scripts/install.py --host both --project "/absolute/path/to/project"
uv run scripts/install.py --host both --project "/absolute/path/to/project" --apply
```

Replace `both` with `codex` or `claude` for one host. `--home "/temporary/home"` selects an isolated personal root; it cannot be combined with `--project`. Empty scope values are rejected before writes.

The preview reports `create`, `keep`, `update`, or `collision`. Any collision stops the entire installation before writes, including when installing both hosts. Existing zstack folders, links to another checkout, and locally modified agent copies can collide. Inspect the named path, back up custom work, then choose another scope or resolve only that conflict. A receipt from another checkout is rejected rather than adopted.

To replace conflicting skills, such as a previous pstack installation, add `--force`. Preview first, then apply with the same scope:

```sh
uv run scripts/install.py --host both --force
uv run scripts/install.py --host both --force --apply
```

The preview marks these skills as `replace`. Applying deletes conflicting skill files or directories (including their contents) and replaces them with links to this checkout. Existing symlinks are replaced without deleting their destinations. Back up custom skills first. `--force` does not override agent or receipt conflicts, affect other installation locations, or change uninstall behavior; without `--apply`, it writes nothing.

## Check discovery

Start a new session in the target project. Check that `how` appears in the host's skill picker or command list, then run this read-only prompt:

::: code-group

```text [Claude Code]
/how explain how this command parses arguments; read-only, cite the source
```

```text [Codex]
$how explain how this command parses arguments; read-only, cite the source
```

:::

Skills remain linked to this checkout. Native agents are owned copies; model overrides use the host's configuration. [setup-zstack](../../skills/setup-zstack/SKILL.md) checks installation and requested settings without inventing model IDs.

Confirm the response uses the intended skill and cites the target command's source. An installer preview proves the file plan, not host discovery or behavior. If discovery fails, check the [host locations](#host-differences), restart the session, and follow the relevant host setup page.

## Update

From the original checkout, update the library and rerun the installation in each scope you installed. Use your original `--host` value; this example updates an installation for both hosts:

```sh
git pull --ff-only
uv run scripts/install.py --host both
uv run scripts/install.py --host both --apply
```

Repeat the original `--project` or `--home` option when applicable. Linked skills see checkout changes immediately; rerunning creates new links and updates unchanged owned agent copies. Edited agent copies produce a collision, so preserve those edits before resolving the conflict. Start a new host session after updating. For other removals or renames, the installer does not prune installed names that disappear from the checkout; uninstall before those updates.

### Migrate to zstack

Rerun the preview and apply commands above in each original installation scope. This rename does not require uninstalling first. On `--apply`, the installer atomically adopts the legacy `pstack-install.json` receipt as `zstack-install.json`, removes only owned `poteto-mode` and `setup-pstack` links and unchanged owned `poteto-agent` copies, and installs `z-mode`, `setup-zstack`, and `z-agent`.

Modified agent copies and foreign files remain with a warning. If you customized an old agent, transfer those customizations to the new agent and remove the old copy yourself when ready. Start a new host session and invoke `$z-mode` in Codex or `/z-mode` in Claude Code.

## Uninstall or move the checkout

Run removal from the original checkout while it still exists, using the same host, scope, and environment overrides as installation:

```sh
uv run scripts/install.py uninstall --host both
uv run scripts/install.py uninstall --host both --apply
```

Repeat `--project "/absolute/path/to/project"` or `--home "/temporary/home"` if used. Review `remove`, `preserve`, and `absent` in the preview. Removal unlinks only links pointing to this checkout and deletes only unchanged agent copies recorded in its receipt. Modified or unowned files remain; inspect them separately. Shared directories and host settings are left in place.

Before moving or deleting the checkout, complete these steps for every installed scope:

1. Run the uninstall preview and apply commands from the original checkout.
2. If modified agent copies are preserved, move those specific files to a backup directory outside the host's discovery directories. Keep the backups so you can reapply your customizations later; leave unrelated files alone.
3. Rerun the same uninstall preview and apply commands from the original checkout. The installer clears receipt entries for the now-absent agent copies. Confirm `zstack-install.json` is gone from the selected host's native configuration directory: `.codex/` or `.claude/` beneath the original personal/project root, or the configured `CODEX_HOME` / `CLAUDE_CONFIG_DIR` for a personal installation. If a receipt remains, inspect its recorded agents and resolve those retained files before proceeding.
4. Move the checkout and preview/apply installation from the new location with the same host and scope. Reapply your backed-up customizations to the newly installed agent copies. Those edited copies will again be preserved on uninstall and reported as collisions on reinstall.

Receipts record the source path. Moving first leaves broken links and causes receipt ownership errors. If already moved, restore the original path and follow the full cleanup above; uninstall alone does not clear a receipt for preserved modified agents.

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

## Route work through z-mode

The [router](../../skills/z-mode/SKILL.md) reads only relevant playbooks and principle leaves. Small work runs directly. The first prompt below selects a feature workflow; the second selects investigation.

::: code-group

```text [Claude Code]
/z-mode add a --json flag; keep text output unchanged and verify both forms
/z-mode explain the retry path; no edits
```

```text [Codex]
$z-mode add a --json flag; keep text output unchanged and verify both forms
$z-mode explain the retry path; no edits
```

:::

::: tip Mode persistence
The mode lasts within conversational context until "stop z-mode". A resume note carries it to a new session.
:::
