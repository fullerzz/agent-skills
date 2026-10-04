# zstack

Zach's updated personal engineering skill library for Codex and Claude Code, adapted from Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack).

Shared instructions live in `skills/`. Each host uses its own native agents and model configuration. The library includes 50 skills, 24 engineering principles, 23 workflow playbooks, two native agent roles, and portable helpers.

## Install

Codex can load this checkout as a native plugin: shared skills plus one trusted `SessionStart` hook. See [Codex plugin setup](docs/hosts/codex.md#native-plugin) for installation, migration from linked skills, and hook trust. Only `how` and `why` permit automatic selection in Codex; z-mode and the other workflows remain explicit.

From this checkout, stage and install the native Codex plugin:

```sh
uv run scripts/package_plugin.py
codex plugin marketplace add "$PWD"
codex plugin add zstack@zstack-local
```

Start a new session and select `zstack:how` from the skill picker. Review hook trust separately. The plugin packages skills and the hook; it does not register native agent roles.

Claude Code loads the same checkout in place as a native plugin: shared skills, the same `SessionStart` hook, and both agent roles. See [Claude Code plugin setup](docs/hosts/claude-code.md#native-plugin) for migration from linked skills and hook behavior. Every skill except `setup-zstack` stays explicit in Claude Code.

```sh
claude plugin marketplace add "$PWD"
claude plugin install zstack@zstack-local
```

Start a new session and invoke `/zstack:how`. Checkout edits apply at the next session or `/reload-plugins`.

### Linked installation

Keep this checkout where its links can remain valid. uv runs the Python 3.14+ installer and structural validator, resolving their inline dependencies (Rich for output and PyYAML for validation). Node.js 20+ runs the repository integration tests. The optional orchestration, PR watcher, plan validator, and worktree audit use uv-managed Python 3.12+ and the standard library. Install missing tools with mise or brew.

From this checkout, preview and then apply the selected personal installation:

```sh
uv run scripts/install.py --host codex
uv run scripts/install.py --host codex --apply
```

```sh
uv run scripts/install.py --host claude
uv run scripts/install.py --host claude --apply
```

Use `--host both` for both hosts. For an explicit project installation, add `--project "/absolute/path/to/project"`. For isolated checks, `--home "/temporary/home"` targets a different personal root. Explicit `--home` and `--project` paths must be nonempty; an empty shell variable is rejected before any installation or removal.

Skills are individual folder links. Agents are native owned copies, so you can customize model settings without editing this library. The installer previews all files, refuses collisions by default, updates only unchanged owned agent copies, and never changes model or permission configuration. Add `--force` to preview replacement of conflicting skills and `--force --apply` to perform it. This deletes conflicting skill files or directories; symlink destinations are preserved. Back up custom skills first. Agent and receipt conflicts still block installation.

Start a new host session after installation. Invoke `$z-mode` or `$how` in Codex, and `/z-mode` or `/how` in Claude Code. A small first request:

```text
Explain how this command parses arguments. Keep this read-only and cite the source.
```

Explicit-only workflows retain their invocation policy. The mode reads relevant companion instructions when you select it. Simple work runs directly; broader investigations can use native agents. Missing capabilities and independent coverage are reported.

See [Codex setup](docs/hosts/codex.md), [Claude Code setup](docs/hosts/claude-code.md), and the [guide](docs/guide/README.md). Runtime evidence and remaining gaps are recorded in [validation](docs/validation.md).

## Remove

For the native Codex plugin, run `codex plugin remove zstack@zstack-local`. See [plugin updates and marketplace removal](docs/hosts/codex.md#plugin-update-and-removal). For the Claude Code plugin, run `claude plugin uninstall zstack@zstack-local`; see [Claude plugin removal](docs/hosts/claude-code.md#plugin-update-and-removal).

For linked installations:

```sh
uv run scripts/install.py uninstall --host both
uv run scripts/install.py uninstall --host both --apply
```

Repeat the original `--project` or `--home` scope if used. Removal unlinks only this checkout's skill links and removes only unchanged owned agent copies. Modified or unowned files stay. Keep the checkout path stable; a moved checkout needs its original links uninstalled first.

## Workflows

- Understand with how, why, teach, recall, and blast-radius.
- Design and review with architect, arena, swarm, interrogate, and no-comments.
- Build with z-mode's bug, feature, refactoring, performance, and prototype playbooks.
- Verify with project harnesses and create-verification-skill.
- Prevent repeated agent mistakes with correct, using architecture and automated enforcement before prose rules.
- Resume long work with scoped history, durable handoffs, and show-me-your-work's decision log.
- Inspect observable zstack activity in the current session with explicitly invoked [xray-session](docs/reference/workflow-skills.md#xray-session), a chronological ledger and ASCII diagram with history coverage gaps.
- Publish or merge only when the user's request authorizes those actions.

Cross-provider orchestration, public marketplace publication, and the old automation runtime are outside this release. Native independent runs may use the same model.

## Maintain

```sh
uv run scripts/validate.py
node --test scripts/*.test.mjs
uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'
uv run --with ty ty check skills/z-mode/scripts --extra-search-path skills/z-mode/scripts/orch --extra-search-path skills/z-mode/scripts/watch-pr
```

The documentation site in `docs/` uses VitePress, managed with pnpm:

```sh
pnpm install
pnpm docs:dev
pnpm docs:build
```

To build and serve the static site from nginx on http://localhost:8080:

```sh
docker compose up -d --build
```

Set `DOCS_PORT` to use a different host port, for example `DOCS_PORT=3000 docker compose up -d`.

The [adaptation plan](docs/adaptation-plan.md) records the approved scope and oracle findings. [Provenance](docs/provenance.md) records the copied version and retired content. The [MIT license](LICENSE) retains Lauren Tan's copyright.
