# Hermes Agent setup

## Native plugin

The repository root is a native Hermes directory plugin: `plugin.yaml` identifies zstack and `__init__.py` registers every shared `skills/*/SKILL.md` through `ctx.register_skill`. Resources stay beside their skills, including z-mode playbooks, references, and executable helpers. No build step or additional Python dependencies are needed to load the plugin. Helpers that use uv still require uv on the execution host.

This follows Hermes' [native plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins#bundle-skills). Skills load as `zstack:how`, `zstack:z-mode`, and so on. Hermes owns registration cleanup and keeps plugin skills outside its mutable personal skill directory.

## Install

After this change merges, install from GitHub:

```sh
hermes plugins install fullerzz/agent-skills --no-enable
hermes plugins enable zstack
hermes plugins list
```

The repository's `package.json` belongs to the documentation site. If Hermes offers to install Node dependencies, answer **no**; the plugin does not use them.

### Test the draft PR

Before merge, pin the draft PR's full head commit. From a checkout of that commit:

```sh
PR_HEAD_SHA="$(git rev-parse HEAD)"
hermes plugins install fullerzz/agent-skills --ref "$PR_HEAD_SHA" --no-enable
hermes plugins enable zstack
hermes plugins list
```

Hermes requires a full 40-character commit SHA for `--ref`, not a branch name or abbreviated SHA. Review the existing installation before using `--force` to replace it. Pinned installs stay on that commit; choose a new SHA explicitly for the next test. These commands use the active Hermes profile. See Hermes' [plugin management guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins).

## Invoke and verify

Start a new Hermes session in the target project. Ask:

```text
Load zstack:how with skill_view, then explain this command's argument parsing.
Keep the investigation read-only and cite the source.
```

To select the engineering mode:

```text
Load zstack:z-mode with skill_view and use it for this task.
```

All Hermes plugin skills require an explicit load. Installation and enablement do not select z-mode. Use the qualified name; a bare `how` can resolve to another skill. Follow the shared explicit-invocation rules, including the direct-request requirement for `xray-session`.

Before merging, check:

1. From the PR checkout, run `hermes plugins doctor . --ci` and inspect `hermes plugins list` after installing.
2. Confirm `skill_view` loads `zstack:how` and `zstack:z-mode` from the installed plugin. Check a z-mode playbook and a sibling principle, including their resource paths.
3. Complete the small read-only prompt above, then select z-mode, say `stop z-mode`, and verify the opt-out is respected.
4. If available and explicitly requested, run one bounded read-only delegation using the host's native tools. Report unavailable capabilities rather than inventing roles.

## Host boundaries

Hermes has no zstack session hook in this package. Mode selection and opt-out persist through conversation context and resume notes only. The Codex/Claude session controls and xray recorder are not registered; xray-session can use available transcript evidence and must label missing coverage.

The plugin does not register the Codex TOML or Claude Markdown agent roles. Workflows use Hermes' available native delegation with a scoped brief and inherited configuration. The [native contract](../../skills/z-mode/references/native-hosts.md#hermes) explains resource resolution and fallback reporting. The linked installer still targets Codex and Claude Code only.

## Update and remove

For an unpinned GitHub installation:

```sh
hermes plugins update zstack
```

For a pinned draft installation, install again with `--force --ref "$PR_HEAD_SHA"` after reviewing the replacement commit. Restart Hermes after changes.

```sh
hermes plugins disable zstack
hermes plugins remove zstack
```

The [validation record](../validation.md#native-hermes-plugin) distinguishes local tests from the manual Hermes session checks still needed.
