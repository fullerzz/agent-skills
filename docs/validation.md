---
outline: [2, 3]
---

# Validation

Historical observations below retain the names used during those runs (`pstack`, `poteto-mode`, and `poteto-agent`). Current equivalents are `zstack`, `z-mode`, and `z-agent`; those earlier observations do not establish live behavior under the new names.

## Herdr board plugin — 2026-10-06

The experimental `zstack.herdr` plugin (`herdr-plugin.toml`, `integrations/herdr/`) was checked on macOS with Herdr client and server `0.9.3` (private protocol `22`). Every live check ran on a disposable isolated server: `env -i` with a temporary `HOME`, minimal `PATH`, `TERM`, and `LANG`, which strips every `HERDR_*` and `XDG_*` variable. Before linking, each server showed a socket under the temporary `HOME`, `herdr plugin list` reported no plugins, and the snapshot was empty. Nothing was linked to the personal server. Its `plugins.json` hash matched before and after each phase, and its plugin list stayed unchanged. Teardown unlinked the plugin, stopped only the isolated server, and removed only its temporary directory.

Agents were simulated, not run. Raw `pane.report_agent` socket requests set a `custom:` occupant, then `herdr:<agent>` with an `agent_session_id` where a session was needed. No real Claude or Codex integration ran. Run files lived in temporary paths containing spaces.

Board and actions (E1–E10) all passed:

- Opening from an unenrolled pane opened nothing and wrote nothing.
- The board opened as a split from a worker without moving focus and refreshed every five seconds.
- With several runs it showed a choose-run screen.
- Artifact updates appeared without any Herdr event.
- A corrupt run file and an unreadable socket each showed `STALE` with the last good data, and each recovered.
- `q`, Ctrl-C, and closing the pane each ended the board process.
- Focus worked on `ok` and `moved` bindings. It was refused for `occupant changed`, `pane missing`, and agent-less panes.
- Metadata tokens used only the `zstack.herdr` source and left other sources' tokens intact.
- A plugin root containing a space worked.
- An orchestration-backed run rendered with its store byte-identical and no `.orch.lock`.

Caveats: `occupant changed` was produced by releasing the agent, not by a session swap, because Herdr ignored simulated session changes. Plain shell panes can't be focused by ID in 0.9.3.

Lifecycle hooks (L1–L9):

- **Passed: L1–L6, L8, L9.** Status transitions updated observations. Unrelated pane events wrote nothing (the state directory's hash was unchanged). Cross-workspace moves were observed as `moved`, and pane or workspace close as `pane missing`. Only this run's tokens were cleared when a pane stayed but its binding became invalid. With the lock held from outside, a hook skipped, and the open board still showed the current state. A server restart ran the startup hook (`alpha: ok`), left run files and the registry unchanged, and sent nothing to agents. Teardown was clean.
- **L7 passed with a caveat.** Detach and reattach of a headless pseudo-terminal client ran no startup hook and kept board processes and terminals unchanged. The detach was done by closing the pseudo-terminal; `ctrl+b q` sent as raw bytes did not detach.
- **Restart conditions:** agent resume was disabled in the isolated config, and restored panes got new terminals, so bindings showed `occupant changed` until rebound.
- **Simulated-agent limit:** status flips were shown only on a custom-only occupant. Once a `herdr:` session is claimed through the raw API, Herdr ignores later simulated state reports.
- **Hook behavior observed:** closing a workspace emits `workspace.closed` but no `pane.closed`. Startup hooks do not run on attach, link, or enable.

Clean copy (Phase 4):

- **Setup.** `git clone` of `HEAD` (`29f5bfa`) into `<temp>/clean copy/zstack repo`, overlaid with the working tree's modified and untracked, not-ignored files (excluding `.agent-work/`). The copy had no `__pycache__`, `.venv`, or `node_modules`, and was linked on a fresh isolated server.
- **Linking.** `herdr plugin link` reported that `plugin_root`, and `plugin action list` listed the three actions.
- **Boards.** Opening the board from the enrolled worker ran with its working directory in the copy (`lsof`) and rendered the run. An orchestration-backed run rendered `orch review · reported done` and its ledger evidence, with the store byte-identical afterward.
- **Hooks.** A `pane.moved` hook logged `alpha: ok` and wrote an observation under the isolated plugin state directory. After the isolated server restarted, the startup hook logged `alpha: ok` and `gamma: ok` and wrote both observations.
- **Provenance.** The copy's bytecode was removed beforehand. Afterward, `herdr_run` and orchestration `store` bytecode reappeared only in the copy, and the checkout's bytecode timestamps were unchanged.
- **Negative control.** With the copy's `skills/z-mode/scripts/orch` hidden, a new `open-board` failed with `ModuleNotFoundError: store`, even though the checkout still had that directory. This proved resource resolution from the plugin's own root and exposed the crash repaired in the continuation below.
- **Teardown.** Unlinking left no plugins, the isolated server stopped, and the temporary directory was removed. Only the personal server (unchanged, same PID) remained. `~/.local/state/zstack` and the plugin state directory did not exist.

Original four-phase static and unit checks on this host:

- `uv run scripts/validate.py`: 51 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: 15 of 15 passed, including the VitePress build and isolated installer tests.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 158 tests passed, 39 of them in `test_herdr_plugin.py`.
- Ruff check and format passed for the plugin files and their tests, and `git diff --check` passed.
- The new packaging tests parse the manifest with `tomllib` and check:
  - required fields and `min_herdr_version`;
  - unique, dot-free action and pane IDs;
  - every hook and command script resolving relative to the manifest directory;
  - POSIX-only platforms, matching the `fcntl` lock;
  - the orchestration directory under the manifest root;
  - no native package resource (`.codex-plugin`, `LICENSE`, `skills`, `hooks`) referencing `integrations/herdr`.
- Six temporary mutations each failed these tests and were then reverted: a `windows` platform, a missing script, a dotted ID, a duplicate ID, a removed `min_herdr_version`, and a hook file naming `integrations/herdr`. A static search found no skill, hook, agent, installer, or packager reference to the plugin. The native package and installer are unchanged.

### Continuation repairs — 2026-10-06

The continuation ran in Codex outside a Herdr-managed pane (`HERDR_ENV` absent), using native scoped workers. It issued no live Herdr commands and did not reuse the previous session's pane or controls. The personal `plugins.json` still matched its recorded SHA-256 baseline. Python checks used 3.14.7 through Homebrew `uv` 0.12.23; Node checks used 26.10.0. An inherited `mise` shim was inaccessible, so checks used the installed tools through an explicit `PATH`.

Two handoff defects were repaired and verified by 42 focused plugin tests:

- A copied package with no orchestration directory now reports an `orch_store` data gap. Fresh isolated interpreters exercised inspection, the board, all three actions, reconciliation, and an unrelated enrolled pane. These calls used a fake Herdr CLI, so they establish local behavior only. This repairs the earlier Phase 4 negative control's crash.
- `coordinator bind RUN_FILE --pane P` refreshes terminal and session identity for ordinary and orchestration-backed records. Fixtures verified recovery and preservation of labels, task data, acceptance, evidence, registry entries, and record bytes/timestamps when an invalid pane is supplied. Live restart recovery remains unverified.

An independent read-only review reproduced four additional defects, which were repaired:

- Registry/run identity drift is checked during action resolution, cached board refresh, focus, and hooks. A changed or replaced enrollment yields a data gap and preserves the previous visible state without acting on another identity.
- Board refresh now uses the hooks' existing label reconciliation against the current snapshot. It clears stale ownership after a missed occupant-change event and repairs missing labels without altering unrelated tokens.
- Run and task IDs are limited to 80 characters in CLI/schema validation and orchestration mapping. Display-only orchestration phases are normalized to Herdr's token limit, preventing repeated writes caused by normalization.
- The task ID `coordinator` is reserved in ordinary records and orchestration mapping, preventing focus-selector and observation-key collisions. Invalid orchestration IDs become a data gap; the adapter never rewrites the store.

Fresh coordinator verification after all implementation writers stopped passed: 165 Python tests (46 plugin tests), 15 Node tests including the VitePress build and isolated installer checks, 51 skills with zero structural problems, Ruff lint/format, tracked whitespace checks, and whitespace checks for all five untracked implementation artifacts. The personal `plugins.json` SHA-256 still matched its baseline. These repairs add no real-agent evidence.

These results are isolated-server and unit evidence with simulated agents or fake CLI calls. Not verified:

- real Claude or Codex agent integrations;
- the `ctrl+b q` detach key in a real terminal;
- Windows, which the manifest excludes;
- remote Herdr endpoints;
- `herdr plugin install` from GitHub, along with publication and personal installation;
- focusing non-agent panes, which 0.9.3 cannot do by ID;
- skip-if-held staleness: a skipped hook can leave an observation one event old until the next reconciliation; the board refresh updates its display and labels independently;
- live coordinator rebinding after a restart; the new command is verified only by fixtures.

## Selective pstack 0.15.12–0.15.13 guide port — 2026-10-05

Updated four guide pages with native Claude Code/Codex examples for prompting, prototypes, verification, benchmark validation, repeated-mistake prevention, and trust before unattended work. [Provenance](provenance.md) records the selection and cites both source commits. Skill behavior, invocation metadata, and plugin versions are unchanged. Removed existing trailing whitespace from the README note marker so structural validation passes.

On this macOS host, `uv run scripts/validate.py` reported 51 skills and zero structural problems; `node --test scripts/*.test.mjs` passed all 15 tests, including the actual VitePress build; `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'` passed all 119 tests. `git diff --check` passed. Commands used Homebrew uv and Node with `MISE_CACHE_DIR=/private/tmp/zstack-guide-mise` for isolated test subprocesses because the default mise shim was inaccessible in the sandbox.

Inspected the four generated guide HTML files for the new heading IDs, rendered examples, both host tabs, and rewritten skill links. The independent oracle review found no actionable issues in the guide, proposal, or provenance changes. These are structural, rendered-output, and existing regression checks; no browser interaction, native model adherence to the new examples, unattended run, scheduling, or deployment was exercised.

### PR #26 review repairs — 2026-10-05

The original checks above preceded removal of the review document in `a38ee4b`. After that deletion, structural validation reproduced two broken links in provenance and this entry. Removed both stale references, qualified planning by task complexity or user request, and aligned benchmark reporting with the skill's limiter and named-gap contract. Rechecks on this macOS host passed: 51 skills with zero structural problems, all 15 Node tests including the VitePress build, all 119 Python tests, and `git diff --check`. This repair adds no live host or deployment evidence.

## Public documentation notice and policy fixes — 2026-10-04

PR #25 review repair: the footer notice link now uses `/third-party-notices.txt`, matching the emitted root asset and sidebar link. A regression extracts the built footer's actual href and resolves it from `/`, `/guide/`, and `/hosts/codex`; it failed before the fix with `/guide/third-party-notices.txt` and passed afterward. All 15 Node tests (including the docs build), 119 Python tests, structural validation (51 skills, zero problems), and whitespace checks passed on macOS. This verifies URL resolution for the current root-hosted configuration; subpath hosting and browser clicks remain untested.

The README and docs homepage now state that zstack is maintained for personal use, shared for MIT-licensed reuse, accepts no external issues or pull requests, and provides no user support. Removed the VitePress edit invitation. The scoped Zach Fuller copyright, upstream Lauren Tan copyright, pstack attribution, and Catppuccin credit remain intact.

The docs build now emits `third-party-notices.txt` with the unchanged root MIT license and full license/notice files for included client JavaScript and loaded dependency CSS. On this checkout, it contains notices for 15 packages, including both Fontsource packages and the Vue runtime. A version-pinned copy of DocSearch's [v3.8.2 MIT license](https://github.com/algolia/docsearch/blob/v3.8.2/LICENSE) supplies the notice omitted from the published `@docsearch/css` package. Missing or empty notices stop the build; no dependency or manual notice-generation step was added. The home footer and project sidebar link to the generated text file.

On macOS, `uv run scripts/validate.py` reported 51 skills and zero structural problems; all 15 Node tests and 119 Python tests passed, and `git diff --check` passed. The new Node integration test builds the actual site through the VitePress CLI and verifies full font/repository/VitePress notices, Vue runtime coverage, the rendered policy, and removal of the edit invitation. An isolated fixture verifies that loaded CSS with missing or empty license text fails generation. Checks used `MISE_CACHE_DIR=/private/tmp/zstack-public-mise`.

A local VitePress preview returned HTTP 200 and `Content-Type: text/plain` for the notice file; its served contents exactly matched the build. HTTP reads also verified the homepage policy and footer download link, the guide's notice link, and the absence of the edit invitation. The task-owned preview was stopped afterward. This verifies local static serving, not deployment, Docker serving, browser interaction, or subpath hosting. GitHub contribution settings and visibility remain unchanged; no commit or publication was performed.

## Public visibility audit — 2026-10-04

Reviewed the tracked source and documentation, upstream MIT notice, installer and packaging boundaries, native hooks and optional recorder, bundled Git helpers, built-site assets, and current GitHub repository settings. The wiki footer now credits Zach Fuller for zstack adaptations and documentation while retaining Lauren Tan's upstream copyright, pstack attribution, and Catppuccin credit. The root MIT license is unchanged.

On this macOS host, structural validation reported 51 skills and zero problems; all 13 Node tests and 119 Python tests passed. The VitePress build and whitespace check passed. Commands used `MISE_CACHE_DIR=/private/tmp/zstack-public-mise` because the default mise cache was inaccessible in the sandbox. Installer tests used temporary configurations; no personal installation or native inference run was performed.

Gitleaks reported no secrets in 79 commits reachable through local Git refs (`--all`, including locally available remote refs), or in the 21 GitHub PR records and 21 issue/PR conversation comments returned by the API. This is pattern-based detection, not proof of absence; inline review comments, attachments, inaccessible or unreferenced history, and every historical personal detail were not exhaustively reviewed. GitHub reported a private repository, issues and pull requests enabled, pull request creation policy `all`, no Actions runs or artifacts, and no configured Pages site. Repository visibility and settings were not changed.

The full pnpm dependency audit reported four development-tool advisories (one high, three moderate) through Vite 5.4.21 and esbuild 0.21.5; the production-only audit reported none. These results do not demonstrate an exploit against the static nginx site. Update the docs toolchain before exposing a development server. The generated site contains 17 WOFF2 fonts with copyright and license-URL metadata but no full OFL text, and no standalone license/notice files. Include the Fontsource packages' full notices and review bundled client-library notices before distributing the docs build.

Remaining publication preparation: state the personal-use/no-external-contributions policy in the README and docs, remove the docs edit invitation, restrict GitHub issues and PR creation to collaborators (or disable them), and choose the public docs host. Project-subpath GitHub Pages hosting needs the matching VitePress base and a deployed link/asset check. The home-page skill count still says 50 although validation reports 51. Publishing the repository also exposes the author email already stored in commit metadata; changing future Git identity does not alter historical commits. Live deployment and fresh Codex/Claude/Hermes compatibility remain unverified by this audit.

## Herdr execution integration — 2026-10-04

Version `0.4.0` adds explicit Herdr execution selection alongside existing playbooks. The initial implementation stored execution alongside mode activation in the per-session JSON; the review fixes below moved execution to a separate marker. Native remains the default for legacy mode-only records. Herdr selection alone does not activate z-mode; enabling z-mode preserves execution; Native clears only the execution preference; Disable and clear/reset remove both. No hook launches or probes Herdr.

Local validation on macOS:

- `uv run scripts/validate.py`: 51 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 13 tests passed, including isolated installation and documentation reference coverage.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 114 tests passed. New regressions cover preference roundtrips, same-ID restore, child isolation, opt-out, legacy/invalid state, failed atomic writes, Hermes restart/reset behavior, and xray event reading. The added selection tests failed against the old helper before implementation.
- Ruff lint and format checks passed for the four changed Python files; project mypy passed for 27 source files. `pnpm docs:build` and `git diff --check` passed.
- An isolated Git fixture packaged the current resources, including all three new Herdr skill files, and verified byte equality plus relocated hook-to-skill references with paths containing spaces. This did not stage the working tree, refresh an installed plugin, or modify personal host configuration. Normal packaging includes tracked resources only, so the new skill must be tracked before packaging from the real checkout.

Actual Herdr checks: `HERDR_ENV=1` was present. Installed CLI help confirmed the documented pane and agent command surfaces. `herdr status` reported client/server `0.9.3`, private protocol `22`, compatible endpoint, and no restart required. Both `herdr pane current --current` and `herdr pane layout --current` returned `pane_not_found`. The attempted pane smoke stopped at caller resolution; no pane was created, no focus was changed, and no agent was launched. The operations reference now explicitly treats an unresolved caller as a blocker even when the environment flag is present.

The automated checks prove state/packaging contracts, not model adherence or live Herdr orchestration. Fresh installed-host selection, a valid-caller pane run/read/cleanup, agent startup/prompt/wait/blocked recovery, detach/pickup, remote coordination, and Windows PowerShell execution remain unverified. PowerShell quoting is covered by serialization tests only. Live checks should run in a disposable caller pane with task-owned resources and preserve unrelated work.

### Codex shared-daemon diagnosis — 2026-10-05

On macOS with Codex CLI `0.160.1` and compatible Herdr client/server `0.9.3`, the live Codex terminal process had the correct pane context, while the shared app-server daemon and tool shells inherited a nonexistent pane from another workspace. `herdr pane current --current` returned `pane_not_found`; supplying the pane ID verified from the foreground Codex process in a single read-only command resolved the correct live pane. No panes, agents, or servers were created, stopped, or restarted.

Installed CLI help confirmed `--no-daemon` for new and resumed sessions. A [maintainer comment on Herdr issue #4649](https://github.com/herdrdev/herdr/issues/4649#issuecomment-5869269080) explicitly recommends this workaround, and [Codex's daemon documentation](https://github.com/openai/codex/blob/main/codex-rs/app-server-daemon/README.md) confirms that shared clients use the daemon's launch-time environment without per-client isolation. The [guide](guide/herdr.md#known-codex-shared-daemon-issue) now documents the limitation. A fresh `--no-daemon` launch/resume and live orchestration remain unverified by this investigation.

### Review fixes: context size, control race, style switch — 2026-10-04

The SessionStart context now emits one control template per shell (`ACTION` replaced by enable, disable, herdr, or native) instead of eight full commands. With xray on and a realistic Codex data path, context went from 3924 to 2353 characters and keeps the full xray read commands. Herdr selection is a `<session>.herdr` marker beside `<session>.json`, so each control writes one file and parallel Enable/Herdr no longer lose a preference; read errors on the mode JSON no longer rewrite execution. Disable on a style switch is scoped to active z-mode, so a Herdr-only selection survives.

Local validation on macOS:

- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 117 tests passed. New regressions for parallel controls, real-length install paths under 4000 characters with full xray commands, and the scoped style-switch instruction all failed against the previous helper (the parallel test reproduced the lost Herdr preference).
- `uv run scripts/validate.py`: 51 skills, zero structural problems. `node --test scripts/*.test.mjs`: all 13 passed. Ruff lint/format, mypy on the helper, and `git diff --check` passed.

A Codex review flagged that sessions saved by the previous helper as `{"active": true, "execution": "herdr"}` would lose Herdr after upgrade. Reads now honor that legacy field, and every control first moves it into the marker and strips it from the JSON, so Native clears it for good. The upgrade regression failed against the unmigrated helper; afterwards 118 Python tests, 13 node tests, `validate.py`, ruff, mypy, and `git diff --check` passed.

Not verified: a live Codex session reading the new template, model adherence to `ACTION` substitution, and Windows PowerShell execution.

### Review fix: unambiguous control substitution — 2026-10-04

The shared hook now explicitly instructs executors to replace only the final `ACTION` argument and preserve every other argument, including paths and session IDs containing that text. The regression failed against the previous instructions, then passed with all four actions executed against an isolated copied helper and data directory containing `ACTION`. PowerShell serialization is checked too; live PowerShell execution and model adherence remain unverified. All 119 Python tests, 13 Node tests, skill validation (51 skills, zero problems), Ruff lint, the VitePress build, and `git diff --check` passed.

### Wiki coverage review — 2026-10-04

Reviewed the branch against `origin/main`, including the execution companion, playbook changes, hook controls, and follow-up state fixes. Added a [Herdr user guide](guide/herdr.md) with setup, workflow behavior, preference lifecycle, pause/pickup, troubleshooting, and upstream documentation links. Linked it from the sidebar and existing guides/reference, and corrected the long-work guide's native-only description.

Local checks passed: `pnpm docs:build`, all 13 Node tests, all 118 Python tests, `uv run scripts/validate.py` (51 skills, zero problems), and `git diff --check`. Inspected generated HTML to verify the guide/sidebar and upstream documentation links plus six linked heading targets. This was a static documentation check; no new live Herdr or browser interaction check was performed.

## Native Hermes plugin

### Correlation-ID review fix — 2026-10-04

Version `0.3.1` separates bounded metadata identifiers from filesystem-safe session identifiers. The pinned Hermes source below builds turn IDs as `session:task:suffix` and request IDs as `turn:api:n`; the original recorder rejected those colons. Metadata IDs now accept colons and up to 512 characters so compound IDs survive both capture and sanitized reading. Storage scopes retain the existing 128-character restriction and reject colons, traversal, and path separators.

The regression failed before the fix: native turn IDs disappeared, and a start/result from different turns with the same tool ID was incorrectly paired. After the fix, all 22 xray tests passed, including native ID roundtrips through the read CLI, distinct-turn correlation, long composite IDs, rejected malformed metadata, and strict filesystem scopes. Full validation passed on macOS: 108 Python tests, 13 Node tests, 50 skills with zero structural problems, Ruff lint/format, project mypy (27 files), and whitespace checks. These are isolated tests; no live model session or personal Hermes installation was exercised for this repair.

### Native hooks — 2026-10-04

The follow-up adds 12 native hooks to the Hermes plugin and bumps all three manifests to `0.3.0`. It shares the existing session control renderer and metadata recorder with Codex/Claude. Explicit activation survives same-ID resumes, process restarts, and same-ID compaction; reset clears only Hermes' replacement ID, and new children/branches do not inherit activation. Xray stays default-off and independent of mode selection. Its native observers retain bounded identities and outcomes while excluding raw event content, and observer failures cannot block a tool.

Contract research used the official [plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins), [observer hooks](https://hermes-agent.nousresearch.com/docs/developer-guide/observer-hooks), [gateway hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks), and upstream Hermes source pinned at [`439334127f012e1ee0685acd5dba288e459af0ec`](https://github.com/NousResearch/hermes-agent/tree/439334127f012e1ee0685acd5dba288e459af0ec). The adapter uses the documented profile-aware `plugin_data_dir("zstack")` API. No native completed-compaction hook connects old/new IDs: compression auxiliary calls are recorded as model-call boundaries only, and rotated IDs need explicit mode selection again. Persistence-disabled background forks skip the context hook and remain a coverage gap.

On this macOS host:

- Structural validation: 50 skills, zero problems. All 106 Python tests and 13 Node tests passed, including existing Codex/Claude regressions. The 12 Hermes tests passed again after the final type-checking changes.
- Ruff lint/format passed on all 10 affected Python files; project mypy passed for 27 files.
- A temporary staged plugin was loaded by the pinned upstream Hermes **Plugin Doctor**: 50 skills, 12 hooks, zero findings, version `0.3.0`. The check used `doctor_plugin` and the Doctor's isolated runtime from an upstream source checkout, not an installed personal Hermes CLI.
- An isolated integration harness invoked callbacks through Hermes' actual `PluginManager`: activation, same-ID subsequent-turn restoration, opt-out, reset, child isolation, qualified skill-tool capture, compression request capture, and unload cleanup passed. The generated control and read commands ran as subprocesses with their exact helper arguments; the parent capture contained 20 sanitized records, zero invalid records, and none of the private payload canaries. No model inference ran.

Unit fixtures additionally cover a new adapter restoring persisted activation, corrupt state, profile separation, invalid identities, failed clear and retry, default-off recording, fail-open observers, statuses including blocked/cancelled, native parent/child identifiers, and missing-identity ambiguity. VitePress build and `git diff --check` passed. Installed uv/Node binaries were used directly where mise shims could not access their runtime in the sandbox.

No personal Hermes installation or configuration changed. Real installation/enablement, model-driven `skill_view` and control execution, actual CLI/gateway resume/reset/compaction/fork flows, live delegation, and Windows remain for the user's [manual checklist](hosts/hermes.md#invoke-and-verify) before merge. Native loader/dispatcher checks establish callback integration, not those live behaviors.

### Initial skills-only package — 2026-10-04

The initial implementation added a root `plugin.yaml` and `__init__.py` using Hermes' documented `ctx.register_skill(name, path)` API. All 50 skills remained in the shared tree. That first adapter registered only skills, without Hermes hooks, recording, or native role files. The three host manifests shared version `0.2.0` and the bump helper updated them together. The hook follow-up above supersedes these initial behavior limits.

Reference review used the official [native plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins), [installation guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), and the upstream `PluginContext.register_skill` and installer source. The setup guide documents the optional Node-dependency prompt caused by this repository's docs-only `package.json`.

On this macOS host:

- `uv run scripts/validate.py`: 50 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 13 tests passed. `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 89 tests passed.
- Ruff lint and format checks passed for all six changed Python files; project mypy passed for 25 files. VitePress build and `git diff --check` passed. Checks used installed uv/Node binaries directly because the mise shims could not access their runtime normally inside the sandbox.

New registration tests load the actual entrypoint with a narrow recording context from a temporary package containing spaces, a separate working directory, and a symlinked install. They verify the complete shared skill inventory, sibling resources, playbooks and helpers, rejection of a missing skills tree, and skipping non-skill entries. Manifest/version regressions cover Hermes drift, missing entrypoints, and refusing partial bumps when the YAML version field cannot be rewritten.

These initial checks were local contract tests, not a live Hermes loader or model run. Hermes was not installed on this host and no personal installation or configuration was changed. The subsequent native loader checks and remaining manual gaps are recorded above.

## Shared v0 plugin versioning <Badge type="info" text="2026-10-04" />

The Codex and Claude Code manifests share one `0.MINOR.PATCH` version. Validation now rejects a Codex version outside `0.x` (Claude must already match it), and `scripts/bump_version.py`, exposed as `just bump minor|patch`, rewrites both manifests in place after refusing drift, non-v0 versions, or unknown parts. The README records the bump policy. Installed caches on this host are keyed by version: `~/.codex/plugins/cache/zstack-local/zstack/0.1.0` and Claude's `installPath` `~/.claude/plugins/cache/zstack-local/zstack/0.1.0`.

On this macOS host, structural validation reported 50 skills and zero problems; 83 Python tests, 13 Node tests, Ruff lint/format, and project mypy passed. `just bump patch` then `just bump minor` produced `0.1.1` and `0.2.0` in both manifests, which were restored to `0.1.0`; `just bump major` exited 1. No plugin was reinstalled, so host pickup of a bumped version was not exercised.

## Catppuccin wiki theme <Badge type="info" text="2026-10-03" />

PR #20 maps the VitePress color tokens onto Catppuccin Macchiato (dark) and Latte (light), switches Shiki to the matching Catppuccin themes, recolors the logo, and credits Catppuccin in the home-page footer. Hex values match `@catppuccin/palette` 1.8.0. VitePress shows the footer only on pages without a sidebar, so the credit appears on the home page alone.

Review follow-up: raw Latte accents fell below 4.5:1 as text on their own 14% tints and on mantle. Examples are the mauve tip badge at 3.93:1, yellow at 2.07:1, and green at 2.57:1. Latte now darkens the text-role (`-1`) shades with black: 85% for mauve, red, and blue, 65% for green, and 60% for yellow. Macchiato keeps its raw accents, which already passed (4.70:1 minimum). Fills and tints still use the raw palette.

On this macOS host, `pnpm docs:build` passed. Playwright (Chromium) runs against `vitepress preview` covered the home page, footer, `/skills`, `/guide/01-setup`, and `/guide/04-long-work` in both modes. Computed contrast against the composited background was: Latte tip badge 5.03:1, links 6.13:1, inline code 5.31:1, and tip titles 5.80:1. Macchiato measured 5.20, 6.84, 5.50, and 7.54. The yellow, red, green, and blue text shades were computed offline at 4.67:1 or higher on their tints. No rendered warning or danger callout or badge was measured, and no browser other than Chromium was checked. Structural validation reported 50 skills and zero problems. All 13 Node tests and 47 Python tests passed, along with the whitespace check.

## Python helper migration <Badge type="info" text="2026-10-03" />

Additional PR #21 review repairs trim frozen-stack items before their optional `#` prefix, decode watcher command streams and existing status reports explicitly as UTF-8, and update public setup/playbook guidance to Python/uv. Three regressions failed before repair and now cover whitespace-prefixed PR numbers, Unicode command stdout/stderr with a simulated CP1252 default, and a repeated Unicode status render with a simulated ASCII default. On macOS, all 81 Python tests, 13 Node tests, mypy (21 files), Ruff lint/format, structural validation (50 skills, zero problems), and the VitePress build passed. These encoding simulations do not establish native Windows behavior.

PR #21 review repair: inbox pointer reads now explicitly decode UTF-8, matching the writer. A regression with a simulated CP1252 default reproduced mojibake before the fix and verifies non-ASCII agent, unit, status, and report fields through both peek and drain afterward. All 78 Python tests, mypy (21 files), and Ruff lint/format passed on macOS. This simulation is not a native Windows run.

The `just mypy` recipe runs the uv command with Rich, PyYAML, and PyYAML stubs; invoking the recipe on this macOS host passed with no issues in all 21 source files.

Naming and type-check follow-up: renamed the three Python entrypoints to `check_plan.py`, `worktree_audit.py`, and `watch_pr.py`, including callers and fixtures. Removed the pytest-specific Ruff `PT` rules and obsolete unittest exemptions. Added `mypy.ini` covering all 21 project Python files in `scripts/`, `hooks/`, and the bundled helpers, with local import paths and checking of untyped function bodies. Fixed annotations, dynamic test-module declarations, optional loader/executable handling, and hook metadata narrowing. Existing callback aliases (`Stamp`, `Emit`, and `Fail`) now use Python's `type` statement. Mypy reports no issues; Ruff lint/format, ty, all 77 Python tests, 13 Node tests, whitespace checks, and structural validation (50 skills, zero problems) passed on this macOS host.

Reimplemented the plan validator, worktree audit, orchestration store/CLI, and PR watcher in standard-library Python, launched with `uv run`. The entrypoints declare Python 3.12+ with inline script metadata and no dependencies. Removed the TypeScript/JavaScript implementations, Bun manifest/lockfile, and dependency bootstrap. The existing `worktree-audit.sh` and extensionless `watch-pr` launchers forward to uv; active callers use the `.py` entrypoints. Existing orchestration TSV/Markdown/JSON files, watcher NDJSON schema, CLI modes, and exit codes remain supported.

Before replacement, all 58 Bun tests (226 assertions) and strict TypeScript checking passed. A temporary differential harness compared 96 watcher snapshot/event combinations against the original implementation; all matched. The Python regressions exercise existing store files, locking/recovery, malformed data, Graphite frontier pins, watcher blocker priorities, retries/deadlines, paginated review/check queries, queue advancement and sweep resumption, and actual uv subprocess entrypoints. Tests use temporary repositories and controlled `gh`/`gt` responses; no GitHub or Graphite state is changed.

Follow-up cleanup resolved the full Ruff findings by annotating the helpers and tests, adding reader/clock protocols, splitting complex CLI/store/watcher functions, and applying formatting and style fixes. The repository Ruff configuration is unchanged. Narrow exemptions retain the existing standard-library unittest conventions and explicit subprocess argument vectors without shell execution.

On this macOS host, the final checks passed: 50 skills with zero structural problems, 77 Python tests, 13 Node tests, ty checking of the bundled helpers with their two module search paths, full-repository `ruff check .`, `ruff format --check .` (149 files), and whitespace checks. Python type checking still allows dynamic JSON dictionaries and is not equivalent to the retired strict TypeScript check. Checks used installed uv/Node binaries directly because mise shims could not access their default cache in the sandbox.

Installed-resource tests ran from paths containing spaces and a separate target cwd, including Python entrypoints reached through symlinks. Worktree fixtures preserved untracked and ignored files and unknown-history classifications. Live GitHub/Graphite service behavior, native Codex/Claude loader reruns, and Windows execution were not tested. No personal installation, commit, or publication was performed.

## Agent-resistant design and performance mantras <Badge type="info" text="2026-10-03" />

PR #18 follow-up repairs make measurement and correctness checks an explicit per-mantra loop, with advancement after an unmet target and a report when supported options are exhausted. Reused results require invalidation for mutable inputs or proven input immutability throughout the cache's scoped lifetime. On this macOS host, structural validation reported 50 skills and zero problems; all 13 Node tests, 47 Python tests, and whitespace checks passed using `MISE_CACHE_DIR=/private/tmp/skills-review-mise`. These checks validate the repository and prose structure, not live model-driven optimization behavior.

PR #18 review repairs qualify same-change deletion for internal APIs without external compatibility obligations, preserve required deprecation and downstream migration periods, distinguish build-enforced visibility from private-by-convention APIs, and require an agreed measurable performance target before optimization. On this macOS host, structural validation reported 50 skills and zero problems; all 13 Node tests, 47 Python tests, and the whitespace check passed using `MISE_CACHE_DIR=/private/tmp/skills-review-mise`. These are static and harness checks; no live model-driven architect or perf run was performed.

Ported upstream a586282 and e43c7ee. Architect screens candidates as an agent contributor would change them and adds split-ownership, two-ways, importable-internals, and hand-synced-list red flags. Perf issue replaces its strategy list with seven ordered performance mantras and stops at the first that meets the target, keeping the local requirement that the trace supports each attempt. Hillclimb borrows only the mantra order for perf metrics; benchmark-checklist's cross-reference follows. Upstream version bumps have no local equivalent.

On this macOS host, structural validation reported 50 skills and zero problems; all 13 Node tests and 47 Python tests passed, and the whitespace check passed. These are prose-only changes; no live model-driven architect or perf run was performed.

## Optional xray event collection <Badge type="info" text="2026-10-03" />

Additional PR #17 repairs: directory validation now uses `lstat` and scanning catches only missing directories, preserving access failures for the CLI's sanitized `coverage.unavailable` response. Deterministic injected permission failures cover both ancestor inspection and directory listing, including private-error redaction; missing stores still read as empty. The context fallback test now uses a fixed budget instead of OS-dependent temporary-path length. File-mode assertions run only on POSIX, and privileged Windows symlink cases are isolated and skipped without dropping corruption/session-scope coverage. All 47 Python tests, 13 Node tests, structural validation, and Ruff checks passed on macOS. No live Linux or Windows run was performed; these test portability changes do not establish native Windows support.

PR #17 follow-up: Codex recorder launchers now check `ZSTACK_XRAY=1` before starting uv; Claude's three tool-event recorders use native `async: true` while retaining exec-form portability. All 45 Python tests, 13 Node tests, structural validation (50 skills, zero problems), and Ruff checks passed on macOS. Manifest-driven sentinel tests prove every Codex recorder skips uv for unset, empty, `0`, and `true` values, and preserves arguments and stdin for `1`, including paths with shell metacharacters. Claude configuration assertions verify asynchronous tool events and synchronous lifecycle events. Claude's documented async behavior allows delayed, reordered, or shutdown-cancelled records; no live tool-event timing, Windows execution, or speedup measurement was performed. The earlier native startup/shutdown result below predates this follow-up.

Added default-off `ZSTACK_XRAY=1` metadata recording through host-specific hook manifests and a standard-library recorder. Recording is independent of z-mode. Records use versioned, host/session-scoped atomic event files, native correlation identifiers, explicit zstack skill attribution where exposed, and actual outcomes from zstack's startup and mode controls. Prompts, arguments, commands, tool results, and transcript bodies are not persisted. The read command reports partial coverage, corruption, unfinished writes, soft-cap limits, unmatched calls, and identity ambiguity. Xray merges these records with transcript evidence and retains its transcript-only fallback.

On this macOS host, structural validation reported 50 skills and zero problems. All 43 Python tests and 13 Node tests passed, along with Ruff lint/format, the VitePress build, and whitespace checks. Tests exercise disabled recording, host/data isolation, privacy canaries, malformed input, traversal and symlink refusal, concurrent atomic writes, caps, corruption, actual internal outcomes, emitted read commands, and ambiguous correlation. Runtimes used `MISE_CACHE_DIR=/private/tmp/zstack-xray-mise` for the sandbox. No bundled Bun tools changed.

Claude Code 2.1.289 passed strict plugin-manifest validation. With an isolated unauthenticated profile and `ZSTACK_XRAY=1`, an actual `--init-only --plugin-dir` run emitted startup context and stored both the zstack `session_start` outcome and host `SessionEnd` event in Claude's own data directory, despite an unrelated `PLUGIN_DATA` value. The final source repeated this successfully, including explicit zstack attribution. No inference ran or personal configuration changed. Tool, subagent, and direct skill-expansion collection have fixture coverage; live inference-driven hook capture, live Codex collection, Windows execution, and overhead measurements remain unverified. Updated Codex hook definitions require native trust review after installation.

An independent `gpt-6.1-sol` review found two issues, both repaired: long paths could push optional read commands beyond the existing 4,000-character context budget, and missing actor identities could appear to form a resolved pair. Startup now uses a compact read reference when needed, with a long-path/active-mode regression; the reader exposes `ambiguous_tool_ids` with missing-identity regressions. A separate synthetic hybrid exercise merged before/after records with transcript calls once each, excluded unrelated and post-cutoff activity, and retained ambiguous evidence and coverage gaps. Its uncertainty about an internal startup record prompted explicit `attribution: zstack` on internal outcomes, covered by the emitted-read integration test. Synthetic evaluation does not establish access to complete real transcripts.

These checks did not update the personal plugin or enable recording in it. Opt-in setup, retention/deletion, limits, and transcript fallback are documented in the [workflow reference](reference/workflow-skills.md#optional-event-collection).

## Xray session <Badge type="info" text="2026-10-03" />

Added the user-only `xray-session` skill, chronological evidence ledger and ASCII hierarchy, workflow reference, and z-mode companion-routing exclusion. Both host invocation flags are enforced by validation. The isolated regression failed for missing, false, and string-valued shared flags before enforcement, then passed; it also rejects missing or permissive Codex policy.

On this macOS host, `uv run scripts/validate.py` reported 50 skills and zero structural problems. All 13 Node tests and 26 Python tests passed, along with Ruff lint/format checks, the VitePress build, and whitespace checks. Dependencies were installed from the frozen pnpm lockfile. Commands used `MISE_CACHE_DIR=/private/tmp/zstack-xray-mise` because the default mise cache was unavailable in the sandbox. No bundled Bun tools changed.

Claude Code 2.1.289 passed strict validation of the marketplace and plugin manifests. An isolated, unauthenticated `--init-only --plugin-dir` run loaded 50 plugin skills and successfully ran `SessionStart:startup`. No inference ran or personal configuration changed. The CLI's directory validator required a plugin manifest and could not validate the standalone skill folder directly; repository metadata checks cover that folder. These are discovery and structural results, not proof of live xray invocation or non-selection. Live Codex and Claude xray execution remain unverified. No plugin archive was built, and no personal installation, staging, commit, or publication was performed.

An independent `gpt-6.1-sol` agent applied the candidate to five synthetic scenarios: hook context and concurrent delegation with failures/retries; compaction and inherited fork history; no prior observed activity; direct versus generic/quoted invocation; and 36 helper operations with a duplicate export record. The reports retained all distinct long-fixture operations, removed only the duplicate, distinguished observed from reported activity, and omitted synthetic sensitive arguments. This was a supplied-evidence exercise, not actual archive retrieval or host skill selection. Review of the generated reports prompted clearer rules for file-load parentage, delegation reports, and retry cross-references; a retry alone does not establish nesting. A fresh `gpt-6.1-sol` agent then exercised the revised rule with a skill-file load, attributed helper failure, assistant-launched retry, and xray invocation: all four remained at root, with the retry linked by reference, and no concrete issue was found.

## Claude controls and state isolation <Badge type="info" text="2026-10-03" />

Fixed the two follow-up PR #15 findings. Each launcher now supplies an explicit host marker: Claude reads only `CLAUDE_PLUGIN_DATA`, while Codex reads only `PLUGIN_DATA`. The hook emits labeled POSIX sh and PowerShell enable/disable commands and instructs choosing the executing shell's variant. PowerShell literal quoting doubles straight and curly apostrophes and preserves dollar signs and backticks. Host selection no longer depends on inherited environment-variable precedence, and shell selection does not rely on a platform guess.

On this macOS host, structural validation reported 49 skills and zero problems; all 25 Python tests and 13 Node tests passed, along with Ruff lint/format and whitespace checks. Regressions cover inherited absolute and relative `PLUGIN_DATA` in Claude, unrelated Claude variables in Codex, Windows-path PowerShell serialization, and POSIX execution from a path with apostrophes and shell metacharacters. Existing enable/disable, clear, fork, and session-isolation checks remain green.

Claude Code 2.1.288 passed strict validation of both manifests. An isolated, unauthenticated `--init-only --plugin-dir` run with `PLUGIN_DATA=unrelated-relative` loaded 49 skills and both agents, then successfully executed `SessionStart:startup`. Its 2,007-character context contained both shell variants and the isolated `CLAUDE_PLUGIN_DATA` path. No inference ran or personal configuration changed. An independent `gpt-6.1-sol` review found no actionable issues. Neither PowerShell nor Windows is available on this host, so PowerShell quoting has fixture and static-review coverage only; live PowerShell execution and a live Codex session remain unverified. The changed Codex launcher requires reviewing hook trust after updating.

## Claude plugin PR review fixes <Badge type="info" text="2026-10-03" />

Addressed all three PR #15 findings. Validation now reports a missing Claude manifest and marketplace independently; regression cases for either missing file and both missing files failed before the fix and pass afterward. Migration instructions now preserve the original `CLAUDE_CONFIG_DIR` for both uninstall commands.

Replaced the shared POSIX fallback launcher with separate host configurations. Claude's default `hooks/hooks.json` uses exec-form `command` and `args`, passing the plugin path without a shell. The Codex manifest points to `hooks/codex.json`, which retains the `PLUGIN_ROOT` shell command and context limit. Both launch the unchanged shared Python helper. The hook regression executes Claude's argument vector from a plugin path containing spaces, an apostrophe, a dollar sign, and backticks, then exercises its emitted enable control. The Codex regression reads its manifest's hook path and succeeds even with an unrelated `CLAUDE_PLUGIN_ROOT` present.

On this macOS host, Claude Code 2.1.288 passed strict validation of both manifests. An isolated, unauthenticated `CLAUDE_CONFIG_DIR` and `--init-only --plugin-dir` run loaded 49 skills, both agent files, and exactly one configured hook. Debug output confirmed successful `SessionStart:startup` execution and valid additional context from the exec-form launcher. No inference ran or personal configuration changed. Windows execution and a live Codex loader/session rerun remain unverified; the Windows fix follows Claude's documented exec-form contract.

Structural validation (49 skills, zero problems), all 24 Python tests, all 13 Node tests, Ruff lint/format checks, the VitePress build, and whitespace checks passed. A six-pair Codex benchmark smoke run against the PR head completed all scenarios with zero failures; this is compatibility evidence, not a new performance claim. Packaging with a temporary Git index and object directory included the new Codex configuration, and the packaged manifest resolved it successfully. The real Git index was unchanged. Commands used `MISE_CACHE_DIR=/private/tmp/zstack-pr15-mise` because the default mise cache was unavailable in the sandbox.

## Claude Code plugin <Badge type="info" text="2026-10-03" />

Added `.claude-plugin/plugin.json` and a `zstack-local` marketplace whose plugin source is the checkout root. The manifest lists both `agents/claude` roles; skills and `hooks/hooks.json` use Claude's default locations. The shared hook command now resolves `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`, and the script reads `PLUGIN_DATA`, falling back to `CLAUDE_PLUGIN_DATA`. The z-mode activation rule and agent references name both hosts. The validator requires matching plugin versions and a manifest entry for every Claude agent file.

Claude Code 2.1.288 ran with a temporary `CLAUDE_CONFIG_DIR`, unauthenticated, so no inference ran and no personal configuration changed. `claude plugin validate . --strict` passed for the marketplace and the plugin manifest. A probe plugin showed that hooks receive `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, and `CLAUDE_PROJECT_DIR`, but not `PLUGIN_ROOT` or `PLUGIN_DATA`. The previous hook command would therefore have failed. The probe also showed that the `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}` fallback resolves, and that Claude tolerates the Codex `additionalContextLimit` field and the anchored matcher.

After install, debug logs showed the plugin loading from the checkout: 48 skills, both agent files, and the hook, which returned 1,493 characters of context. `--agent zstack:z-agent` and `--agent zstack:comment-sicko` resolved, while an unknown name listed both roles as available. An emitted enable control wrote state under `plugins/data/zstack-zstack-local/z-mode/`. `--resume` then reported source `resume` with z-mode enabled. `--resume --fork-session` reported source `fork` with no stored activation, and the parent state was unchanged. `claude plugin details` reported `Agents (0)` for manifest-listed agents, even though the session loaded them. Install also copied the full checkout into the plugin cache, but the session loaded from the source path.

Structural validation passed (48 skills, zero problems). All 13 Node tests passed. All 22 Python tests passed, including a hook run with only Claude variables set and a validator check for omitted agents. Ruff, the VitePress build, and a `dist/zstack` rebuild also passed. The Codex hook command changed, so the existing trust no longer matches and must be reviewed again. The fixture still runs that command with only `PLUGIN_*` variables. No live Codex session was run after this change.

These checks did not include model-driven skill invocation, executing controls from natural language, live `/clear` or compaction, interactive `/agents` output, or Bash-tool permission prompts for the controls.

Review follow-up:
- The hook benchmark now finds the helper path in both old and new command forms and ignores inherited `CLAUDE_PLUGIN_*` variables. Six-pair smoke runs against `HEAD` and the pre-rename baseline `2b873c9` each completed every scenario with zero failures. These were compatibility checks, not new performance results.
- The docs now say that `setup-zstack` permits automatic selection in Claude Code, which matches its frontmatter.
- The home-page plugin card now links to the installation choices for both hosts.
- The Codex docs now say to trust the changed hook again.
- The validator now requires a `zstack-local` marketplace with a root-source `zstack` plugin.

After these changes, structural validation (48 skills, zero problems), 13 Node tests, 23 Python tests, Ruff, `claude plugin validate . --strict`, the VitePress build, and the whitespace check passed.

After rebasing onto PR #14, which added the `correct` skill, structural validation reported 49 skills and zero problems. All 13 Node tests and 23 Python tests passed. Ruff, `claude plugin validate . --strict`, and the VitePress build also passed. The isolated Claude session loaded 49 plugin skills, and its startup hook ran successfully.

## Correct skill <Badge type="info" text="2026-10-03" />

PR #14 review remediation explicitly gates rule-table updates and rule cleanup on authorized repository edits. Review-only invocations return the proposed table and rule changes in the report without modifying files. Structural validation passed (49 skills, zero problems), and whitespace checks passed. A direct instruction walkthrough checked both review-only and authorized-edit paths; this is prose verification, not a live model-driven run.

Ported upstream 9511e603's repeated-mistake prevention workflow with explicit-only metadata for Codex and Claude Code. Preserved the prevention hierarchy and rule table, while scoping history access, requiring isolated historical reproductions, and keeping commits and future invocation outside the skill's authority. Updated the catalog references and current skill counts; historical host results below remain unchanged.

Structural validation passed with 49 skills and zero problems, all 13 Node tests and 20 Python tests passed, and the VitePress production build and whitespace check passed. The first Node run lacked VitePress; installing the frozen pnpm dependencies resolved it. Commands used Homebrew's uv on PATH and a temporary mise cache for pnpm. A temporary-home installation for both hosts verified that each `correct` link resolves to this checkout and exposes the explicit-only policy. No personal skill installation was changed.

A direct instruction walkthrough covered a commit plus its review (one incident), two independent recurrences (eligible class), a review-only request (no edits), unavailable history (reported gap), and a configured but unexecuted CI check (no passing-CI claim). This is prose review and installer verification, not a live model-driven correction run or fresh native host discovery. No bundled executable tools changed.

## Documentation refresh <Badge type="info" text="2026-10-03" />

Updated the README, site home, setup guide, navigation, visual-guide scope, workflow reference, and provenance to distinguish native Codex plugin installation from linked installation. Corrected the Codex setup-zstack invocation policy and documented plugin discovery checks, troubleshooting, cached updates, native-role limits, and session-scoped mode persistence.

On this macOS host, structural validation passed with 48 skills and zero problems, all 13 Node tests and 20 Python tests passed, and the VitePress production build passed. Installer and hook tests used isolated fixtures. Commands used `MISE_CACHE_DIR=/private/tmp/zstack-docs-mise` after the default mise shim failed under the sandbox.

Codex CLI 0.160.0 reported zstack@zstack-local version 0.1.0 installed and enabled. This chat received the installed hook's session-specific orientation and inactive-mode status. A direct read-only resume-event invocation of that installed hook exited successfully and returned matching controls and inactive state. CLI help and plugin listing exited successfully despite a PATH-alias creation warning; the hook did not emit that warning. No plugin installation, trust setting, activation state, or personal configuration was changed by these checks.

This verifies current registration, delivered session context, and direct hook output. It does not establish model-driven implicit selection, mode activation/opt-out, or live resume/fork behavior. The documentation build is not a fresh browser or deployed-site check.

## Codex plugin <Badge type="info" text="2026-10-03" />

PR #12 review repairs enforce the Codex invocation allowlist for every skill, including an explicit false policy for setup-zstack, and exclude only the generated root dist directory from validation. Hook controls accept leading-hyphen IDs and fork events provide child-scoped controls that supersede inherited parent controls. Packaging uses a Git-tracked resource inventory, excludes ignored files, rejects wrong resource types, and checks symlink routes against packaged resources. Regression fixtures cover nested dist content, absent/malformed policies, executed controls and parent/child isolation, resource types, omitted symlink routes, and untracked personal files. `just check`, structural validation (48 skills), 13 Node tests, 20 Python tests, the documentation build, and a tracked-resource package rebuild passed. These are direct fixture checks, not proof of model-driven fork handling.

The added Ruff annotation (`ANN`) and complexity (`C901`) rules pass through `just check`. Typed helpers separate installer receipt loading, planning, and application; validator checks; package resource validation; hook state restoration; and benchmark execution. No new rule suppressions or hook runtime imports were added for these rules. Structural validation (48 skills), 13 Node tests, 14 Python tests, and a six-pair hook benchmark smoke check passed; the staged package was rebuilt.

The user-provided Ruff configuration and `just check` recipes now pass for the Python sources. Formatting/import fixes and bound benchmark closures were applied; benchmark verification uses explicit errors so Python optimization cannot disable it. Documented rule exceptions preserve measured hook startup imports, lexical installer path handling, the stdlib unittest runner, trusted subprocess fixtures, the SafeLoader subclass, and independent helper-error reporting. Structural validation, 13 Node tests, 14 Python tests, and the historical-baseline benchmark smoke check passed. The user's justfile and Ruff configuration were unchanged.

Renamed the hook to `session_start.py` and updated its configured command and tests. The benchmark reads each revision's helper filename from its hook configuration, preserving comparisons against pre-rename commits. Structural validation, 13 Node tests, 14 Python tests, and a six-pair historical-baseline benchmark smoke check passed; the smoke check establishes compatibility, not a new performance result. The staged package was rebuilt with the renamed hook.

### Hook startup optimization

The hook now defers argparse until a mode control runs and tempfile until enable writes state, uses os.path without importing pathlib, resolves its helper location once, and skips a redundant read after clear. The configured command and emitted controls use `--no-config` plus Python `-I -S` to avoid uv configuration discovery, Python environment customizations, and site initialization. State validation, atomic replacement, shell quoting, and opt-out failure reporting remain intact. The configured-command regression also runs with invalid local uv configuration and a PYTHONPATH site customization that must not execute.

Two independent runs of `uv run scripts/benchmark_codex_hooks.py 2b873c9` each used 20 alternating AB/BA pairs per scenario after two warmups per side. Every measured process ran the full configured shell/uv/Python command, returned valid context and controls, and checked clear's file removal; failed commands or assertions abort the run. State was reset outside each timed region. Across both runs, each side completed 40 samples per scenario with zero failures. On this macOS host with Python 3.14.7, 14 logical CPUs, and starting load averages 3.12/3.14/2.99:

| Scenario | Before median (range), ms | After median (range), ms |
| --- | --- | --- |
| Inactive startup | 88.84 (86.83–95.67) | 81.22 (78.63–89.83) |
| Active startup | 88.83 (87.08–94.56) | 80.88 (78.91–85.89) |
| Clear | 89.18 (86.39–93.53) | 81.44 (78.56–86.67) |

Active startup is about 9% faster in this fixture. A separate import profile attributed about 5.2 ms to tempfile and its dependencies before optimization; it is absent from the normal startup import path afterward. An empty optimized shell/uv/Python launch had a 75.52 ms median (73.62–77.70 ms, ten measured runs), so launcher overhead dominates the remaining time. These are warmed fresh-process hook timings, not cold-disk measurements or end-to-end Codex turn latency. Both variants used the same inherited launcher environment and temporary mise cache; no claim is made that all hosts will see the same improvement.

Added a native Codex package, local marketplace, clean staging command, and a session-scoped z-mode hook. Only how and why opt into Codex implicit invocation; Claude invocation flags remain unchanged. Native agent roles still use the existing installer or disclosed built-in fallback.

Codex CLI 0.160.0 installed the staged package in a temporary `CODEX_HOME`. Auth-free app-server `skills/list` discovered all 48 enabled, namespaced plugin skills with no loader errors. `hooks/list` and `plugin/read` discovered the SessionStart hook as untrusted. Trusting its exact reported hash in that temporary profile changed its native trust status to trusted. No credentials were copied and no personal configuration was changed.

The native manifest is deliberate: on this CLI, a portable root manifest exposed skills but did not expose its OpenAI-extension hook declaration. A compatibility manifest alongside that root did not fix discovery; using only `.codex-plugin/plugin.json` did. Installing the checkout directly also copied Git history and dependencies, so the local marketplace now uses `dist/zstack`, containing only the manifest, license, skills, and hooks. The final cached package contained neither `.git` nor `node_modules`.

Structural validation passed with 48 skills and zero problems after staging. All 13 Node tests, 14 Python tests, the VitePress production build, and whitespace checks passed. Hook tests execute the configured command and its emitted enable/disable commands in temporary directories; they cover inactive defaults, session isolation, resume/compaction, clear, corrupt state, invalid identities, and reported reset failure. Packaging checks cover resource preservation, dependency exclusion, rebuilds, and symlink boundaries. A regression keeps generated packages out of source validation. Commands used a temporary `MISE_CACHE_DIR` because the default mise shim failed under the sandbox.

These checks do not prove model-driven implicit skill selection, execution of mode controls in response to natural language, or lifecycle hook execution during a real model turn. The isolated native thread was created without inference; hook commands were exercised directly by fixtures. Desktop/remote/Windows behavior, public marketplace publication, and Claude plugin packaging were not exercised. Hook trust and uv on the execution host remain required; failed mode-state updates must be reported, and user opt-out takes precedence over stored state.

## PR workflow <Badge type="info" text="2026-10-03" />

PR #11 review remediation explicitly marks only Tradeoffs and Blast Radius as optional and defines when Blast Radius may be omitted, matching the user reference. Structural validation (48 skills, zero problems), both documentation reference tests, the VitePress build, and whitespace checks passed. This is documentation validation, not live host behavior.

Ported upstream 23e4138's built-in PR-tool preference and concise description headings. The workflow keeps repository templates and requested draft status, falls back per unsupported operation, and requires host registration even after CLI creation. Queue publication routes through the shared PR playbook.

Structural validation passed (48 skills, zero problems), all 13 Node tests and four Python tests passed, and the VitePress build and whitespace check passed using the temporary mise cache. A direct instruction walkthrough covered a partial-capability PR tool (fallback only for missing operations), an attachment-only tool (create through forge tooling, then attach), a requested draft (preserve it), and a child PR (target its parent). This is prose validation, not fresh autonomous host behavior. The task's actual stack publication uses gh-stack plus host attachment because no built-in creation tool is exposed.

## Agent lifecycle <Badge type="info" text="2026-10-03" />

PR #9 review remediation makes the reviewed-defect handoff explicitly target a fresh owner with the prior scope, directives, report, and artifact paths. The shared state-dependent reuse exception and safe writer handoff still apply. Structural validation (48 skills, zero problems), both documentation reference tests, the VitePress build, and whitespace checks passed. This is instruction and documentation validation, not live agent execution.

Ported the fresh-agent default from upstream 23e4138 into the shared native contract, mode, agent descriptions, swarm retries, and queue playbooks. Consolidated briefs carry prior directives and artifacts; costly agent-held state permits reuse. Replacement writers must not overlap the previous writer's scope.

Structural validation passed (48 skills, zero problems), all 13 Node tests and four Python tests passed, and the VitePress build and whitespace check passed using the temporary mise cache. A direct instruction walkthrough covered a completed worker's fix round (fresh agent), a needed live watcher (reuse), and an unconfirmed writer termination (separate scope or blocker). This is a prose walkthrough, not live agent-lifecycle validation. No personal installation was changed.

## Benchmark skills <Badge type="info" text="2026-10-03" />

PR #8 review remediation replaces fixed AB ordering with counterbalanced AB/BA pairs or balanced randomized schedules, equivalent state preparation, and independent warmup. The workflow reference matches. Structural validation (48 skills, zero problems), all 13 Node tests, all four Python tests, the VitePress build, and whitespace checks passed. These checks validate documentation and packaging, not live benchmark fairness.

Added benchmark-checklist and principle-explain-the-number from upstream 23e4138, with explicit-only metadata for both hosts. Z-mode routes measured performance to the checklist and measured eval results to the principle. Perf issue vets each number; hillclimb vets the probe before freezing it and requires error and completed-work counts.

Structural validation passed with 48 skills and zero problems. All 13 Node tests, all four Python tests, the VitePress production build, and `git diff --check` passed. Commands used `MISE_CACHE_DIR=/private/tmp/benchmark-skills-mise` after the default mise shim failed with a sandbox permission error. The generic Codex skill-creator quick validator rejected the shared `disable-model-invocation` field; the repository validator covers that field and its corresponding Codex policy. No policy was removed to satisfy the generic validator.

A parent-run Node scenario alternated five eager and five unconsumed-generator exports of 1,000 rows. Assertions confirmed that each eager run completed 1,000 rows and each lazy run completed zero. Applying checklist question 7 rejects the apparent speedup: the lazy side never did the work. This is a local scenario walkthrough, not an independent agent evaluation or a performance claim. Fresh native host discovery and autonomous use of the new routing were not exercised; installer tests remained isolated from personal configuration.

## Interactive visual guide <Badge type="info" text="2026-10-02" />

Added page-local Vue components for the library/host component map, four illustrative z-mode routes, and host/scope installation destinations. The maps derive their descriptions from the shared router, selected playbooks, native host contract, and installer locations; they do not execute workflows or change installation state.

The VitePress production build passed on Node 24.21.0, alongside structural validation (46 skills, zero problems), all 13 Node tests, and all four Python tests. Runtime commands used a temporary `MISE_CACHE_DIR` because the default shim encountered a sandbox permission error.

Camofox exercised route switching on the development page. Chromium through playwright-cli checked the production preview: expanding/collapsing components, all four routes, all four host/scope combinations, generated preview commands, receipts, and linked reference anchors. The interaction check also passed at 390px with no horizontal page overflow. Desktop dark and mobile light layouts were visually inspected; keyboard Enter activated route buttons and expanded component details. Explicit accessible names were added to the installation selectors after the exact-name check exposed ambiguous implicit labels. Browser console inspection reported no errors or warnings.

To repeat the browser smoke check, build and preview the site, open `/guide/visual-guide`, and evaluate `scripts/docs-visuals.check.js` in the browser console or a browser evaluation tool. Use the production preview because link checks inspect rendered HTML anchors. Restart preview after rebuilding; its cached HTML can otherwise retain the prior build. The script changes only illustration controls and reads same-origin reference pages. No new dependencies were added. These checks cover documentation behavior, not fresh native host discovery, actual agent execution, or deployed-site behavior.

## Forced skill replacement <Badge type="info" text="2026-10-02" />

PR #5 review repairs retain rejection of both `pstack-models.mdc` and `zstack-models.mdc` in active Markdown instructions. Regression fixtures cover skills, Claude agents, and guides. The legacy migration fixture now removes the renamed agent and its receipt entry before migration, checks a read-only `create` preview, and verifies the installed agent contents. Structural validation passed (46 skills, zero problems), all 12 Node tests and four Python tests passed. These are isolated local checks; native host discovery was not rerun.

The installer accepts `--force` to replace conflicting skills, with `--apply` still required for writes. Isolated both-host fixtures verified directory, file, foreign symlink, and dangling symlink replacement; preview preservation; agent collision preflight; reruns; symlink destination preservation; and unchanged uninstall ownership rules.

Structural validation passed with 46 skills and zero problems, all 12 Node tests and three Python tests passed, and `git diff --check` passed. Commands used a temporary `MISE_CACHE_DIR` after the default mise shim failed with a sandbox permission error. No personal configuration was changed and no native host discovery was exercised.

## zstack naming migration <Badge type="info" text="2026-10-02" />

Migrated active skill, agent, package, helper, installer, and documentation names to `zstack`, `z-mode`, `setup-zstack`, and `z-agent`. Upstream attribution and historical evidence retain their original names. The installer recognizes the legacy receipt and retires only owned old links and unchanged agent copies; customized and foreign files remain preserved. Both receipt names present is an explicit preflight error.

Structural validation passed with 46 skills and zero problems. All 11 Node tests and three Python tests passed, including isolated legacy-install migration, read-only preview, and customized-copy preservation. The bundled tools passed frozen installation, 58 Bun tests (226 assertions), and strict typechecking using Bun 1.2.20 and Node 24.21.0. The VitePress production build and whitespace checks passed. Runtime commands used a temporary mise cache or installed binaries because the default mise shim encountered a sandbox permission error.

These are local structural, fixture, and build checks. No personal installation was modified, and fresh native Codex/Claude discovery or behavior under the renamed identifiers was not exercised.

## PR portability and reference checks <Badge type="info" text="2026-10-02" />

PR #3 review corrections replace `import.meta.dirname` with `fileURLToPath(import.meta.url)` and normalize filesystem separators before routing source links or emitting URLs. The dev command uses a Node launcher to set `NODE_ENV=development` before importing the VitePress CLI, preserving forwarded options without shell-specific assignment syntax. The override remains necessary for the previously observed inherited production environment. The writing guide distinguishes technical-writing from unslop. Dark-mode button backgrounds now follow the teal palette with dark foreground text.

On Node 24.21.0, the production build, ten Node tests, three Python tests, structural validation (46 skills, zero problems), and whitespace checks passed. Reference coverage now checks IDs on rendered Markdown headings, with a regression excluding prose and fenced examples. Camofox rendered the home page through `docs:dev` launched with inherited `NODE_ENV=production` and forwarded host/port flags; light and dark appearances were inspected. The browser tab and server were closed. Full Windows and Node 20.0 execution were not performed; native agent behavior and deployed Pages remain outside these checks.

## User documentation review remediation <Badge type="info" text="2026-10-01" />

Expanded first-time installation, scope selection, discovery checks, updates, collision handling, removal, and checkout relocation against `scripts/install.py`. Added user references for all 23 workflow skills, 23 playbooks, and 23 principles, based on their current instructions. Catalog cards now link to those references; source instructions remain supporting links.

`pnpm docs:build` passed. Structural validation reports 46 skills and zero problems; all nine Node tests and three Python tests passed. The new documentation test checks reference anchors against the source inventory. A separate check of the built HTML confirmed all 69 catalog cards resolve to existing reference anchors. `git diff --check` passed. Commands used a task-local `MISE_CACHE_DIR` to avoid the local shim cache permission error.

Camofox checked the setup page on the local dev server, then the catalog and all three reference pages on the production preview. Clicking the how catalog card opened its user reference; the reference pager opened Playbooks and Principles with their content rendered. This caught an unescaped placeholder in the draft, corrected before the successful build. Browser tabs and preview processes were closed afterward. These were local documentation checks, not a deployed-site test, a mobile layout audit, or new native Codex/Claude behavior validation. Installer tests used temporary fixtures; no personal installation was changed.

The relocation instructions were subsequently corrected for customized agent copies. An isolated both-host installer fixture confirmed that uninstall retains their receipts, moving the customized copies to backup and rerunning uninstall clears those receipts, and installation from a moved checkout then succeeds. The backed-up customizations were restored successfully. This exercised the real installer against temporary source and home directories, not native host discovery or personal configuration.

## VitePress documentation site <Badge type="info" text="2026-10-01" />

`docs/` is now a VitePress 1.6.4 site managed with pnpm 12.4.2. Checked locally with Node 24.21.0: `pnpm docs:build` renders every page with no dead links, including the guide overview rewritten from `guide/README.md`. Links to a skill or playbook file render as anchors on the generated skill catalog; other links that leave `docs/`, such as the license or a skill section, render as GitHub URLs on `main`. The catalog reads `skills/*/SKILL.md` and the poteto-mode playbooks at build time, and local search indexes each entry; searching "shipping" returned the playbook card first. The guide now has five pages instead of ten, with code groups for both hosts. Playwright checked the home page, guide, catalog, host, and validation pages in light and dark themes and at a 390-pixel width without page-level horizontal scroll. Structural validation, the eight Node tests, and the three Python tests still pass. With `NODE_ENV=production` set by the user's mise configuration, the dev server served every page as 404 with `ReferenceError: __VP_HASH_MAP__ is not defined`: Vite ran in production mode, so the client used the build-only page lookup. `docs:dev` now sets `NODE_ENV=development`. Playwright confirmed that the home, guide overview, guide pages, and validation page render with no console errors. A deployed site was not checked.

## Python script migration <Badge type="info" text="2026-10-01" />

The installer and structural validator now run through uv with Python 3.14+ and Rich output. The validator uses PyYAML for YAML and stdlib tomllib for TOML. Documentation and test callers use the Python entrypoints; the old JavaScript implementations were removed.

Checked locally with uv 0.12.18, Python 3.14.7, and Node 24.21.0: structural validation reports 46 skills and zero problems; all eight Node installer/helper tests and three Python validator tests pass; git diff --check passes. Installer mutations use temporary homes and projects, including paths with spaces. Coverage includes preview, collisions, ownership, interrupted updates, malformed receipts, and symlink preservation. A regression reproduced the empty explicit scope fallback before the fix; empty `--home` and `--project` now fail before installation or removal, with personal roots redirected to temporary paths during the test. Validator fixtures cover native metadata, YAML boolean policy, local links, and missing helpers.

The local mise shims failed with an "Operation not permitted" error, so checks used the installed runtime binaries directly through PATH. The available Bun binary lacked the old validator's YAML API. No bundled Bun tools changed, and their suite was not rerun. These checks exercise the Python scripts and installed helpers; native Codex/Claude discovery was not rerun for this migration. Earlier host observations follow.

Checked on 2026-10-01 using Codex CLI 0.160.0, Claude Code 2.1.287, Node 24.21.0, and Bun 1.4.2. These are historical host checks from before the Python migration; current script checks are recorded above.

## Repeatable local checks

Run from this checkout:

```sh
uv run scripts/validate.py
node --test scripts/*.test.mjs
uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'
cd skills/z-mode/scripts
bun install --frozen-lockfile
bun run test
bun run typecheck
```

| Check | Observed result | Status |
| --- | --- | --- |
| Shared metadata, identifiers, native definitions, explicit-only mappings, local references, supported entrypoints, active retired host APIs | 46 skills; zero structural problems. | <Badge type="tip" text="pass" /> |
| Installer and helper behavior | Six tests pass after the implementation review below. Preview has no writes; both-host collisions preflight; reruns update unchanged owned copies; user edits and foreign links survive removal; interrupted copy updates reconcile. | <Badge type="tip" text="pass" /> |
| Installed resources in a separate target Git repository | Paths contain spaces. Resource links resolve to this library; audit reports the target root. Clean unknown history stays review-required; untracked work is preserved. TSV logger sanitizes field separators and formula prefixes. | <Badge type="tip" text="pass" /> |
| Task-sized plan contract | Valid small plan accepted; missing phase verification rejected. | <Badge type="tip" text="pass" /> |
| Existing Bun tools | Frozen install succeeds; 52 tests pass, 206 assertions; strict typecheck passes. | <Badge type="tip" text="pass" /> |
| Whitespace | Structural validator covers untracked Markdown; git diff --check passes. | <Badge type="tip" text="pass" /> |

These checks leave no personal installation. Temporary fixtures own all installer mutations. The installer does not change model, permission, or trust settings.

## Native behavior

The documented project installer was applied to a separate temporary Git repository named `target repo` beneath a directory containing spaces. Its real module was `export function add(a,b){return a+b;}`, with a license comment and a redundant narration comment. Prompts required local scoped work and forbade external actions.

| Scenario | Observed result | Status |
| --- | --- | --- |
| Codex discovery | Native app-server skills/list returned all 46 repository skills enabled, real paths in this checkout, and no loader errors. Temporary native config disabled conflicting personal sources and trusted only the fixture. | <Badge type="tip" text="pass" /> |
| Claude discovery and explicit mode invocation | Native initialization listed both named roles and explicit commands. The run read this checkout's installed poteto-mode, host contract, and investigation instructions. | <Badge type="tip" text="pass" /> |
| Both native roles in both hosts | poteto-agent investigated the real module; comment-sicko kept the legal comment and reported the redundant comment without editing. Both reached terminal results. No provider diversity was claimed. | <Badge type="tip" text="pass" /> |
| Missing execution permission | Claude's restricted review inferred the return value from source and reported that denied Node execution prevented runtime proof. It did not claim the command passed. | <Badge type="tip" text="pass" /> |
| Codex handoff/resume | A named persistent parent session resumed and synthesized its two completed native child results. Child rollout metadata identified the requested roles and fixture cwd; terminal receipts confirmed completion. | <Badge type="tip" text="pass" /> |
| Explicit-only selection sample | A natural-language Codex question about calc.mjs read the product source directly without loading the explicit-only how or poteto-mode skills. This is one observed non-selection sample, separate from the explicit-mode runs. | <Badge type="warning" text="sample" /> |
| Direct fix through mode router | Codex read the mode and bug-fix playbook, changed only greeting.mjs from helo to hello, and exercised the real function. The assertion failed before and passed after; no delegation, commit, or publication. | <Badge type="tip" text="pass" /> |

Native smoke tests used bounded CLI print/exec runs with JSON output. For a reproduction, install into a fresh small Git fixture, start a new host session, select z-mode explicitly, and ask for a read-only investigation by z-agent plus a reporting-only comment-sicko review. Wait for terminal results and inspect file contents and actual command exits. Follow with a one-file fix and a saved-session resume. Use native settings to resolve duplicate skill sources rather than changing the user's existing installation.

## Limits and environment findings

- Codex project roles needed native project trust and enabled agents. The installer grants neither. CLI 0.160.0's ephemeral execution failed child rollout creation; persistent sessions worked.
- Running Codex's sandbox inside the outer tool sandbox failed sandbox initialization. The smoke runner used the approved outer execution path while retaining Codex's read-only or workspace-write sandbox.
- Claude used a temporary project installation with existing native authentication. Its personal skill catalog was not completely isolated; project role discovery and reads of the adapted source were verified. This does not prove behavior in an empty personal profile.
- Existing explicit-only intent is encoded and structurally checked for both hosts. Direct invocation and selected-mode composition were exercised, along with one Codex natural-language non-selection sample. These are representative samples, not a guarantee about every model's future skill-selection behavior.
- Claude protects writes to native configuration directories. The generator now preserves a requested canonical source directory and reports registration pending when discovery writes are blocked. Its initial authoring runs reached permission/turn limits; subsequent proof is recorded below.
- No live PR, message, tracker, merge, deployment, unattended scheduler, or cross-provider scenario was run. The PR watcher has its existing deterministic checks. Every workflow has documented native execution or a disclosed capability/handoff fallback; not every playbook has been behaviorally evaluated.

Temporary raw native logs are excluded from the repository because they contain session/account metadata. This record reports observed artifacts and exits rather than claiming static checks prove agent compliance.

## Generated verification skill

Claude authored a canonical verify-calc skill in the temporary project's ordinary source directory. The first proof exposed a relative checkout-path assumption, which was corrected in the shared generator contract and generated helpers. After correcting permission scope for the fixture, doctor, drive, and cleanup all exited 0 from /private/tmp with quoted absolute helper paths and an explicit target path containing spaces. Actual evidence recorded add(2,3) returning 5, the target module hash, and the working directory. Scratch was removed and evidence remained; the product module was unchanged.

The coordinator registered collision-free temporary links into both native skill directories. Codex skills/list discovered verify-calc at its canonical source with no loader error. A fresh Claude /verify-calc invocation loaded the installed link, read the saved handoff, revalidated its now-completed registration against current files, and repeated doctor/drive/cleanup successfully. It wrote only proof evidence and owned scratch. No agents, git mutations, messages, tracker items, or publication occurred.

The temporary Codex authentication link was removed after validation. No credential contents or raw native logs were added to this checkout. The temporary generated skill is a smoke fixture, not an additional library skill.

## Independent implementation review <Badge type="info" text="2026-10-01" />

Reviewed the committed implementation against the approved plan, rather than treating the earlier check results as proof. Coverage included the installer and its ownership transitions, structural and plan validators, worktree audit, both native roles, all 23 playbooks, the core investigation/design/delegation skills and reference prompts, history/digest handling, verification generation, and the watcher/orchestration entrypoints and callers. This was a single-reviewer implementation review, not an additional oracle panel or an exhaustive upstream comparison; the copied upstream commit remains unknown.

### Findings resolved

::: details Claude installation ignored CLAUDE_CONFIG_DIR (fixed)
**Finding:** Personal Claude installation ignored `CLAUDE_CONFIG_DIR`, so an alternate native profile did not receive the skills or agents.

**Correction:** Installer now uses the configured native root for Claude skills, agents, and receipts. A regression reproduced the missing destination before the fix. It now checks installation/removal and that explicit `--home`/`--project` remain isolated. Codex skill discovery remains separate from `CODEX_HOME`. The native directory override is documented in [Claude's environment reference](https://code.claude.com/docs/en/env-vars#variables).
:::

::: details Plan validation accepted blank phase values (fixed)
**Finding:** Plan validation accepted blank phase values because `\\s*` consumed the newline and matched the next bullet as content.

**Correction:** Restrict whitespace after the colon to spaces/tabs. The regression failed before the fix and now rejects empty Depends on, Files, Acceptance, and Verification values.
:::

::: details Reflection advice ignored explicit-only invocation (fixed)
**Finding:** Reflection reviewers and synthesis advised tuning missed triggers without respecting explicit-only invocation.

**Correction:** All four reference prompts now require reading invocation metadata and treat ordinary non-selection of explicit-only skills as expected. This is an instruction review correction; an end-to-end reflection panel was not run.
:::

::: details Commit conditions lacked explicit authorization (fixed)
**Finding:** The standalone proof principle and decision-trail skill conditioned commits on task size without expressly requiring authorization.

**Correction:** Both now require commit authority from the user's request. No commit was made during this review.
:::

::: details Plan status was out of date (fixed)
**Finding:** Plan status denied the existing implementation commit and still described native compatibility as untested.

**Correction:** Updated the status and phase-6 wording while retaining representative-coverage limits.
:::

The audit required no behavior change: added checks demonstrate that ignored files in a detached worktree, locked worktrees, and missing/prunable worktrees remain held. Installer checks also now cover restoration of a missing owned copy and preservation of a foreign dangling link. Concurrency and arbitrary process termination at every write boundary remain outside the tested contract.

### New native observations

Versions were rechecked: Codex CLI 0.160.0, Claude Code 2.1.287, Node 24.21.0, Bun 1.4.2. The fresh fixture was `/private/tmp/pstack review ZfE8TP/target repo`; preview and both-host project installation succeeded. Product `calc.mjs` remained unchanged. Raw logs are retained only in temporary task directories and are not committed.

::: details Claude clean profile (partial: authentication unproven)
**Scenario:** Claude clean profile

**Observed result and limit:** A new empty `CLAUDE_CONFIG_DIR`, project-only settings, and strict MCP configuration exposed all 46 library skills and both named roles alongside native built-ins. Authentication then returned `Not logged in · Please run /login`. No credentials were copied and no personal configuration changed. Clean authenticated execution is still unproven.
:::

::: details Claude non-selection (one sample)
**Scenario:** Claude non-selection

**Observed result and limit:** A bounded ordinary question used Read on `calc.mjs` only; no skill invocation or skill source reads appeared. One sample with Read available, not a universal selection guarantee.
:::

::: details Claude companion composition (pass)
**Scenario:** Claude companion composition

**Observed result and limit:** A direct `/poteto-mode` prompt read the project-linked how companion and minimize-reader-load principle. Both real paths resolve into this checkout. Read and Skill were the only tools available; product files were unchanged. A separate model-side `Skill(poteto-mode)` attempt was rejected for `disable-model-invocation`; that attempt did not execute the mode and is not counted as successful composition.
:::

::: details Codex generated-skill execution (pass)
**Scenario:** Codex generated-skill execution

**Observed result and limit:** Directly invoked the earlier canonical verify-calc. Tool output confirmed doctor, drive, post-drive doctor, and cleanup exits of 0 from `/private/tmp`. Evidence recorded real `add(2,3) === 5`, an unchanged module hash, and retained proof after scratch removal.
:::

::: details Codex authoring from the reviewed source (bounded)
**Scenario:** Codex authoring from the reviewed source

**Observed result and limit:** After excluding the personal-copy sample, an exact project-linked invocation read this checkout's generator and native-host contract. It created `skills/verify-calc-reviewed`, a feature map, and an executable helper. Doctor, drive (four public addition cases), and cleanup each exited 0 from `/private/tmp`. Parsed JSON artifacts independently confirmed the invocation cwd, exits, retained evidence, and preserved product/previous-fixture hashes. Registration was deliberately left pending. This is a bounded source-pinned authoring result, not proof that an ambiguous skill name selects the project copy.
:::

::: details Claude scoped digest (digest path only)
**Scenario:** Claude scoped digest

**Observed result and limit:** Invoked recall with a supplied fixture-only digest and transcript access unavailable. It read this checkout's history contract, checked local Git/source state, labeled its output digest-based, and did not scan other chats. This proves the digest path, not a local transcript parser or the reflect/automate-me workflows.
:::

::: details Claude native resume (pass with persistence)
**Scenario:** Claude native resume

**Observed result and limit:** The first sandboxed sample returned a session ID but resuming it reported no conversation found. A fresh scoped sample run through the approved outer execution path persisted successfully; `claude -p --resume <that-id>` with tools disabled recalled the inspected function, pending work, and unverified digest basis. Native resume works when persistence is available; the sandboxed result is not evidence of a general host defect.
:::

Codex could not initialize its app-server inside the outer sandbox. Approved outer execution retained Codex's own workspace-write sandbox. No authentication link was recreated. One authoring sample selected a conflicting personal generator and was excluded as validation of this checkout; source identity must be checked even when the requested skill name matches.

The six Node tests, structural check (46 skills, zero problems), frozen Bun install, 52 existing Bun tests (206 assertions), strict typecheck, and whitespace checks passed. These do not certify every host behavior or validator field. Publication, messages, trackers, merges, deployment, provider diversity, and unattended execution remain deferred, not failed acceptance tests.

Remaining clean-profile action: the user can authenticate the isolated Claude profile through its native login flow, then rerun the same bounded source/role checks. This review did not move or copy credentials to make that test pass.

## Watcher review remediation <Badge type="info" text="2026-10-01" />

Addressed both findings from the subsequent delegated review. Review-thread reads now follow GraphQL cursors before filtering resolved threads and calculating Bugbot pass counts; missing pagination cursors fail closed. The regression covers 100 resolved threads followed by an unresolved thread on page two, including pass counts across pages.

The shared polling loop caps normal and retry sleeps to the remaining deadline and returns the appropriate timeout without another query after that sleep. Injected-clock regressions cover simple and queued modes, including query time consumed before sleeping. A 10-second timeout with a 3600-second interval and a 2-second query sleeps only 8 seconds. This does not cancel an already-running GitHub command.

Validation: 58 bundled Bun tests (226 assertions), strict typecheck, structural validation, six Node tests, and whitespace checks pass. These are deterministic local checks; no live GitHub calls or external mutations were used for remediation.

## Docker docs image <Badge type="info" text="2026-10-02" />

`docker compose up -d --build` (Docker 29.4.0) built the VitePress site in `node:26-alpine` and served it from `nginx:1.31-alpine`. The build stage installs Git because `lastUpdated` reads commit timestamps; `.git` is part of the build context. The image healthcheck (`wget --spider` on `/`) reported `healthy`. GET `/`, `/guide/`, `/guide/01-setup`, and `/skills` returned 200 through the `cleanUrls` `try_files` rule; an unknown path returned 404.

Hardened `docs/nginx.conf` for a TLS-terminating reverse proxy. Against the rebuilt image, `/guide` redirected to the relative `/guide/`; pages and 404s returned `Cache-Control: no-cache`, hashed assets returned `immutable`, and all responses carried gzip, CSP, `nosniff`, and `Referrer-Policy`. In headless Chromium via playwright-cli, local search returned results, the inline VitePress scripts ran, and the console reported no CSP errors. Not tested behind Pangolin itself.

## Installer terminal output <Badge type="info" text="2026-10-02" />

`scripts/install.py` now renders a Rich panel per host when stdout is a terminal. Entries are grouped by operation, with counts, a short meaning, and wrapped names; skill and agent directories appear once at the top of each panel. Piped output keeps the tab-separated lines that existing tests and scripts parse. A new Node test forces terminal rendering with `TTY_COMPATIBLE=1` and checks grouping, both host panels, and the agents directory. Rendering was inspected at 60 and 100 columns against the real `~/.claude` and `~/.agents` state. Long names fold instead of truncating.

Validation: 13 Node tests, structural validation (46 skills), and 4 Python unit tests pass. This was not checked in an interactive TTY session; `TTY_COMPATIBLE=1` stood in for one.


## Phase 7 real Codex and coordinator restart checks — 2026-10-06

These checks add real-agent evidence to the historical simulated-agent results above. Herdr client/server 0.9.3 (protocol 22) and Codex CLI 0.160.1 ran on a disposable `/private/tmp/zstack-phase7-*` endpoint. Before linking, its socket was inside the temporary HOME, with an empty snapshot and plugin list. The server used `env -i`, a temporary Herdr config/registry, and `resume_agents_on_restore = false`. Two real Codex probes ran sequentially with `codex --no-daemon`, normal installed auth/config, and no model or permission overrides; their UI displayed GPT-6.1-Sol xhigh. Credentials were never copied. The initial inherited filesystem sandbox prevented Codex startup; the authorized isolated server was then launched outside that sandbox while the probes retained CLI defaults.

- Both probes ran `herdr pane current --current` in their own sessions and returned exit 0 with the correct isolated pane and native session.
- The enrolled worker produced actual `working` and `idle` hooks. Observations and board text recorded those states; acceptance stayed `not recorded`. Worker/coordinator tokens, board key focus, and focus actions were checked against live snapshots and completed action logs.
- A real isolated-server stop ended every recorded original server/probe process. Restart ran the startup hook and classified the coordinator binding as `occupant changed`; the stale focus action failed. A fresh native session remained stale until explicit `coordinator bind`, after which inspection, labels, board, focus, and real hooks recovered. No automatic resume or rebind was used.
- Reads/hooks preserved fixture run and registry bytes and timestamps between explicit coordinator writes. Coordinator-owned repository artifacts and personal `plugins.json` remained unchanged. Cleanup closed the task panes, unlinked the isolated plugin, stopped only that server, and verified no recorded task process remained. Receipts and temporary fixture files were retained.

No demonstrated plugin defect required a code/test change. Real blocked-state hooks remain unverified: no approval/question dialog arose, and none was induced or approved. Claude integration, native resume, remote/install/detach checks remain outside this assignment. Full commands, exit statuses, identities, snapshots, hook observations, process accounting, and limitations are retained in `.agent-work/herdr-plugin/reports/phase7.md` and `phase7-live/`.

## Phase 8 real Claude and blocked-state checks — 2026-10-06

These checks add real Claude Code evidence to the Phase 7 Codex results. Herdr client/server 0.9.3 (protocol 22) and Claude Code 2.1.292 ran on a disposable `/private/tmp/zstack-phase8-*` endpoint. Before linking, its socket was inside the temporary HOME, with an empty snapshot and plugin list. The server used `env -i`, a temporary Herdr config/registry, and `resume_agents_on_restore = false`. The probe started with `herdr agent start ... --kind claude -- --permission-mode default` in an empty directory. A launcher gave only the `claude` process the real HOME/USER/LOGNAME, so it used installed auth, config, and the installed Herdr hook. Credentials were never copied or read. The CLI showed Opus 5.5 with high effort, Claude Pro, and manual (default) permission mode; these were CLI defaults.

- The first launch passed only HOME and was not logged in, so no API turn ran. `claude auth status` showed `loggedIn: false` without `USER` and `true` with it, because macOS Keychain lookup needs `USER`. This was a test-harness fault, and the launcher was corrected.
- Claude's SessionStart hook exposed `agent_session` at startup. `task bind` after the first real turn captured terminal and session. The board showed `binding ok`, observed lifecycle, and acceptance `not recorded`.
- An inert no-tool turn produced real `working` and then `idle` `pane.agent_status_changed` hooks, observations, and board text.
- **Blocked:** asked to run `touch ./phase8-blocked-marker`, the probe showed Claude's Bash permission dialog. `agent get` returned `blocked`, hook `plugin-log-12` succeeded (`phase8-worker: ok`), the observation recorded `agent_status: blocked`, and the board showed `observed blocked` with acceptance `not recorded`. The dialog was cancelled with `pane send-keys Escape`, and nothing was approved. Claude reported `Interrupted`. Herdr returned to `idle`, with a matching hook (`plugin-log-13`), observation, and board update. The marker file was never created.
- Live tokens were exact (`zstack_run=phase8-worker`, `zstack_role=worker`, `zstack_task=probe`, `zstack_phase=not recorded`; coordinator `zstack_role=coordinator`). Board key `1` and the `focus-worker` action, invoked from the focused coordinator shell, focused the Claude pane; the action exited 0. Board key `c` refused to focus the shell coordinator, which is the documented Herdr 0.9.3 limit on focusing panes that host no agent.
- Board, hooks, and focus left the fixture run and registry bytes and mtimes unchanged after the explicit bind. Cleanup closed the panes, unlinked the isolated plugin, and stopped only that server. All 9 recorded task PIDs were absent, and the personal server, its plugin list, and `plugins.json` were unchanged.

No plugin defect was found, and no code or test changed. Remaining gaps: the coordinator was a plain shell, so board `c` focus to a Claude coordinator, Claude restart/rebind, and native resume were not exercised. The probe wrote its normal transcripts under the real `~/.claude/projects/`. Receipts are in `.agent-work/herdr-plugin/reports/phase8.md` and `phase8-live/`.

## Phase 9 real Claude coordinator restart and rebind checks — 2026-10-07

These checks bind a real Claude Code 2.1.292 process as a run's coordinator on a disposable Herdr 0.9.3 (protocol 22) endpoint under `/private/tmp/zstack-phase9-*`. The isolated server ran under `env -i` with `resume_agents_on_restore = false`. Its snapshot and plugin list were proven empty before linking. The worker task was a plain shell.

- **Before restart:** coordinator `binding ok` with terminal and native session, plus `zstack_role=coordinator` tokens. Board key `c` and the `focus-coordinator` action, invoked from the worker shell, both moved focus to the Claude pane; the action exited 0. An inert turn produced `working` and `idle` hooks and observations.
- **Restart:** every recorded original process was absent before the server restarted on the same socket. These included server, Claude, MCP, shell, and board processes. The startup hook classified the coordinator `occupant changed` and applied no labels. `focus-coordinator` exited 1, and focus did not change. After an explicit `task bind` of the restored worker shell, a reopened board showed the coordinator stale and refused `c`.
- **Rebind:** one fresh Claude process was started in the restored coordinator pane. Inspection stayed `occupant changed` until an explicit `coordinator bind`. After that: `binding ok`, labels restored, board `c` and the action focused the pane, and an inert turn drove hooks. Run and registry bytes and mtimes were unchanged between explicit writes, and acceptance stayed `not recorded`.
- **Failed criterion:** the rebind did not capture the fresh native session. Herdr kept reporting the pre-restart session restored from its `session.json`, even after two turns, although the fresh process ran a new session. Claude's exit hint and transcript confirm the new one. `coordinator bind` therefore recorded the fresh terminal with the old session ID. The plugin records what Herdr reports, and the fresh terminal still rejected the stale occupant. No code or test changed.

Cleanup unlinked and stopped only the isolated server, and all 17 created PIDs were absent. The personal server, its plugin list, and `plugins.json` were unchanged. Static checks passed (51 skills, 15 Node tests, 165 Python tests, `git diff --check`). Remaining gaps:

- Fresh-session capture after restart with restored pane metadata.
- Whether a new pane captures the fresh session.
- Native resume.
- Question, trust, and Codex blocked sources.

The probes wrote transcripts and session-env entries under the real `~/.claude/`. Receipts are in `.agent-work/herdr-plugin/reports/phase9.md` and `phase9-live/`.

## Herdr plugin pre-landing review and repairs — 2026-10-07

A read-only final review of `integrations/herdr/` reported six findings, each reproduced with throwaway fixtures. All six were repaired, and each repair has a regression test that failed with the fix removed:

- An unresolvable `~user/...` report reference now shows as a missing-report gap instead of crashing inspect, the board, and hooks.
- Run-record writers serialize read-modify-write under a sibling lock file; inspection, the board, and hooks never take it.
- Every writer validates the record it is about to store, so a bad argument can no longer leave a record the helper later refuses.
- The coordinator-only guard resolves the caller pane to its terminal, so a moved worker still cannot record acceptance.
- Relabelling a pane clears `zstack_*` keys its new role does not use.
- Writes through a symlinked run file reach the target, and the board accepts only ASCII `1`–`9` keys.

Phase 9's failed criterion led to one more change: when a rebind captures a new terminal that reports the previous binding's agent session, the helper records no session and prints a warning, so the binding is checked by terminal and agent kind only. A regression test reproduces the Phase 9 snapshot. These changes landed after Phases 7–9 ran; the live checks above used the pre-repair code (hashes in `phase9-live/tested-source-hashes.json`), and the repaired paths are covered by unit tests only.

PR #28 review (cubic and Codex bots) raised 15 distinct issues; 14 were fixed and one was declined. Agentless bindings stay valid: shell workers are a supported binding, and focus already refuses them with Herdr's error. Each code fix has a regression test that failed with the fix reverted:

- Enrollment holds the registry entry's lock across its conflict check and write.
- A snapshot whose `result` is not an object is a read error, so the board shows `STALE` instead of crashing.
- Orchestration evidence shows only ledger rows for the unit's current PR and SHA.
- The worker guard compares pane IDs for bindings that recorded no terminal.
- Repeated evidence is recorded once.
- Board entries after the ninth get keys `a`–`z`, skipping `c`, `q`, and `r`.
- Terminal control characters are stripped from rendered text.
- A malformed observation's fields are rebuilt instead of crashing hooks.
- A pane already labeled by another enrolled run is not relabelled.
- `open-board` exits 1 when it opens nothing.

The guide now covers `enroll` and removing registry entries when a run ends, and the plan's handoff explains the follow-up phases. Checks: 185 Python tests, 15 Node tests, `validate.py`, Ruff, and `git diff --check`. No live Herdr check was rerun for these changes.

A second Codex review of `676e116` raised two more issues, both fixed with regression tests that failed with the fix reverted:

- Inside Herdr, `task accept`, `task reject`, and `task evidence` require the caller's pane to match the coordinator binding, by terminal when both are known and otherwise by pane ID. Before, any pane not bound to a worker could run them. A pane bound to a worker task is refused even when it also matches the coordinator binding, as a follow-up Codex review of the uncommitted fix pointed out. A run with no coordinator binding still refuses only worker panes.
- A pane holding more than one of a run's bindings gets none of that run's tokens instead of the last binding's role.

Checks: 187 Python tests, 15 Node tests, `validate.py`, Ruff, and `git diff --check`. No live Herdr check was rerun for these changes.
