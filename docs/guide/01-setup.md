# Install and route work

## First-time setup

Install Git, [uv](https://docs.astral.sh/uv/), and the host you intend to use: Codex, Claude Code, or Hermes Agent. Use mise or brew for missing tools. The installer requires Python 3.14+; `uv run` resolves that version and its inline Rich dependency. Node.js 20+ is needed for repository integration tests and the documentation site. The bundled plan validator, worktree audit, orchestration CLI, and PR watcher use uv-managed Python 3.12+ and the standard library.

Clone the library to a stable location, then run all installer commands from that checkout:

```sh
git clone https://github.com/fullerzz/agent-skills.git "$HOME/Code/agent-skills"
cd "$HOME/Code/agent-skills"
```

Linked installations and the Claude Code plugin refer back to this checkout. The native Codex plugin uses a cached package, with this checkout supplying local marketplace updates.

## Install

Choose one installation method per host.

| Method | Includes | Use when |
| --- | --- | --- |
| [Native Codex plugin](../hosts/codex.md#native-plugin) | Namespaced skills and a session hook | You want plugin management and session-scoped mode persistence after trusting the hook. |
| [Native Claude Code plugin](../hosts/claude-code.md#native-plugin) | Namespaced skills, agent roles, and a session hook, loaded in place | You want plugin management and session-scoped mode persistence in Claude Code. |
| [Native Hermes plugin](../hosts/hermes.md) | Explicit namespaced skills and session hooks | You want Hermes plugin management, session-scoped mode controls, and optional xray recording. |
| Linked installer | Skill links and copied native agent roles | You need project-scoped installs or installer-managed Codex roles. |

### Native Codex plugin

From the checkout, stage the package and register its local marketplace:

```sh
uv run scripts/package_plugin.py
codex plugin marketplace add "$PWD"
codex plugin add zstack@zstack-local
```

Start a new session and select `zstack:how` in the skill picker for a small read-only question. Review and trust the session hook through Codex before using mode persistence. Installation does not activate z-mode. Only `how` and `why` permit automatic selection in Codex.

If you already use linked Codex skills, follow the [migration steps](../hosts/codex.md#native-plugin) first to avoid duplicate skills. The plugin does not register native agent roles; workflows use available roles or disclose a fallback. Plugin updates require restaging and refreshing the cached package; see [plugin update and removal](../hosts/codex.md#plugin-update-and-removal).

### Native Claude Code plugin

From the checkout, register its local marketplace and install the plugin:

```sh
claude plugin marketplace add "$PWD"
claude plugin install zstack@zstack-local
```

Start a new session and invoke `/zstack:how` for a small read-only question. Every skill except `setup-zstack` stays explicit in Claude Code. Installation does not activate z-mode.

If you already use linked Claude Code skills, follow the [migration steps](../hosts/claude-code.md#native-plugin) first to avoid duplicates. The plugin registers `zstack:z-agent` and `zstack:comment-sicko`. It loads in place, so checkout edits apply at the next session or `/reload-plugins`; see [plugin update and removal](../hosts/claude-code.md#plugin-update-and-removal).

### Native Hermes plugin

Install the repository with `hermes plugins install fullerzz/agent-skills --no-enable`, then `hermes plugins enable zstack`. Ask Hermes to load `zstack:how` with `skill_view` for a small read-only question. Installation does not activate z-mode. See [Hermes setup](../hosts/hermes.md) for draft-PR installation, the optional Node dependency prompt, resource loading, and manual validation.

### Linked installer

The remaining installation, discovery, update, and removal commands on this page describe linked installations. Keep their checkout at a stable path.

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

The preview reports `create`, `keep`, `update`, or `collision`. In a terminal, entries are grouped by host and operation; when output is piped, each entry is one tab-separated `operation  target  source` line. Any collision stops the entire installation before writes, including when installing both hosts. Existing zstack folders, links to another checkout, and locally modified agent copies can collide. Inspect the named path, back up custom work, then choose another scope or resolve only that conflict. A receipt from another checkout is rejected rather than adopted.

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

The table and [installation maps](visual-guide.md#from-checkout-to-host) describe linked installations. Native Codex plugin skills come from the plugin cache and use names such as `zstack:how`; the plugin does not register agent roles. Claude Code plugin skills and roles load from the checkout as `/zstack:how` and `zstack:z-agent`.

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
The mode remains selected until "stop z-mode" or a style switch. With the plugin hook (trusted in Codex, enabled in Claude Code), explicit activation is stored for that session and restored on resume or compaction; forks do not inherit activation, and clearing resets it. Without the hook, preserve the selection or opt-out in conversation context and resume notes. Installation alone never activates the mode.
:::
