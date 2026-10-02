# Zach's agent skills

A personal engineering skill library for Codex and Claude Code, adapted from Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack).

Shared instructions live in `skills/`. Each host uses its own native agents and model configuration. The library includes 46 skills, 23 engineering principles, 23 workflow playbooks, two native agent roles, and portable helpers.

## Install

Keep this checkout where its links can remain valid. uv runs the Python 3.14+ installer and structural validator, resolving their inline dependencies (Rich for output and PyYAML for validation). Node.js 20+ runs the helper tests; Bun runs the optional orchestration and PR tools. Install missing tools with mise or brew.

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

Skills are individual folder links. Agents are native owned copies, so you can customize model settings without editing this library. The installer previews all files, refuses collisions before writing, updates only unchanged owned agent copies, and never changes model or permission configuration. Existing pstack skills in your personal directories may collide; inspect the preview rather than overwriting them.

Start a new host session after installation. Invoke `$poteto-mode` or `$how` in Codex, and `/poteto-mode` or `/how` in Claude Code. A small first request:

```text
Explain how this command parses arguments. Keep this read-only and cite the source.
```

The explicit-only skills retain their invocation policy on both hosts. The mode reads relevant companion instructions when you select it. Simple work runs directly; broader investigations can use native agents. Missing capabilities and independent coverage are reported.

See [Codex setup](docs/hosts/codex.md), [Claude Code setup](docs/hosts/claude-code.md), and the [guide](docs/guide/README.md). Runtime evidence and remaining gaps are recorded in [validation](docs/validation.md).

## Remove

```sh
uv run scripts/install.py uninstall --host both
uv run scripts/install.py uninstall --host both --apply
```

Repeat the original `--project` or `--home` scope if used. Removal unlinks only this checkout's skill links and removes only unchanged owned agent copies. Modified or unowned files stay. Keep the checkout path stable; a moved checkout needs its original links uninstalled first.

## Workflows

- Understand with how, why, teach, recall, and blast-radius.
- Design and review with architect, arena, swarm, interrogate, and no-comments.
- Build with poteto-mode's bug, feature, refactoring, performance, and prototype playbooks.
- Verify with project harnesses and create-verification-skill.
- Resume long work with scoped history, durable handoffs, and show-me-your-work's decision log.
- Publish or merge only when the user's request authorizes those actions.

Cross-provider orchestration, marketplace packaging, and the old automation runtime are outside this release. Native independent runs may use the same model.

## Maintain

```sh
uv run scripts/validate.py
node --test scripts/*.test.mjs
uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'
cd skills/poteto-mode/scripts
bun install --frozen-lockfile
bun run test
bun run typecheck
```

The [adaptation plan](docs/adaptation-plan.md) records the approved scope and oracle findings. [Provenance](docs/provenance.md) records the copied version and retired content. The [MIT license](LICENSE) retains Lauren Tan's copyright.
