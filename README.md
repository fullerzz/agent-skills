# zstack

My personal engineering skill library for Codex, Claude Code, and Hermes Agent, adapted from Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack).

Maintained for my own use and shared for reference and reuse under the [MIT license](LICENSE). I do not accept external issues or pull requests, and I do not provide user support. Please fork the repository for your own changes.

Shared instructions live in `skills/`. Workflows use native host agents by default, or Herdr execution when explicitly enabled. The library includes 51 skills, 24 engineering principles, 23 workflow playbooks, two native agent roles, and portable helpers.

> [!NOTE]
> Lauren Tan's upstream pstack library can be found at [**pstack**](https://github.com/cursor/plugins/tree/main/pstack) in the GitHub repo [cursor/plugins](https://github.com/cursor/plugins).

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

Hermes loads this repository as a native directory plugin through `plugin.yaml` and `register(ctx)`, exposing all shared skills as explicit `zstack:<skill>` loads:

```sh
hermes plugins install fullerzz/agent-skills --no-enable
hermes plugins enable zstack
```

These commands use the merged default branch. See [Hermes setup](docs/hosts/hermes.md) for draft-PR installation at an exact commit, verification, and removal. Decline any Node dependency prompt: `package.json` is for the docs site. Ask Hermes to load `zstack:z-mode` with `skill_view` to select the mode. Native hooks provide session-scoped mode controls and optional xray recording. Hermes uses native delegation fallbacks; the package registers no agent roles. See the setup guide for compaction and session-ID limits.

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

See [Codex setup](docs/hosts/codex.md), [Claude Code setup](docs/hosts/claude-code.md), [Hermes setup](docs/hosts/hermes.md), and the [guide](docs/guide/README.md). Runtime evidence and remaining gaps are recorded in [validation](docs/validation.md).

## Remove

For the native Codex plugin, run `codex plugin remove zstack@zstack-local`. See [plugin updates and marketplace removal](docs/hosts/codex.md#plugin-update-and-removal). For the Claude Code plugin, run `claude plugin uninstall zstack@zstack-local`; see [Claude plugin removal](docs/hosts/claude-code.md#plugin-update-and-removal).

For Hermes, run `hermes plugins remove zstack`; see [Hermes removal](docs/hosts/hermes.md#update-and-remove).

For linked installations:

```sh
uv run scripts/install.py uninstall --host both
uv run scripts/install.py uninstall --host both --apply
```

Repeat the original `--project` or `--home` scope if used. Removal unlinks only this checkout's skill links and removes only unchanged owned agent copies. Modified or unowned files stay. Keep the checkout path stable; a moved checkout needs its original links uninstalled first.

## Workflows

Select `$z-mode Use Herdr execution for this session` in Codex, `/zstack:z-mode Use Herdr execution for this session` in Claude Code's plugin, or ask Hermes to load `zstack:z-mode` with Herdr enabled. Existing bug-fix, feature, investigation, review, and queue workflows then use Herdr for their authorized delegated agents and useful long-running processes. Small work stays direct. Herdr must be available inside the calling pane (`HERDR_ENV=1`); enabling the preference does not attach an outside session.

"Disable Herdr execution" restores native execution while retaining z-mode. "Stop z-mode" clears both preferences. The shared native hooks remember them for the same session ID; new sessions and children require their own selection. With linked skills or older hooks, selection remains conversational. See [Herdr workflow](docs/reference/workflow-skills.md#herdr-workflow) for mechanics, limits, and resume behavior.

- Understand with how, why, teach, recall, and blast-radius.
- Design and review with architect, arena, swarm, interrogate, and no-comments.
- Build with z-mode's bug, feature, refactoring, performance, and prototype playbooks.
- Verify with project harnesses and create-verification-skill.
- Prevent repeated agent mistakes with correct, using architecture and automated enforcement before prose rules.
- Resume long work with scoped history, durable handoffs, and show-me-your-work's decision log.
- Inspect observable zstack activity in the current session with explicitly invoked [xray-session](docs/reference/workflow-skills.md#xray-session), a chronological ledger and ASCII diagram with history coverage gaps.
- Publish or merge only when the user's request authorizes those actions.

Herdr can launch a requested supported agent CLI with its own configuration; independent runs do not establish provider diversity or consensus. Public marketplace publication and the old automation runtime remain outside this release.

## Maintain

```sh
uv run scripts/validate.py
node --test scripts/*.test.mjs
uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'
uv run --with ty ty check skills/z-mode/scripts --extra-search-path skills/z-mode/scripts/orch --extra-search-path skills/z-mode/scripts/watch-pr
uv run --with mypy --with rich --with pyyaml --with types-pyyaml mypy
```

Run `just mypy` as a shortcut for the project-wide mypy check.

### Versioning

The Codex, Claude Code, and Hermes plugins share one `0.MINOR.PATCH` version in `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, and `plugin.yaml`. Validation fails if the manifests differ or leave `0.x`; reaching `1.0.0` is a deliberate change to that rule.

- Bump MINOR for incompatible or new behavior: added, removed, or renamed skills and agents, changed invocation policy, and hook or stored-state contract changes.
- Bump PATCH for compatible fixes and wording changes to packaged content.
- Changes that ship no plugin behavior or instructions, such as tests or the docs site, need no bump.

Run `just bump minor` or `just bump patch` (`uv run scripts/bump_version.py`) to update all three manifests together.

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

Every docs build includes `third-party-notices.txt` with the repository license and full notices from bundled client dependencies, including the fonts. The build stops if a dependency's notice is missing or empty. Keep these notices with the published site.

The [adaptation plan](docs/adaptation-plan.md) records the approved scope and oracle findings. [Provenance](docs/provenance.md) records the copied version and retired content. The [MIT license](LICENSE) retains Lauren Tan's copyright.
