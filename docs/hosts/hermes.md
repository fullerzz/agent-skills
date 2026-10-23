# Hermes Agent setup

## Native plugin

The repository root is a native Hermes directory plugin: `plugin.yaml` identifies zstack and `__init__.py` registers every shared `skills/*/SKILL.md` through `ctx.register_skill`, plus native session hooks through `ctx.register_hook`. Resources stay beside their skills, including z-mode playbooks, references, and executable helpers. No build step or additional Python dependencies are needed to load the plugin. Mode controls and helpers require uv on the execution host.

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

All Hermes plugin skills require an explicit load. Installation and enablement do not select z-mode. Use the qualified name; a bare `how` can resolve to another skill. Follow the shared explicit-invocation rules.

Before merging, check:

1. From the PR checkout, run `hermes plugins doctor . --ci` and inspect `hermes plugins list` after installing.
2. Confirm `skill_view` loads `zstack:how` and `zstack:z-mode` from the installed plugin. Check a z-mode playbook and a sibling principle, including their resource paths.
3. Complete the small read-only prompt above. Select z-mode and verify the current session's enable control runs. Resume the same session, confirm activation is restored, then say `stop z-mode` and confirm the disable control runs and a subsequent resume stays inactive.
4. Start a new chat and fork a conversation if supported: each new ID must start inactive and supply its own controls. Check `/reset` or `/new` starts inactive without erasing the old conversation's saved preference.
5. Exercise compaction and note whether the session ID changes. Same-ID activation should survive; a replacement ID needs explicit mode selection again, as explained below. Never run controls inherited from the previous ID.
6. If explicitly requested, run one bounded read-only delegation using the host's native tools. The child's ID must not inherit activation. Report unavailable capabilities rather than inventing roles.

## Session hooks

The native `pre_llm_call` hook refreshes session-scoped POSIX and PowerShell enable/disable commands on each user turn. The assistant runs the matching command only when you explicitly select z-mode or opt out/switch styles. State is a reminder; a later user instruction wins. Installation and plugin enablement never activate z-mode.

State lives in `z-mode/<session-id>.json` beneath Hermes' documented `plugin_data_dir("zstack")`, normally `<HERMES_HOME>/plugin-data/zstack` in the active profile. The same shared renderer and control helper serve Codex, Claude Code, and Hermes. Missing or malformed state is inactive. Invalid session identity yields no executable controls; the adapter never substitutes a parent or task ID. Registration itself writes no state. Controls run Hermes' resolved Python interpreter directly. If a sandboxed terminal backend blocks a control, the context asks for one approved rerun and then hands you the command; this path has not been verified live on Hermes.

Explicitly enabled [Herdr execution](../reference/workflow-skills.md#herdr-workflow) uses a marker beside that state file with the same lifecycle. Herdr/Native controls change execution without changing z-mode activation. Enable preserves execution; Disable and reset remove both preferences. New IDs inherit neither. The hook changes preferences only; it never launches or inspects Herdr. The agent must run inside Herdr for control, and each CLI worker has its own configuration and scope. Playbooks keep their normal routing and acceptance criteria.

| Boundary | Behavior |
| --- | --- |
| Next turn or resume with the same ID | Restore explicit activation or opt-out, including after a process restart. |
| New chat, fork, or delegated child with a new ID | Start inactive and emit controls for that ID. Parent activation does not transfer. |
| `on_session_reset` | Clear the replacement ID supplied by Hermes; preserve the outgoing conversation for resume. A failed clear remains inactive in the running adapter and retries on the next turn. |
| `on_session_end` / `on_session_finalize` | No callback is registered; retain saved mode state for resume. Hermes end notifications are run boundaries, not proof the conversation is gone. |
| Compaction | Preserve state if the ID stays the same. If Hermes rotates the ID, explicitly select z-mode again. |

Hermes currently has no documented native plugin hook for **completed** compaction or a reliable native notification connecting the old and replacement IDs. Its `session:compress` notification belongs to the separate gateway `HOOK.yaml` system. This plugin does not transfer activation based on parent IDs or auxiliary model requests. Background forks that Hermes runs with persistence disabled skip `pre_llm_call`; they receive no fresh zstack controls and are a coverage gap.

## Host boundaries

The plugin does not register the Codex TOML or Claude Markdown agent roles. Workflows default to Hermes' available native delegation with a scoped brief and inherited configuration; explicitly enabled Herdr execution uses independent CLI sessions under the shared execution contract. The [native contract](../../skills/z-mode/references/native-hosts.md#hermes) explains resource resolution and capability reporting. The linked installer still targets Codex and Claude Code only.

Hook contracts follow the official [plugin API](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) and [lifecycle hooks](https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks), with native runtime evidence recorded in [validation](../validation.md#native-hermes-plugin).

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
