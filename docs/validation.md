---
outline: [2, 3]
---

# Validation

## Codex other-provider route — 2026-10-27 {#other-provider-route}

Added the native-hosts other-provider route, wired it into arena's judge and one interrogate adversary, and documented `/codex:adversarial-review` as a user-run check for Claude Code. Shared native manifests are `0.21.0`. Checks ran on macOS in Claude Code with Codex CLI `0.165.0`.

- `uv run scripts/validate.py`: 57 skills, zero structural problems. `node --test scripts/*.test.mjs`: 212 passed, zero failed, 61 skipped. Python unittest discovery: 153 tests passed. `git diff --check` passed.
- Live probe of the documented command from a Claude Code Bash call: `codex exec --sandbox read-only --ephemeral -C <scratch repo> -o <file> -` with the brief on stdin. It read the fixture, answered correctly, and wrote the last message to the `-o` file. The run header printed `provider: openai`, `model: gpt-6.1-sol`, and `sandbox: read-only` on stderr. The Claude Code sandbox did not block it in this session.
- Live interrogate of this change with two Claude Opus 5.5 adversaries and one Codex `gpt-6.1-sol` adversary under `workspace-write`. Four findings survived lead reruns; the Codex seat reported none. Fixes, each rerun after the change:
  - Outside a Git repository, `codex exec` exited 1 with `Not inside a trusted directory and --skip-git-repo-check was not specified.` With `--skip-git-repo-check` the documented command exited 0 in a non-repository scratch folder and wrote `PONG`.
  - Inside Codex's sandbox, mise shims and the uv cache failed with `Operation not permitted` while the host runs passed, and a piped `node --test` still exited 0. The Codex adversary hit this and worked around it. `codex sandbox -P :workspace -C <dir> -- uv --version` reproduces the block without a model call (exit 1), while `-- git --version` exits 0, so the route now preflights one representative check and treats blocked commands as gaps.
  - On a Codex host the Codex seat is the coordinator's own model (`model = "gpt-6.1-sol"` in config). The route, interrogate, and reference now skip it for a Codex coordinator.
  - The route permitted a direct `codex exec` under Herdr, contradicting herdr-workflow; it now applies to native execution only.
- A side effect occurred outside the worktrees: one adversary's `mise which uv` auto-pruned old tool versions (`usage` 7.1.2, `fnox` 1.42.1, `mr-boxington` 1.27.0, `npm:@openai/codex` 0.164.0).

- Live arena with a Codex judge: two Claude Opus 5.5 candidates rewrote the route section, and the judge ran the documented read-only command in a non-repository scratch folder. It exited 0 with `provider: openai`, `model: gpt-6.1-sol`, `sandbox: read-only` on stderr, scored the candidates 25/25 and 23/25, checked both commands byte-for-byte, and flagged that differing `model:` values alone do not establish another family. The synthesis keeps candidate 1, grafts candidate 2's ordering of the blocked-command rule and two sentences, fixes the family wording, and stays at 285 words.

- Live arena under a Codex coordinator: Codex CLI `0.165.0` (`GPT-6.1-Sol high`) with the native plugin refreshed to `0.21.0`, launched in a Herdr pane without Herdr execution selected. After a plugin refresh, Codex opened its hook-trust review and swallowed the first prompt; the user reviewed the hooks and the prompt was resent. Two native candidates completed, without exact model IDs exposed. The coordinator skipped the Codex route, citing "Skip the route when you are a Codex model", found only GPT-family overrides, and did not launch the installed Claude CLI because Herdr was not selected. It skipped judging and picked the base alone, as arena step 4 requires. Its first `node` call failed through the mise shim with `Operation not permitted`, and it reported that as blocked rather than passing. The checkout stayed clean.

- Claude CLI route, added after that run. Live probes with Claude Code `2.1.312` in a non-repository scratch folder: the documented read-only command returned `PONG` with `modelUsage` key `claude-opus-5-5` and no permission denials. Without `--strict-mcp-config`, the seat offered the user's MCP write tools (Google Drive, GitHub); with it, the seat listed only `Glob, Grep, Read`. The writing variant wrote `repro.txt` in its folder through sandboxed Bash. In an earlier probe the same sandbox also let Bash write a sibling folder under `$TMPDIR`, as Codex's `workspace-write` does, and refused compound commands, reporting them in `permission_denials`.
- Live arena under a Codex coordinator after the Claude route, with the plugin refreshed and hooks re-reviewed by the user: two native candidates completed without exposed model IDs. A read-only judge ran through the documented `claude -p` command from Codex's sandbox. It exited 0 with `modelUsage["claude-opus-5-5"].provider` `firstParty`, no permission denials, and scored the candidates 24/25 and 23/25. Three Claude SessionEnd hooks failed through blocked mise shims; the judge's result was unaffected, so no unsandboxed rerun was requested. The checkout stayed unchanged.

A blocked-host-sandbox rerun and a writing Claude adversary under a Codex coordinator were not exercised.

## pstack 0.15.35 workflow port — 2026-10-27 {#pstack-0-15-35}

Ported interrogate, arena, autopilot, explain-the-number, and z-mode changes from pstack PR #986. Shared native manifests are `0.20.0`. Checks ran on macOS in Claude Code with native agents.

- `uv run scripts/validate.py`: 57 skills, zero structural problems. `node --test scripts/*.test.mjs`: 212 passed, zero failed, 61 skipped (TLC-backed, differential, and render suites). Python unittest discovery: 153 tests passed.
- Live interrogate scenario on a scratch fixture repository: a committed branch diff with two planted bugs, plus an uncommitted `last_page` addition that depends on one of them. Two native adversaries (Claude Opus and Claude Sonnet, so same provider) each worked in a detached worktree and returned exact commands with printed and required output. A rerun in a fresh lead worktree, carrying only the named repro files, reproduced every reported output. Three findings survived, each found by both adversaries, with the `last_page` failures merged into the floored `page_count` root cause. One reproducible `ZeroDivisionError` from `page_count(5, 0)` was dropped because the stated intent does not define that input. After the worktrees were removed, the fixture checkout still held only its original uncommitted change.
- The scenario found one gap, which is now fixed in the skill. On this host `git diff` uses an external diff tool, so the first copy of the uncommitted changes produced no applicable patch. The skill now requires `git diff --no-ext-diff --binary` and names untracked files.

Arena's cross-family judge rule, the model-rejection fallback, the autopilot playbooks, goal restatement, and Codex and Hermes invocation were reviewed statically and not exercised live. No Herdr or other-provider judge was available to run.

## Statechart compiler — 2026-10-27 {#statechart-compiler}

Ported the pstack statechart compiler from the `519d36aa` tree (#977, #982, #981). Shared native manifests are `0.19.0`. Checks ran on macOS with Node `24.22.1`, Java `25.0.2`, and tla2tools `1.7.4` (sha256 `936a2620…0e88`, matching upstream's pin), downloaded to a session scratch folder. Personal mise and npm configuration was untouched.

- Unmodified upstream suite, with TLC, fast-check `4.5.3`, Pele `1.9.0`, and Mermaid `11.16.0` (render cache in scratch): 366 of 367 passed. The failure was the relative-symlink launcher test, which builds its link with lexical `path.relative` under macOS's `/var` → `/private/var` TMPDIR. With a resolved TMPDIR, both launcher tests passed. The test now resolves its link folder.
- Adapted suite, same setup, on the final scripts and references: 368 of 368 passed (upstream's 367, including the fixed launcher test, plus one new view-key test).
- `node --test scripts/*.test.mjs` without TLC: 210 passed, 0 failed, 61 skipped. Skips cover TLC-backed statechart tests, the differential suite (needs fast-check), and the render suite (needs `STATECHART_RENDER_TESTS=1`).
- `uv run scripts/validate.py`: 57 skills, zero structural problems. Python discovery: 153 tests passed. `git diff --check` passed.
- Live launcher with real TLC: a model with `[k \in {A, "A"} |-> 0]` and a view exited 2 with the key-collision message. Without a view it exited 0 and drew two states. A model with integer `9007199254740992` exited 2 because TLC refused the number ("TLC can't handle a number this big"), so the old safe-integer guard was dropped as unreachable.
- In an ad hoc probe model, SANY's XML exporter crashed on `@` inside `EXCEPT` and the command exited 2 with SANY's stack trace. This was not investigated further; the probe was rewritten without `@`.

Bun and Deno launch paths, the mise auto-install path, fresh Codex/Claude/Hermes invocation, and remote CI were not exercised.

PR #69 review follow-up (cubic, 13 threads):
- Fixed. An unlabeled step in the TLC dump now stops with an error instead of being dropped. A stop message containing backticks gets a longer fence in `report.md`. SKILL.md documents the launcher's 127 exit. The setup docs now require Node 22.18+ for the TypeScript tests. The workflow reference separates unchecked-rule reporting on reruns from the no-output exit on a first-run TLC error. Both new regressions failed against the unfixed code and pass now.
- Added `typescript` 5.9.3 and `@types/node` 22.18.0 as devDependencies with a `typecheck` script. `tsc -p .` initially reported four upstream errors (an `exit` widened to `number`, and two tests returning non-void). After fixes it reports zero.
- Declined, with evidence. Tightening the config fuzz to require a TLC error failed on a U+2029 config: TLC silently drops the following `CONSTANT` line, and the skill refuses the config by design. With real TLC 1.7.4, `CONSTANT P <- [R] Q` leaves `PROPERTY P` unreplaced while `P <- Q` replaces it, and the skill matches both. Lazily read TLC output depends on its open file descriptors after the temporary folder is removed. The `CounterOrder` dump is TLC's real output for a state past `CONSTRAINT`. An empty dump is valid for a spec with no initial states. The 10,000-state drawing took 0.32 s against its 5 s budget. The synchronous poll targets a short file-writing window.
- Full suite with TLC, fast-check, Pele, and Mermaid: 370 of 370 passed.

## Bundled Codex agents and manual installation — 2026-10-26

The Codex package now includes tracked `agents/` files. Shared native manifests are `0.18.4`. The README, setup guide, and Codex host guide document copying `agents/codex/z-agent.toml` into `${CODEX_HOME:-$HOME/.codex}/agents/` while keeping plugin skills installed. The copy prompts before overwriting an existing role, and the host guide covers updates, removal, and `comment-sicko`.

Checks on this macOS host:

- `uv run scripts/package_plugin.py` rebuilt the package with both Codex TOML roles. The new packaging regression checks working-tree agent contents and excludes an untracked personal role; it fails with the old resource list and passes with `agents` included.
- The documented shell commands copied the exact source bytes from both the checkout and staged package into disposable `CODEX_HOME` paths containing spaces. Declining an overwrite preserved a customized file. Personal Codex configuration was untouched.
- `uv run scripts/validate.py`: 57 skills, zero structural problems. `node --test scripts/*.test.mjs`: 55 passed, zero failures, 51 skipped because TLC was unavailable. Python unittest discovery: all 153 tests passed. Ruff check and format check on both changed Python files, and `git diff --check`, passed. Checks used Homebrew uv and Node to avoid the sandbox-blocked mise shims.
- Mypy passed on both changed Python files. The additional project-wide run reported an existing `run_queued` argument-type error at `scripts/test_pr_watcher.py:746`; the same command against an isolated archive of base commit `3a8dbb5` reported the identical error.
- PR review clarified that manual-copy sources are relative to the plugin root, resolved two directories above the real z-mode `SKILL.md`. Direct path assertions found both Codex roles using that rule in the checkout and rebuilt package; structural validation and diff checks passed again.

The installed CLI reports `codex-cli 0.164.0`; static inspection of its plugin manifest parser found skills, MCP servers, and hooks, but no `agents` field. The manifest therefore retains its existing supported declarations. Packaging and manual-copy checks do not prove discovery or a live `z-agent` spawn in a fresh Codex session; those checks and a personal plugin refresh were not performed.

## Watcher thread policy and comment reviews — 2026-10-22 {#watcher-thread-policy}

Issue #64 (shared native manifests `0.18.3`): `watch-pr` ended watch mode on any unresolved review thread, even after the author replied and GitHub reported the PR `CLEAN`. It also ignored the Codex connector, which reports review progress in an edited PR comment rather than a check. `reviewAutomationRunning` only affected the status table and never held back READY.

- `--threads warn` keeps watching past the threads open at its first poll. Those threads block only once CI is clean and the forge still reports `BLOCKED`, which is how a required conversation resolution appears. A thread that appears later blocks at once, so findings from the review the watcher waited for are not folded into READY. READY lists the accepted threads in `proof.threads`, and `--pretty` names the count. `--threads block` is the default and keeps the previous contract.
- The GitHub reader pages PR comments and reads the `codex-review-state:v1` marker from `chatgpt-codex-connector`.
  - A review of the head SHA is pending while its status is null, `queued`, `pending`, `running`, or `in_progress`. Any other status except `completed` becomes a failed check (exit 4), so an unknown terminal state does not wait forever under the default `--timeout 0`.
  - A review with no commit SHA yet and an in-progress status is also pending.
  - A marker without `-->`, a payload that is not a JSON object, or a review field of the wrong shape raises a non-retryable `codex-review-state` query error.
  - GitLab reports no comment reviews.
- An interrogate pass with two Claude Opus 5.5 reviewers and one Codex reviewer found three gaps in the first version: unbounded waits on unknown statuses, silent acceptance of malformed or null-status markers, and threads opened during a warn watch reaching READY. Eight new tests (one table test with 11 cases) fail against that version and pass now.
- Three new watcher tests and the expanded golden stream failed before the change and pass now. The golden diff is 22 added lines; existing scenario bytes are unchanged. The uv process test's fake `gh` now answers the comments query; it returns TIMEOUT while a Codex review of the head is running and READY once it completes. That case was added with the fix and was not run against the old code.
- Live: the new comments query parsed fullerzz/herdr-plugin-sesh PR #157 and found the connector's marker. The completed review of `ce9ac81` produced no pending check, and the same comment with its status changed to `running` produced one. The original PR is merged, so the thread repro was not re-run live. On open PR #156, both thread modes ran end to end and stopped at its real failing lint check (exit 4).
- `uv run scripts/validate.py`: 57 skills, zero structural problems. `node --test scripts/*.test.mjs`: 55 passed, zero failures, 51 skipped because TLC is not installed. Python discovery: all 152 tests passed. Ruff check and format, and ty, pass on the watcher. The installed uv binary directory was put on `PATH` because the sandbox blocks the mise shim.

Status values other than `running` and `completed` are not documented, so the in-progress set beyond `running` is assumed; an unlisted in-progress status would stop the watch as a failed check. Right after a push, the marker still names the previous commit until the connector picks up the new head, so READY can still precede a Codex review that has not started. Warn mode cannot tell a required conversation resolution from other `BLOCKED` causes while threads are open, so it reports the threads. Threads opened between the remediation and the first warn poll are accepted with the rest.

## Sandboxed mode controls — 2026-10-22 {#sandboxed-mode-controls}

Issue #65: under Claude Code's Bash sandbox, z-mode controls could not write `~/.claude/plugins/data`. The sandbox documentation lists `~/.claude` as a protected path that `allowWrite` cannot reopen, and hooks run outside the sandbox. Shared native manifests are `0.18.2`.

- Reproduced on macOS in a live sandboxed Claude Code session: the hook's original `uv run` Enable control failed. With the mise `uv` shim, the sandbox blocked the shim before Python started. With Homebrew uv, the helper returned 1 with `[Errno 1] Operation not permitted` on its temporary state file.
- An unsandboxed retry of the Enable control was refused by the auto mode classifier (`Safety Bypass Flag`). The `!` prefix fallback was not exercised live.
- Controls now run the base interpreter fixed when the hook starts. In the same sandbox, the emitted Enable control started Python without uv or mise. It returned 1 with `[Errno 1] Operation not permitted` and pointed to the session's guidance for blocked controls.
- Two independent Claude Opus 5.5 reviewers interrogated the first fix; a Codex reviewer could not start because its companion hit the same sandbox denial under `~/.claude/plugins/data`. A reviewer probe showed that `uv run --no-project python` selects a `.venv` in the working directory, so an unsandboxed rerun could execute a planted interpreter. Other findings covered retry budget, the sandboxed `!` cases, a blocked Disable, overstated docs, and remedy text in tool output.
- Six hook tests failed against the original helper and pass now. They cover the planted `.venv`, EPERM/EACCES/EROFS versus EISDIR/ENOSPC errors, a read-only state directory, the per-host context guidance, and the interpreter in both shell templates.
- PR #66 Codex review noted that `realpath` leaves a copied (non-symlink) `.venv` interpreter in place. A local probe confirmed it. Controls now use `sys._base_executable`, and the planted-venv regression covers symlinked and copied venvs. The copied case failed against the first PR head and passes now.
- `uv run scripts/validate.py`: 57 skills, zero structural problems. `node --test scripts/*.test.mjs`: 55 passed, zero failures, 51 skipped because TLC is not installed (the same count as the baseline). Python discovery: all 141 tests passed. Homebrew uv bypassed the sandbox-blocked mise shim.

Codex and Hermes sandbox behavior was not exercised. The SessionStart launchers still use `uv run --no-project` from the session's working directory, so a planted `.venv` there could still choose the hook's interpreter at the next session start or compaction. Through `pyvenv.cfg`, it would also choose the base interpreter that controls emit, as cubic noted on PR #66. Codex also noted that an in-place checkout writable by the session lets a sandboxed command change the helper before an approved rerun. The same checkout already supplies the hook that Claude Code runs unsandboxed, so the docs record that boundary instead of pinning only the control. That exposure predates this change and remains open.

## Statechart upstream fixes — 2026-10-22 {#statechart-upstream-fixes}

Ported pstack #776 and #779 while retaining zstack's parser, output-safety, explicit-invocation, and Pele adaptations. All native manifests are `0.18.1`. Checks used Node `26.12.0`, Java `25.0.2`, and the existing isolated TLC `1.7.4` jar on macOS.

- Structural validation: 57 skills, zero problems.
- `node --test scripts/*.test.mjs` with TLC configured: 97 passed, zero failures, three Linux-only tests skipped (100 total). This includes temporal properties, separate configs, missing-field rejection, unchecked-rule reporting, retained diagnostics, shortest paths, concurrent atomic publication, and the output-folder model with deliberate mutations. The subsequently added portable copy-fallback test passed separately. `git diff --check` passed.
- Python discovery: all 137 tests passed. The first sandboxed run failed when child commands resolved the blocked mise shim; rerunning with the installed uv binary directory on `PATH` passed without modifying personal configuration.
- Without TLC, 38 tests passed and 46 were explicitly skipped before the portable copy-fallback test was added. Parser fixtures cover TLC 1.8's named temporal violation while continuing to reject unrelated errors. Preflight tests reject unsafe property filenames and fixed configs that omit or change original rule categories.
- Three focused live-TLC tests passed for changed inputs, foreign output files, and refusing rendering after input changes. New upstream assertions were adapted for macOS's `/var` versus `/private/var` temporary paths; retained chart evidence is still read and checked.
- A portable live-TLC test injected `ENOSYS`, `EXDEV`, and `EISDIR` from directory rename: initial copy publication and repeated replacements passed, and foreign output notes survived refusal. This is fault injection on a local filesystem, not a real FUSE mount. Concurrent copying is not atomic and may mix files; the output-folder model explicitly excludes that fallback.
- Packaging succeeded. From a separate temporary working directory, the packaged `from-chart sync.mmd --pele` found the expected `NeverSyncedWhileOffline` counterexample, returned 1, compared the chart back unchanged, and wrote both overview and bug SVGs alongside model evidence. Renderer dependency resolution remained local to the caller; images were not visually re-reviewed.

TLC 1.8 itself, a real FUSE mount, fresh Codex/Claude/Hermes invocation, and remote CI were not exercised. Linux namespace and preload-only tests remain platform-limited. These checks preceded PR publication.

Independent pre-merge review reproduced two publication failures against `b917e14`: staging setup errors discarded completed diagnostics, and failed fallback copies deleted concurrently created destination files. Both new regressions failed before repair. Parent/staging setup now uses `NotPublished` handling, and failed fallback copies retain the destination with an incomplete-output diagnostic. A fresh verifier confirmed both repairs and found that cleanup failures could still hide the original error; staging and post-publication backup cleanup now retain diagnostics too. Four focused live-TLC publication tests passed, and another verifier found no remaining cleanup issues.

GitHub review follow-up added regressions for fields missing in later/alternate initial states, record-to-primitive comparison shapes, and changes to adjacent config metadata. Both regression groups failed against `a861cdb` and passed after repair. Guards now collect field paths across all model states and refuse mapping reads of incompatible record parents; metadata snapshots include adjacent config contents and relevant config/module directory entries. New retained-path assertions accept either path separator; Windows execution remains untested. The full follow-up suite passed 103 Node tests with three Linux-only skips. A final independent review caught guards running during internal state hashing: an ignored record/primitive difference was rejected. Its positive regression failed before repair and passed after keeping raw state identity separate from guarded mapping access.

## Statechart and Pele — 2026-10-22 {#statechart}

Added the explicit-only statechart skill from the final merged pstack #741 tree, with local Pele SVG rendering and real-code reproduction requirements. Shared native manifests are `0.18.0`. Validation used Node `26.12.0`, Java `25.0.2`, TLC `1.7.4`, Pele `1.8.0`, and Mermaid CLI `12.0.0` on macOS. Renderer packages and the TLC jar were installed only in an owned temporary workspace; personal host configuration was untouched.

- `uv run scripts/validate.py`: 57 skills, zero structural problems.
- `node --test scripts/*.test.mjs` with `TLA2TOOLS` and `JAVA` configured: 87 passed, zero failures, two Linux-only tests skipped on the merged tree with Node `26.12.1`. The collision regression first failed against the imported implementation, then passed after the fix; the final full suite includes it. Linux PID namespaces and `LD_PRELOAD` rename fault injection are unavailable on this macOS host; path comparisons now account for macOS's canonical temporary-directory alias.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 137 passed, including isolated installer/packaging and host registration fixtures.
- `uv run scripts/package_plugin.py`: the new skill's 16 resources byte-matched the package. The packaged entrypoint ran from a different working directory and loaded Pele from that caller's local dependency, not the plugin cache.
- The sync fixture ran through chart-to-TLA+ generation, TLC checking, and chart comparison. It found the expected `NeverSyncedWhileOffline` model counterexample and drew the agreed chart back unchanged. One run with both `--png --pele` produced the overview and numbered trace in both formats; all four images were visually inspected. A second `from-spec` exercise verified the nested-box fallback and Pele output. Existing TLC regressions exercise `--fixed`, `--against`, guarded parallel regions, model mutations, stale inputs, interruption, and overlapping output publication.
- Missing or failed Pele rendering returns 2, retains Mermaid/model evidence and successful images, and removes stale SVGs on a later run without `--pele`. A blocked sandbox browser launch likewise returned 2 while preserving the successful SVGs; a permitted isolated headless Chrome run then rendered both PNGs successfully.
- Skeleton generation now refuses existing configs/mappings and dangling symlinks when the spec is absent; exclusive file creation also refuses a path occupied after preflight. The regression failed against the imported implementation and passed with the fix.

PR #61 review follow-up added twelve targeted regressions. The original eight reproduced failures against the published head before correction. Fixes refuse unsafe integer conversion and colliding function keys, preserve unrelated files within `tlc/` and directories occupying generated filenames, protect scaffold symlinks, report missing mappings as incomplete runs, reserve TLA+ keywords and generated state-set names, retain changed comparison labels (including covered and unlabeled edges), explain region fallback, and count orphaned TLC as running. The output-folder model now names and scopes its exit properties to publication; renderer failures are covered by the real helper tests instead. Direct parser fixtures establish the unsafe-value behavior; the installed TLC rejects the attempted mixed integer/string function domain before the parser sees it.

A later real-TLC regression reproduced a false fixed verdict when `FIXED.cfg` omitted an original invariant. `--fixed` now refuses missing original rules before checking or publishing a diagram; complete configs and fallback to the original config remain supported.

A further parser regression reproduced value-kind collisions in state keys. Internal identities now distinguish model values, strings, sets, sequences, and typed function domains; projection copies retain those distinctions. Set ordering is canonical, semantically equal record/function and sequence/function representations agree, string escapes decode without losing characters, and unrecognized syntax is refused. A converter fixture verifies separate enabled-action facts after removing code-only fields for spec comparison.

An independent native verifier ran the original statechart suite (58 passed, two skipped), exercised real Pele output, and reproduced the mapping-symlink write. A fresh verifier reviewed the remediation, caught a reverse-order generated-name collision and two comparison-path gaps, and independently confirmed their corrections. A final scoped verifier independently checked missing, empty, complete, and fallback fixed configs. Another scoped verifier checked the value-kind fix using real TLC: twelve distinct typed initial states retained twelve distinct keys, and all twelve initial counterexamples matched their graph keys. These were local native reviews, not cross-provider consensus.

A thirteenth targeted regression reproduced an invariant token overwriting a file outside the TLC work directory. Config parsing now rejects characters outside ASCII letters, digits, and underscores before writing evidence. Real TLC accepts local wrappers for qualified expressions and digit-leading operator names; both survive reruns. An independent verifier confirmed rejection of traversal and malformed names in both primary and comparison configs while preserving an outside file.

The merge from `main` at `3297b77` conflicted only where both branches added validation entries. Both entries are retained, along with the Pages workflow, base-aware links, and its documentation regression test.

The live diagram scenario is an invented model, not a reproduced application bug. Fresh Codex, Claude Code, and Hermes discovery/invocation and Linux-only cases were not run. These are local helper, packaging, rendering, and regression results; they do not establish arbitrary-model correctness or remote CI status.

## Additional GitHub Pages deployment — 2026-10-22

Added a Pages workflow that builds pull requests and deploys `main`, alongside the existing Docker/nginx setup. `DOCS_BASE` selects the repository subpath; the default remains `/`. The favicon, footer notice link, and sidebar notice link respect that base. This follows the [VitePress deployment guide](https://vuejs.github.io/vitepress/v1/guide/deploy).

On this macOS host, both root and `/agent-skills/` production builds passed. The new regression test checks every generated HTML page for root-relative links/assets escaping the Pages base and missing local targets, plus favicon and home-footer notice links. All five documentation tests and eleven helper/installer tests passed; structural validation reports 56 skills and zero problems, and all 137 Python tests passed. Workflow YAML parsing and `git diff --check` passed.

GitHub's API confirmed Pages is enabled with `build_type: workflow` at `https://fullerzz.github.io/agent-skills/`. Deployment remains pending until the workflow reaches `main`; these local build checks do not establish a live Pages deployment, browser interaction, or a Docker rebuild.

## Sharpen prompt rewriting — 2026-10-20

Added the shared explicit-only sharpen skill and its Codex invocation policy, documented the review-and-send handoff, and advanced all three native manifests to `0.17.0`. Reviewed upstream PR #729 and its merge commit `88d47514b82e7c44f00f2b2a72ff6dd12158038c`, including the skill, guides, help text, and generated Claude copies. Local integration uses one shared skill instead of importing the upstream harness tree.

Checks on this macOS host:

- `uv run scripts/validate.py`: 56 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the documentation build and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 137 tests passed.
- `uv run scripts/package_plugin.py`: succeeded; the sharpen entrypoint and Codex policy byte-match their generated copies in `dist/zstack`.
- `git diff --check`: passed.

The successful commands used Homebrew binaries ahead of sandbox-incompatible mise shims and access to the existing uv dependency cache. An initial sandboxed Node run passed the four documentation checks but failed the eleven helper/installer checks; the rerun with cache access passed all fifteen. The installed skill-creator quick validator rejects `disable-model-invocation`, a required repository-standard Claude field; the repository validator accepts and checks both host invocation policies.

Source review checked the four asks, preservation of constraints and open choices, conditional handling of unknown inputs, and the explicit stop before execution. These are source, packaging, and regression checks, not a live sharpen behavior result. Fresh Codex, Claude Code, and Hermes invocation and upstream model evaluations were not run. No personal installation or settings changed.

## Formal-verification maintenance — 2026-10-19

PR #59 review follow-up: clarified that each generator checkpoint advances independently after its own evidence completes; a blocked sibling stays unchanged. Structural validation and whitespace checks passed for this wording correction. The earlier mixed-success behavioral fixture directly exercises this rule; the fixture and full test suites were not rerun for the clarification.

Added explicit-only maintenance, per-check generator coverage/checkpoints, and matching guides; all three native manifests advance to `0.16.0`. Structural validation passed (55 skills, zero problems), all 15 Node tests passed including the documentation build and isolated installer fixtures, all 137 Python tests passed, and `git diff --check` passed. Packaging succeeded and the new entrypoint and Codex invocation policy byte-match their packaged copies. Initial test subprocesses hit sandbox-incompatible mise shims; the successful runs prepended `/opt/homebrew/bin` to PATH. The installed skill-creator quick validator rejects the repository-standard `disable-model-invocation` field; the repository validator accepts and checks the native invocation contract.

An independent agent manually exercised the skill in `/tmp/zstack-formal-eval-kW2RmR`: a bounded queue model remained green after source capacity changed from two to three, then correspondence was updated. Removing the real enqueue guard in a disposable copy triggered correspondence review; translating that change into the handwritten model produced a capacity counterexample, and direct implementation replay failed at four items. An unavailable second verifier returned executable-not-found (recorded as 127) and retained its earlier checkpoint while the successful check advanced. A second scenario preserved a staged caller edit and unstaged capacity change to four byte-for-byte, recorded a separate source digest, and retained both commit checkpoints. The translated mutation and implementation replay failed at five items; restored baselines and the next-agent rerun passed. Evidence and the evaluation script remain in that temporary directory; the coordinator inspected checkpoint records and failure/rerun outputs.

A separate independent read-only review found no actionable instruction or integration defects. These are synthetic bounded Python-model and manual workflow results, not TLA+, concurrency, automatic code/model equivalence, or live Codex/Claude/Hermes plugin discovery. No upstream evaluation scores were reproduced, and no personal plugin configuration was changed.

## Optional formal-verification setup offer — 2026-10-18

Workflow-reference follow-up: the setup entry now documents inspection of formal tooling and skills, the conditional one-time offer, and explicit user invocation after acceptance in its process and expected-result sections. The repeated invocation finding was already fixed in `a1f09bf`. Structural validation (54 skills, zero problems), all 15 Node tests including the documentation build, and whitespace checks passed for this documentation-only correction. Python tests and live host behavior were not rerun.

Tool-selection follow-up: reviewed PR #721 at `5bd8f4a2ae7c0ca0b9a2bd937839e847dd8ab534` and adapted its TLA+ default and no-verifier fallback. The generator and guide require real-code generated-input testing when a language lacks a verifier and distinguish that evidence from formal proof. Structural validation (54 skills, zero problems), all 15 Node tests, all 137 Python tests, and whitespace checks passed after the change. No TLA+ run, generated-input workflow, or upstream behavioral evaluation was reproduced; these results establish local source consistency and regressions only.

PR #58 review follow-up: both invocation comments identified the same blocked handoff. Setup now directs an accepting user to explicitly invoke the generator through their host and forbids loading it directly to bypass invocation restrictions. The setup guide and PR description match that handoff. After this correction, structural validation (54 skills, zero problems), all 15 Node tests, all 137 Python tests, and whitespace checks passed; live host invocation remains untested.

Two workers requested with `gpt-6.1-sol` separately updated setup and the guides for the selective PR #715 port. Setup inspects formal tooling and skills, offers generation once when relevant coverage is absent, and hands accepted offers back to the user for explicit invocation through the host. The guides retain bounded-model limits and describe the existing helper and evidence-retention requirements. Native manifests advance together to `0.15.0`.

Checks on this macOS host: structural validation passed (54 skills, zero problems), all 15 Node tests passed (including the documentation build and isolated installer fixtures), and all 137 Python tests passed. The skill-creator quick validator passed with PyYAML supplied through uv, and `git diff --check` passed. An independent reviewer requested with `gpt-6.1-sol` found no actionable issues in the source diff. Homebrew binaries bypassed the sandbox-incompatible mise shims; no personal configuration was changed.

These are source and local regression checks. The setup offer, acceptance/decline flow, and generator handoff were not exercised in a live Codex, Claude Code, or Hermes session; no formal-verification generator run was needed for this instruction change.

## Ketchup batch coverage and formal verification — 2026-10-18

PR #57 review follow-up: the default generated name is now `verify-formal-<area>`, with a preflight of canonical files and symlinks before writing. Unrelated destinations are preserved; an occupied exact requested path is reported rather than overwritten. Hermes and hosts without a known discovery contract use an ordinary project source folder and report registration pending. The workflow-reference overview now correctly reports 30 workflow/style skills. The earlier counter evaluation below predates this path-only correction; it establishes the verification loop, not the final generated name or Hermes discovery behavior.

A fresh read-only reviewer checked runtime-skill coexistence, unrelated destination files and symlinks, occupied exact requested paths, explicitly requested formal-skill updates, and Hermes without project discovery; no actionable gaps remained. Structural validation, all 15 Node tests, all 137 Python tests, packaging with byte comparison of the revised skill, and diff whitespace checks passed after the corrections. The path review is instruction-level evidence, not live discovery or registration.

Added explicit constituent-item coverage to ketchup and an explicit-only formal-verification generator. The three native manifests advance to `0.14.0`. Two bounded implementation workers owned separate skill files; a fresh independent source reviewer found no actionable issues. Model identity was unavailable. The coordinator inspected the resulting diff and evaluation artifacts.

Checks on this macOS host:

- `uv run scripts/validate.py`: 54 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the documentation build and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 137 tests passed.
- `uv run scripts/package_plugin.py`: succeeded; the new entrypoint, Codex invocation policy, and ketchup entrypoint matched the packaged files byte for byte.
- `git diff --check`: passed.

A fresh native worker followed the new generator in an isolated temporary project with a saturating counter. Its checker executed the actual transition function to a fixed point: the baseline passed with three reachable states and six transitions. Removing the increment guard in an owned disposable copy produced the specific counterexample `inc, inc, inc → 3`, rather than only a changed-source warning. After scratch cleanup, the unchanged baseline passed again; invocation from another working directory also passed, and source snapshots, the mutation diff, commands, and results survived cleanup. The coordinator inspected the generated skill, checker, and report. Completeness applies to this pure, deterministic finite-state fixture under the documented assumptions, not arbitrary Python programs.

Ketchup received a static scenario review for single decisions, a batch of twelve PRs, and mixed recommendations; no live catch-up output was evaluated. The formal-verification exercise is one local native-agent scenario, not proof of fresh plugin discovery on Codex, Claude Code, or Hermes, nor coverage of handwritten models, an already-failing baseline, or every verification tool. Evidence remains in `/private/tmp/zstack-formal-eval-x2rnak2w/evidence/`; orchestration notes remain in the ignored `.agent-work/formal-verification-port/` directory. The generic skill-creator validator rejects the repository-supported `disable-model-invocation` field; the repository validator accepted it and the matching Codex policy. Installed Homebrew uv and Node binaries bypassed sandbox-incompatible mise shims; no personal installation was changed.

## Upstream documentation consistency adaptation — 2026-10-17

CommonMark review follow-up: replaced source-destination regex extraction with markdown-it-py's CommonMark tokens, using the parser already installed through Rich and declaring it explicitly in the validator's inline dependencies. Existing bare destinations with balanced/nested parentheses and Markdown escapes are accepted; rendered full, collapsed, and shortcut reference links and images receive the same path checks. Unused definitions and inline, indented, or fenced code examples are excluded. Nine regression subcases failed before the repair. All 137 Python tests and 15 Node tests passed afterward, including the documentation build; structural validation (53 skills, zero problems), Ruff lint/format, project mypy (28 files), and diff whitespace checks also passed. Generic local-link validation and packaged plugin behavior remain unchanged; live host behavior was not rerun.

Angle-destination review follow-up: current-source checks now extract and unwrap paired angle-bracket destinations, including paths with parentheses, optional titles, and query/fragment components. Generic local-link validation remains unchanged. Five source regression cases failed before the fix; all 134 Python tests and 15 Node tests now pass, including the documentation build. Structural validation (53 skills, zero problems), Ruff lint/format, project-wide mypy (28 files), and diff whitespace checks passed. Live host behavior was not rerun.

Second PR #56 review follow-up: current-source links accept optional double-quoted, single-quoted, and parenthesized titles, including escaped delimiters. Strict decoding and path-resolution errors now produce a broken-link failure for that link and continue to later links. Regression tests reproduce the title bypass and decoding/resolution crashes through both the catalog helper and the complete validator; they also keep a real replacement-character filename from masking invalid UTF-8. All 132 Python tests and 15 Node tests passed; the 24 focused validator tests passed again after adding escaped-title cases. Structural validation, Ruff lint/format, project-wide mypy, and diff whitespace checks passed. Live host behavior was not rerun.

PR #56 review follow-up: source links now parse query and fragment components separately, decode only the path, and reject resolved targets outside the checkout, including escaping symlinks. Prose extraction excludes both backtick and tilde fences with matching markers and sufficient closing length. Overview counts recognize words one through ten as well as digits. The new regressions reproduced the reported failures before the fixes; all 129 Python tests and 15 Node tests passed afterward. The 21 focused validator tests passed again after test typing cleanup, along with structural validation (53 skills, zero problems), Ruff lint/format, project-wide mypy (28 files), and diff whitespace checks. Live host behavior was not rerun.

Reviewed pstack #702, #705, and #704 against zstack's current native-host contracts. The selective #704 adaptation adds tree-backed overview counts and current-source link checks to the existing validator. Three regression tests cover stale counts, missing source targets, fenced examples, historical records, native-role deduplication, and invalid skill slugs. Existing rendered-reference-anchor tests continue to cover the documentation catalog.

Checks on this macOS host:

- `uv run scripts/validate.py`: 53 skills, zero structural problems.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 125 tests passed.
- `node --test scripts/*.test.mjs`: 15 tests passed, including the production documentation build and isolated installer fixtures.
- Ruff lint and format checks for both changed Python files passed; project-wide mypy passed across 28 source files; `git diff --check` passed.

The sandboxed mise shims failed, so checks used installed uv and Node binaries through PATH. Tests used isolated fixtures; no personal installation was changed. Live Claude Code, Codex, and Hermes discovery or agent behavior were not rerun. The count check deliberately covers current README/homepage catalog wording, and source-link checking covers current-repository file targets rather than remote availability or heading fragments. Historical records and Cursor command/model inventories remain outside these new checks.

## Python best-practices skill — 2026-10-17

Latest review follow-up: updated the documentation landing page to 53 skills (the README was already corrected), and explicitly labeled the Codex 48-skill discovery result as historical. Structural validation (53 skills, zero problems), all four documentation tests including the production build, and `git diff --check` passed. Fresh-host discovery was not rerun, so the guide does not claim discovery of the current 53-skill package.

PR review follow-up: corrected the workflow count to 29 and the README total to 53, and reconciled automatic Python skill selection across the overview, setup guide, and Codex host guide. Structural validation (53 skills, zero problems), all 15 Node tests including the documentation build, and `git diff --check` passed. This documentation-only correction did not rerun Python tests or live host invocation.

Follow-up: enabled Codex implicit invocation for Python guidance and updated the validator allowlist, regression fixtures, and workflow reference. Claude's shared invocation flag remains explicit. Structural validation, all 15 Node tests, all 122 Python tests, Ruff lint/format checks, and project mypy passed after this change. Live automatic skill selection remains unverified. The existing `0.13.0` minor bump covers the new skill and its final invocation policy in this PR.

Added a Python companion with uv workflows, Ruff formatting and linting, mypy, extensive type hints, and Pydantic boundary validation. The examples reference contains script/package commands, checking configuration, a boundary self-check, and typed internal variants. Added its workflow reference and advanced all three native plugin manifests from `0.12.3` to `0.13.0` under the new-skill versioning policy.

Checks on this macOS host:

- `uv run scripts/validate.py`: 53 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: 15 tests passed, including the documentation build and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 122 tests passed.
- Extracted both Python examples and the mypy/Ruff configuration into a temporary directory. Ruff formatting and lint checks passed; strict mypy with the Pydantic plugin passed for both files. Pytest ran the boundary example: one test passed, covering valid data, empty input, invalid quantity types/ranges, and extra fields.
- `git diff --check`: passed.

The mise shim failed inside the sandbox, including subprocesses in the first Python suite run. Checks passed after selecting the installed uv and Node binaries directly through PATH. The generic skill-creator validator rejects this repository's supported `disable-model-invocation` field; the repository validator verifies that field and the matching Codex invocation policy successfully. No personal configuration was installed or changed. Fresh-host skill invocation and the full initialization command sequences were not exercised; example execution and structural checks do not establish live agent behavior.

## PR watcher single-pass status and repositories without checks — 2026-10-17

[Issue #53](https://github.com/fullerzz/agent-skills/issues/53) reported that `--status-only` retried for minutes when GitHub reported no checks. The GitHub resolver now accepts exit 1 with `no checks reported` as zero checks after the GraphQL fallback succeeds with an empty rollup. Other fast-path errors and failed fallback queries still fail closed; checks found by the fallback still take precedence. Status-only runs use a one-attempt query-error budget, returning the existing terminal status-query blocker (exit 7) on failure. Normal polling retains its retry budget.

The shared Codex, Claude Code, and Hermes plugin version advances from `0.12.2` to `0.12.3` for this compatible packaged fix.

Checks on this macOS host:

- New regressions failed before the fix: the no-checks case returned BLOCKER, the subprocess fixture timed out, and status-only failures emitted five events instead of one.
- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: 15 tests passed, including the documentation build and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 122 tests passed, including 56 watcher tests. The existing output golden is unchanged. New checks cover status-only failures at each snapshot query in single, stack, and queued-stack modes, plus open no-checks PRs through the subprocess fixture.
- Ruff check and format check on the changed Python files, strict mypy (28 source files), and `git diff --check` passed.

Live read-only check: `gh pr checks 5 --repo fullerzz/busy-apps` still returned exit 1 with `no checks reported`. Calling `GitHubReader.checks()` directly for that PR reproduced the reported retryable `checks-unavailable` before the fix and returned `{"source": "graphql-rollup", "checks": []}` after it. That PR is now merged and the repository had no open PRs, so the complete open-PR path is verified by fixtures. Subprocess timeouts remain outside this fix.

## Host-aware native agent guidance — 2026-10-16

The shared delegation contract now selects only roles exposed by the worker's host. Native workers are the expected path for Codex and Hermes plugin installations; Claude Code prefers its registered plugin roles, and linked installations can use their native role copies when exposed. Expected role absence no longer requires a fallback announcement. Missing delegation and capability gaps that affect the requested work still require reporting, and the selected execution method's fallback rules still apply. The absolute z-mode instruction path and scoped brief remain required for children following the mode. The README and all three host guides use the same distinction. The shared plugin version advances from `0.12.1` to `0.12.2` for this packaged wording fix.

Checks on this macOS host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: 15 tests passed, zero failed or skipped, including the documentation build.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 118 tests passed.
- `git diff --check`: passed.

Source review checked the guidance against the Codex packaging resources, Claude plugin agent registration, Hermes plugin entrypoint, and linked installer. These checks establish instruction and packaging consistency; live Codex, Claude Code, and Hermes delegation sessions were not run, so suppression of the fallback announcement is not behaviorally verified. Native agent definitions, hooks, invocation policy, and dependencies are unchanged.

PR #52 review also reconciles the no-comments entrypoint, its workflow reference, and the Codex setup guide with the shared contract. The comment reviewer remains read-only and returns the same report; role selection, scoped briefs, and reporting capability gaps follow the native contract. The existing `0.12.2` patch bump covers these corrections within the same PR.

## Selective pstack PR #634 wording cleanup — 2026-10-15

Adapted the recommended parts of [PR #634](https://github.com/cursor/plugins/pull/634): Interrogate loses repeated lead-judgment setup and Verdict Calibration, including the suggested five-item Act On limit; the type-system principle keeps all eight decisions with shorter examples; API migration loses only its repeated introduction and conclusion. Direct diff review confirmed that API migration retains all four rules and three applicability conditions, Interrogate retains every filtering/security/correctness criterion, and skill frontmatter is unchanged. Swarm, the Interrogate entrypoint, and the principles reference are unchanged. The three native manifests advance together from `0.12.0` to `0.12.1` under the packaged-wording patch policy.

Three native workers used exclusive file scopes; the coordinator inspected each result and corrected a reversed verb in the provenance draft. A separate fresh read-only evaluator applied the updated lead-judgment reference to dashboard helper source and nine candidate findings. It returned all seven reachable correctness defects under Act on and dismissed a speculative zero-input warning and an unsupported class-extraction suggestion, with evidence and rationale. The brief supplied the source, caller contracts, and candidate reports without an intended verdict. This is one source-based native scenario, not a runtime execution or a before/after equivalence result. Built-in native agents substituted for the named z-agent role; their model identity was not exposed.

Checks on this macOS host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: 15 tests passed, zero failed or skipped.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 118 tests passed.
- `git diff --check`: passed.

Local orchestration state, scenario input/receipt, and command logs are retained in the ignored `.agent-work/pstack-634-selective-port/` directory. The generic skill-creator validator rejected the existing `disable-model-invocation` key during the pilot; the repository validator accepts that supported metadata, which remains unchanged. Live Codex, Claude Code, and Hermes plugin sessions were not rerun, so these results do not establish behavior across all hosts. No new executable code or dependencies were added.

## PR watcher GitLab support — 2026-10-15

`watch-pr` now watches GitLab merge requests through `glab` as well as GitHub pull requests through `gh`. A new `gitlab.py` reader maps GitLab merge request data onto the existing facts, so policy, exit codes, and NDJSON schemaVersion 1 stay unchanged. It reads `detailed_merge_status`, head-pipeline jobs and bridges, MR pipelines, and resolvable discussions. Retained wire names are `ci-github-rejected`, the `github` key, and the `gh-pr-checks` and `graphql-rollup` sources; GitLab adds `gitlab-pipeline`. `--forge {github,gitlab}` overrides the default, which is detected from the origin remote. The `Reader` protocol gains `forge`, `checks`, and `web_url`, and pretty output names the forge. The watcher's last Graphite reference, `gt` in a subprocess comment, is gone; `worktree_audit.py` keeps its own copy of that comment outside this change. The shared plugin version advances from `0.11.4` to `0.12.0`.

Checks on this macOS host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 108 tests passed. The watcher golden fixture is byte-identical, so GitHub JSON and pretty output are unchanged. New GitLab tests use injected responses and a fake `glab` on `PATH` driven through `uv run watch_pr.py`.
- Ruff check and format on the watcher and its tests, mypy (28 files, with Rich and PyYAML stubs), ty on `skills/z-mode/scripts`, and `git diff --check`: passed.

Live read-only runs, unauthenticated `glab` 1.123.0 against public gitlab.com:

- `glab api --paginate --output ndjson` emits one value per line across pages. An empty list emits nothing.
- Merged MR `gitlab-org/cli!4124` mapped to `MERGED`. Its merge-train head pipeline runs on merge-ref sha `727a2ef` and was attributed to MR sha `95641f4`. Its 23 jobs read as 22 passed and 1 skipped.
- On open MRs, `not_approved` mapped to `BLOCKED` and `REVIEW_REQUIRED`, and `unchecked` mapped to `UNKNOWN`.
- `watch_pr.py --forge gitlab --owner gitlab-org --repo cli --pr 4124 --status-only` exited 0 in JSON and `--pretty`. The same check on GitHub PR #49 also exited 0.

The first live GitLab run from this GitHub checkout exposed a bug: a forced `--forge gitlab` took `github.com` from the origin as the GitLab host and got HTTP 404. The fix ignores a GitHub origin when choosing the host, and a regression case covers it.

Limits:

- Discussions return 401 without authentication, so thread mapping is proven only by fixtures. No authenticated or self-hosted GitLab instance and no open-MR watch-to-READY cycle were exercised.
- `detailed_merge_status` reports one blocking reason, so another reason can mask the review state.
- Checks read the head pipeline's jobs and bridges. Child-pipeline jobs appear only through their bridge's status.
- The live watcher run used a merged MR, which returns before reading jobs, pipelines, or discussions; those paths were exercised live only through direct reader calls.

### PR #50 review fixes

An interrogate review and the PR's bot comments found five defects in the GitLab reader. All five are fixed in `gitlab.py`:

- **Outdated head pipeline.** After a push or a `[ci skip]` push, `head_pipeline` can still point at the previous commit's green run, and that used to read as ready. Now it counts as current only if its sha equals the MR sha, or if it is a `refs/merge-requests/<iid>/merge|train` pipeline whose merge commit has the MR sha among its parents. An outdated pipeline adds no checks and keeps its own sha in the rollups. If nothing else remains, the watcher raises a retryable `checks-unavailable`.
- **Non-review merge blockers.** These read as ready because the policy allows `BLOCKED` with a green rollup. Each one now adds a synthetic `GitLab merge check`:
  - Failed for `merge_time`, `merge_request_blocked`, `jira_association_missing`, `title_regex`, `locked_paths`, `locked_lfs_files`, `security_policy_violations`, `commits_status`, and the legacy `blocked_status`.
  - Pending for `status_checks_must_pass`, the legacy `external_status_checks`, and `security_policy_pipeline_check`.
  - Review-type statuses keep their GitHub-equivalent behavior.
- **`status_checks_must_pass`.** This documented status is now mapped. A test confirms that all 24 statuses in GitLab's current list map.
- **`canceling` pipelines.** Rollups now map `canceling` to `FAILURE`. Before, auto-canceled pipelines caused retry churn.
- **Pipeline that fails before creating any job.** A CI config error leaves the head pipeline failed with no jobs. It now becomes a failed `GitLab pipeline` check (exit 4) instead of `checks-unavailable` (exit 7).

A Herdr-launched Claude Code worker made the fixes. It reverted each fix in turn and confirmed that a new test failed each time, then restored the file byte for byte. It also checked public MR `gitlab-org/cli!4124` live: the merge-train head pipeline's merge commit `727a2ef` has MR sha `95641f4` among its parents, so the pipeline is accepted as current, with 23 checks and its rollup relabelled.

Coordinator checks after the fixes:

- `uv run scripts/validate.py`: 52 skills, zero problems.
- `node --test scripts/*.test.mjs`: 15 tests passed.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: 115 tests passed. The golden fixture is unchanged.
- Ruff check and format, mypy (28 files), ty, and `git diff --check`: passed.

Limits:

- None of the following were exercised live: an outdated pipeline, an open MR with a merge gate, a `/merge` ref, a fork MR, a zero-job failed pipeline, or a `canceling` pipeline.
- `merge_time` reports as failing (exit 4) even though it clears on its own.
- A failed external status check reads as pending until timeout.

### Rebase and skipped-pipeline gates

Two more review findings could produce a false READY:

- **Required rebase.** `need_rebase` maps to `BEHIND`, which the policy allows. It now also adds a failed `GitLab merge check`, because fast-forward and semi-linear merge methods refuse to merge until the source branch is rebased.
- **Unexplained `ci_must_pass`.** A skipped head pipeline can carry `ci_must_pass` in a project that doesn't count skipped pipelines as passing. Its jobs read as skipped and its rollup is empty. `ci_must_pass` now adds a failed merge check whenever no enumerated job is failed or pending. Real failing or pending jobs still explain the gate on their own.

Two decision-level regressions run through `policy.read_snapshot` and `select_stack_decision`. Both failed before the fix and pass with it. The snapshot fixture now passes the head pipeline's actual status into the rollups instead of forcing `success`.

Checks after the fix:

- Full Python unittest discovery passed.
- Ruff check and format, mypy (28 files), ty, `uv run scripts/validate.py` (52 skills, zero problems), and `git diff --check` passed.
- Neither gate was exercised against a live GitLab MR.

### Transient states, CI retry, and ported GitHub remotes

The second bot review of `67c778b` raised three threads:

- **Statuses still being computed.** `checking`, `unchecked`, `preparing`, `approvals_syncing`, and `ci_still_running` mean GitLab is still evaluating mergeability, approvals, or CI. Each now adds a pending `GitLab merge check`, so the watcher waits instead of reading the MR as clear.
- **Unexplained `ci_must_pass`.** The fallback now applies only to a current head pipeline:
  - A missing or outdated pipeline stays a retryable `checks-unavailable`.
  - A running pipeline adds a pending check, which covers both no jobs yet and all jobs green so far.
  - A finished pipeline whose jobs don't explain the gate still fails.
- **GitHub remotes with an explicit port.** With `--forge gitlab`, `ssh://git@github.com:22/...` and `https://github.com:443/...` were taken as GitLab host `github.com`. `parse_remote` rejects ports, so a github.com hostname now also counts as a GitHub origin, and the host falls back to `GITLAB_HOST` or `gitlab.com`.

The new forge-selection cases and decision-level tests failed before the fix (8 subtest failures) and pass with it.

Checks after the fix:

- Full Python unittest discovery passed.
- Ruff check and format, mypy (28 files), ty, `uv run scripts/validate.py` (52 skills, zero problems), and `git diff --check` passed.
- None of these paths was exercised live.

## Selective pstack principle durability port — 2026-10-15

Ported the four guidance updates from [pstack PR #633](https://github.com/cursor/plugins/pull/633), aligned Correct and the principles reference, and recorded upstream attribution. The shared plugin version advances from `0.11.3` to `0.11.4` for compatible packaged wording changes. Explicit-only invocation metadata, scoped fixes, required validation, safe failure handling, and separate action authority remain intact; no executable behavior changed.

Checks on this macOS host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the VitePress build, reference anchors, license notices, and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 93 tests passed, including bundled helpers.
- `git diff --check`: passed.

The generic installed skill-creator `quick_validate.py` rejected the first edited skill's existing `disable-model-invocation` frontmatter key and stopped before checking the remaining four. Its accepted schema does not support this repository's explicit-only metadata; the field was preserved, and the repository validator above passed.

The first sandboxed attempts stopped at the mise shims with `Operation not permitted`, before any checks ran; the approved reruns above passed. Installer tests used their isolated fixtures, not real personal configuration.

Manual scenario review checked that the text retains empty-result and no-charge contracts, distinguishes external mocks from private helpers, accepts guards for legitimate first-start state while tracing malformed-state producers, permits time-based premise tests, and refuses to infer stale ownership from a PID alone across hosts. This is a prose review, not an independent model evaluation or a live host behavior result. No fresh Codex, Claude Code, or Hermes session exercised the revised guidance; upstream evaluation results are not claimed for this port.

### PR #49 review repair

Addressed the review's convergence gap: reconciliation now explicitly includes additions, updates to incorrect values, and safe removals of surplus resources within authorized scope. The reference example covers missing jobs, stale configuration, and obsolete duplicates; ownership and staleness safeguards remain intact. This is a wording correction within the unreleased `0.11.4` port.

After the correction, `uv run scripts/validate.py` again reported 52 skills and zero problems, `node --test scripts/*.test.mjs` passed all 15 tests including the docs build, and `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'` passed all 93 tests. `git diff --check` passed. These checks validate structure and existing regressions, not fresh-host adherence to the revised prose.

Historical observations below retain the names used during those runs (`pstack`, `poteto-mode`, and `poteto-agent`). Current equivalents are `zstack`, `z-mode`, and `z-agent`; those earlier observations do not establish live behavior under the new names.

## Plugin website metadata — 2026-10-15

The Codex manifest now sets `homepage` and `interface.websiteURL` to `https://zstack.zachfuller.sh`. [OpenAI's manifest reference](https://developers.openai.com/plugins/deploy/submission#manifest-fields) defines the listing website separately from the package homepage. Claude uses the same URL in its supported [`homepage` field](https://code.claude.com/docs/en/plugins-reference#fields); Hermes' existing `homepage` field now points to the website instead of GitHub. All three plugin versions advance together from `0.11.2` to `0.11.3` using `uv run scripts/bump_version.py patch`.

On this macOS host, `uv run scripts/validate.py` reported 52 skills and zero structural problems; `node --test scripts/*.test.mjs` passed all 15 tests, including the docs build; and `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'` passed all 93 tests. `claude plugin validate .claude-plugin/plugin.json --strict` passed. A read-only Python assertion verified all three homepage values, Codex's listing website, and the shared version. The initial sandboxed version helper could not start mise; the helper and uv/Node checks passed with sandbox escalation.

No installed plugin cache was refreshed or live website-link rendering tested in Codex, Claude, or Hermes. No publication was performed.

## Claude plugin icon and Hermes support — 2026-10-15

The Claude manifest's `icon` points directly to `./docs/public/logo.svg`. [Anthropic's manifest reference](https://code.claude.com/docs/en/plugins-reference#directory-listing-fields) defines this as directory-listing metadata; Claude Code ignores it at load time. Claude Code 2.1.300 passed `claude plugin validate .claude-plugin/plugin.json --strict`. Structural validation reported 52 skills and zero problems; all 15 Node tests (including the docs build) and all 93 Python tests passed.

Hermes receives no icon metadata: the current upstream [manifest model and parser](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/plugins_manifest.py) expose no icon field. No directory submission, installed-plugin refresh, or live icon rendering was tested for either host.

**PR #47 review repair.** `uv run scripts/bump_version.py patch` advances the Codex, Claude, and Hermes manifests together from `0.11.1` to `0.11.2`, giving versioned marketplace installs a new release for the icons. After the bump, structural validation reported 52 skills and zero problems, all 15 Node tests and all 93 Python tests passed, and Claude strict manifest validation passed. Live marketplace upgrades were not tested.

## Codex plugin icon — 2026-10-15 {#codex-plugin-icon}

The Codex manifest's `interface.logo` and `interface.composerIcon` point to `.codex-plugin/logo.svg`, a byte-identical copy of the website's `docs/public/logo.svg`. Keeping the copy under `.codex-plugin` includes it in the existing package resource selection.

On this macOS host, structural validation reported 52 skills and zero problems, all 15 Node tests passed (including the docs build), and all 93 Python tests passed. An isolated temporary Git checkout packaged the current resources plus the new icon and confirmed that both manifest paths resolve to the website SVG byte for byte. The initial sandboxed checks could not start mise; the checks passed with sandbox escalation.

**Limits.** No installed plugin cache was refreshed or live Codex icon rendering tested. The new SVG must be tracked when committing so the tracked-resource packager includes it.

## Codex hook label — 2026-10-15 {#codex-hook-label}

The remaining Codex `SessionStart` handler now supplies `statusMessage`: "zstack session setup: load guidance and restore saved z-mode and Herdr preferences". This adds a readable name and purpose to the hook's running status.

All three native plugin manifests advance together to `0.11.1` for this compatible packaged wording change, using `uv run scripts/bump_version.py patch`.

On this macOS host, `uv run scripts/validate.py` reported 52 skills and zero structural problems; `node --test scripts/*.test.mjs` passed all 15 tests, including the docs build; and `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'` passed all 93 tests. A direct JSON comparison against HEAD confirmed that only `statusMessage` changed in the hook configuration.

**Limits.** Source inspection of Codex App `26.1007.71326` (build `20398`) found that its hook settings renderer uses a non-empty `statusMessage` for the numbered row title. This is not a live UI result or a guarantee for older clients, which may retain generic numbered labels ([older-client report](https://github.com/openai/codex/issues/41611)). No installed plugin cache was refreshed and no live display of this new label was tested. Refreshing the plugin requires reviewing the changed hook through Codex's trust flow.

## Xray removal — 2026-10-15 {#xray-removal}

Removed `xray-session`, the shared recorder, recording context and control events, and the Codex, Claude Code, and Hermes observers. All three plugin manifests advance to `0.11.0`. The remaining session hooks preserve z-mode and Herdr selection. Earlier xray sections below are historical evidence for the removed feature.

On this macOS host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the VitePress production build, reference anchors, and isolated installer checks.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 93 tests passed. Coverage includes session activation, resume, fork/reset isolation, Herdr selection, and a legacy `ZSTACK_XRAY=1` setting producing no recording context or files. The new Codex removal checks failed against the prior implementation before removal.
- Ruff lint and format checks passed for all seven changed Python files. `uv run --with mypy --with rich --with types-PyYAML mypy` passed on 26 source files.
- `uv run scripts/package_plugin.py` rebuilt the tracked Codex package. Direct artifact assertions confirmed no xray skill or recorder, only `SessionStart` in both bundled hook manifests, and version `0.11.0`.
- `claude plugin validate . --strict` and `claude plugin validate .claude-plugin/plugin.json --strict` passed for the marketplace and plugin manifests respectively (Claude Code 2.1.300).
- `git diff --check` and the staged equivalent passed.

**Limits.** These are local fixtures, artifact assertions, and manifest validation, not fresh model-driven Codex, Claude Code, Hermes, or Windows sessions. Hermes was unavailable on this host's PATH. No installed plugin cache or existing capture data was changed for this removal; older hosts require a plugin refresh and restart. Linked installs must uninstall from the old checkout before updating and reinstalling, as described in [setup](guide/01-setup.md#upgrade-0-11-0).

**PR #45 review repair.** The Codex test control helper now passes its isolated environment and `--host=codex`; the legacy-setting regression checks for unexpected files after disable as well as enable. In temporary helper copies, injected recording gated on the host, action, and `ZSTACK_XRAY=1` escaped the prior test on both actions and failed the repaired test on both. README and the docs homepage now report the validated total of 52 skills; historical counts below remain unchanged.

On the same macOS host, all 93 Python tests and all 15 Node tests (including the docs build) passed after the repair. Structural validation reported 52 skills and zero problems; Ruff lint/format for the changed test and `git diff --check` passed. No fresh live host sessions were run for this test/documentation repair.

## Strict mypy for helper scripts — 2026-10-14 {#strict-mypy}

`mypy.ini` now enables `strict`. The changes:

- **watch-pr:**
  - The NDJSON contract lives in `schema.py` as TypedDict unions: events, snapshots, blockers, CI states and parsed GitHub facts.
  - CI is split into pending, failing, rejected and clean variants, so a ready proof can only carry clean CI.
  - Watcher options and poll steps are frozen dataclasses.
  - Blocker exit codes and poll steps are matched exhaustively.
- **orch:**
  - The store types its unit, ledger, inbox, gate, frontier, standing-order and status rows. Gates are an open/resolved union.
  - The CLI dispatches each command group through a typed `match` instead of `getattr`.
- **Tests:** the watcher tests import the real modules, so mypy checks the fake reader against the `Reader` protocol.

On this macOS host:

- `just mypy` passed on 28 files, and ruff check and format were clean.
- Structural validation found 53 skills and zero problems.
- All 15 Node tests and all 124 Python tests passed, and `git diff --check main...HEAD` was clean on the review-fix commit.

**Watcher evidence.** The committed golden file `scripts/fixtures/watch-pr-events.golden` was generated from the pre-refactor modules. It runs 22 scenarios in JSON and `--pretty`, 44 runs in total. The runs cover:

- every verdict, blocker, wait and timeout kind
- retries
- stack, queued-stack and status-only modes

The refactored modules reproduced it byte for byte. Reordering one key in a dict literal makes the golden test fail.

**Parser evidence.** A scratch harness compared `GitHubReader` parsing with HEAD on valid and malformed responses. The only difference was the error detail for a non-object `gh pr list` row: `invalid open PR: 5` instead of `invalid number: 5`.

**Fixed after review.** An intermediate version of this change read `reviewDecision` before `mergeable`, `mergeStateStatus` and `state`. That changed which error a payload with several bad fields reported. The original order is restored and covered by a regression test.

**Correction after PR review.** The first version of this record said `git diff --check` was clean. That check ran while the golden file was still untracked, so git skipped it. On the committed range the check failed on two lines of the fixture, both from `--pretty` blocker lines whose trailing fields were empty: a review thread with no comment, and a failing check with no description or link. The renderer now trims trailing spaces from blocker lines. That is the only output change in this PR. The regenerated golden matches the pre-refactor output with trailing spaces stripped, and NDJSON output is unchanged.

**orch evidence.** A scratch transcript ran 89 orch commands, compact and `--json`, against HEAD and the refactor. It included `frontier set` through a fake `gh`, malformed store files, and a hand-edited `frontier.json` with reordered and extra keys. After normalizing timestamps, paths and SHAs, the two transcripts were identical. An intermediate version rebuilt `frontier.json` and dropped unknown keys; `frontier_show` now returns the validated object unchanged.

**Limits.** All of these runs used fake `gh` responses, not live GitHub.

## Orchestration cleanup: shipping safety — 2026-10-14 {#orchestration-shipping}

Top layer of the [orchestration cleanup stack](provenance.md#pstack-orchestration-cleanup). Shipping gains pinned force-push leases, a pre-merge trunk-drift check with a third-rebase hold, and the post-merge child retarget; Autopilot-full scales re-verification to the change; Autopilot-stack names the coordinator as the only link rebaser. Manifests declare `0.10.0`.

This is a wording change checked statically: 53 skills with 0 structural problems, 15/15 Node tests, 121 Python tests, and a clean `git diff --check`. No playbook run landed a stack under the new rules, so they are not live-verified.

Review fixes: step 6 applies only when the merged PR has a child, and opening-a-pr requires landing authority before invoking it. Autopilot-stack restates the one-verifier rule, including conflict resolution, and links Autopilot-full. A later round made the coordinator's topology writes follow an owner handoff and gated pushes on publication authority. A third round made Shipping step 6 depend on landing authority that covers the child and on a base SHA recorded when the link was created or rebased, which Autopilot-stack and Opening a PR now record. A later round requires a merge-free child range, since rebase drops merge commits and their resolutions. A scratch repository checked the child move: after a parent fix round amended the parent commit and the parent was squash-merged, `git rebase --onto main <parent-final-head> child` stopped on an add/add conflict, while `git rebase --onto main <child-base> child` replayed only the child commit and kept the fixed parent content.

### PR #42 merge-result destination — 2026-10-14

Shipping now pins the confirmed merge-result SHA, verifies it is in the fetched remote-tracking trunk's history, and uses it as the child rebase destination. A fresh scratch Git repository reproduced the old command's stale-local-trunk problem: after fetching the parent's squash merge, rebasing the child onto local `main` succeeded but removed the parent's module from the child checkout. Rebasing the original child onto the fetched merge-result SHA retained both modules. This is a local Git experiment, not a live forge landing or an agent following the full playbook.

The updated stack top passed structural validation (53 skills, zero problems), all 15 Node tests, all 122 Python tests, mypy across 27 files, and `git diff --check`. A live read-only call of the updated frontier resolver from the top checkout returned `#40, #41, #42` in order with their local branch heads. The repaired branching and closed-PR cases remain fixture-only checks; no GitHub topology was mutated for testing.

### PR #42 managed-stack recovery — 2026-10-14

The next review identified stale stack-manager metadata after the manual child rebase. In a fresh temporary repository, the installed gh-stack extension created a parent/child stack; a raw rebase of the child onto the parent's squash-merge commit changed the Git head but left the stack file unchanged and its recorded child base pointing at the original parent. Shipping now routes managed branches through documented manager recovery, checks scope, publication effects, replay boundaries, and merge handling, and verifies the resulting tracking state. The raw SHA-based recipe is restricted to unmanaged branches. The installed gh-stack help confirms that `sync` also pushes the stack, so it is subject to the existing authority and pinned-lease requirements. No real stack was merged or retargeted for this check; the recovery path itself was not exercised against GitHub.

This wording revision passed structural validation (53 skills, zero problems), all 15 Node tests including the documentation build, all 122 Python tests, and `git diff --check` on this macOS host.

## Orchestration cleanup: frontier without Graphite — 2026-10-14 {#orchestration-frontier}

Second layer of the [orchestration cleanup stack](provenance.md#pstack-orchestration-cleanup). `orch frontier set` walks the `gh` PR base chain instead of reading Graphite metadata. Manifests declare `0.9.1`.

The rewritten fixture test drives a real Git repository with trunk `trunk` through a fake `gh` that rejects an inherited `GH_REPO` and a missing `--limit`: a merged parent its child still targets, a branch whose earlier PR closed, a fork PR reusing a stack branch name, an open child, a child merged into its parent's branch (resolved from the bottom branch), pin mismatches that leave `frontier.json` unchanged, a second open child (`not linear`), a parent without a PR, a tag standing in for a deleted local branch, invalid JSON, and trunk (empty chain). Against the previous resolver it fails at the first `gh` call, which asserted `GH_REPO` was cleared.

Live check against this repository's own three-PR stack (#40 to #42), running the layer's code from a copy so checkouts did not swap it: from the middle and bottom branches it resolved `#40, #41, #42`, all `OPEN`, with local head SHAs and lowest unmerged `#40`; on `main` it returned no PRs; the pin `40,42,41` failed with `order differs`. After review fixes, a rerun with `GH_REPO=cli/cli` exported resolved the same chain from the bottom and top branches and an empty chain on `main`, so the override no longer leaks into `gh`. Later review rounds added fixture cases for a closed child with an open descendant, directly or through another closed PR (reported as an error), and for reused branches whose current PR merged after an older one closed or closed after an older one merged, walking down or up the chain (resolved to the newer PR), including a child branch whose newer PR moved to another base, a closed child with a live descendant beside an open sibling and a closed parent reached walking down (both reported as errors), and a descendant whose newer PR moved to another base (not counted). A live rerun after these fixes still resolved this stack from the bottom and top branches. Merged-parent, merged-child, closed-child, and retarget states were exercised only in the fixture.

Validation on the stack top: 53 skills with 0 structural problems, 15/15 Node tests, 121 Python tests, mypy clean across 27 files, and a clean `git diff --check`.

### PR #41 remaining frontier findings — 2026-10-14

Regression fixtures reproduced the hidden live path through a merged child, acceptance of a closed starting parent with live descendants, and rejection of entirely closed ancestor chains before the fixes. Child selection now considers live descendants of merged PRs alongside open siblings, including when resolution starts above the fork. Closed PRs in the resolved chain are rejected only when they have live descendants. Cases cover open and merged descendants, every starting branch around a fork, an inactive merged sibling, closed roots and intermediate parents, inactive chains, and preservation of the previous frontier on rejection.

On this macOS host, structural validation reported 53 skills and zero problems; all 15 Node tests and 122 Python tests passed, mypy passed across 27 source files, and Ruff lint/format checks passed for the changed Python files. These are local fixture checks, not live GitHub topology mutations or a landing test.

## Orchestration cleanup: owner-approval gate — 2026-10-14 {#orchestration-gate}

Adapted part of [upstream PR #613](https://github.com/cursor/plugins/pull/613) at merge `ce649c03ac3b75b6ae80cbd15b7e2c536caedb5a`, starting from main `e47fb8b`, as the bottom layer of the [orchestration cleanup stack](provenance.md#pstack-orchestration-cleanup). `watch-pr` maps a completed `Code Review Gate` with conclusion `ACTION_REQUIRED` to the `code-review-gate` kind on both read paths; any other check with that conclusion stays `failed` with reported state `ACTION_REQUIRED`. The new regression failed against the unfixed `github.py` and passes with the fix. A review follow-up added a snapshot test: `BLOCKED` with a failing head rollup and an `ACTION_REQUIRED` gate now reads `READY`, while the same rollup with only a pending gate still exits 4; it failed against the previous `policy.py`. The exemption reports `basis: owner-gate`. Limit: a failure that is absent from the enumerated checks but present in the rollup is indistinguishable from the gate on this path; GitHub still blocks the merge until approval, and Shipping re-checks current-head CI. Manifests declare `0.9.0`.

Validation: 53 skills with 0 structural problems, 15/15 Node tests, 121 Python tests, and a clean `git diff --check`. No live PR was watched; the gate behavior is covered by mapping tests only.

## pstack 0.15.23: shorter ketchup — 2026-10-13 {#pstack-0-15-23-ketchup}

Adapted [upstream PRs #595 and #609](provenance.md#pstack-0-15-23) at final merge `c86f349b102feb91f1966f8a6a60882a4e601b50` as the top layer of the stack. A Herdr Claude Code worker rewrote the skill and its doc passages in an isolated worktree from main `caf7a1f`. The coordinator reviewed the diff and cherry-picked it onto the in-your-own-words layer. It repaired one instruction that limited before/after visuals to "other" action items, then added provenance and this record. The skill grew from 796 to 840 words; the new voice, box, and decision-line rules account for the growth.

In a clean detached worktree of the layer commit, structural validation reported 53 skills and zero problems; all 15 Node tests and 120 Python tests passed; `git diff --check` passed. These are static checks. No fresh host session invoked ketchup, so the 150-word budget, box limits, and terminal rendering of the visuals remain behaviorally unverified.

### PR #38 initial review repairs (superseded below)

Review found contradictory and ambiguous instructions. The visual rule required a comparison that the evidence fallback could skip, and the options lived only in that visual. "No … proposed actions" could forbid recommendations. The cut-order sentence had two readings. The "tests pass" example blurred local tests and CI. "Chat renders in terminals" contradicted the Mermaid and capture options in the same sentence. Table boxes had no definition. The repair adds a one-line option list when no visual is grounded, restores upstream's cut order, and states that the word budget wins over box and line caps. Table boxes are now non-header cells, and Mermaid and captures apply only where the host renders them. The install and skills-directory guards and the "where available" status qualifier return. The guide and reference now include the one-line irreversible step, the visual exceptions, the nothing-changed stop, and the screen-change line. The skill is now 908 words.

Review also classified the new output contract as new behavior under the README policy. Manifests now declare `0.8.0` rather than `0.7.1`, consistent with ketchup's `0.6.0` visual release. PR #35 stays a patch because it extends an existing principle; provenance records that rationale.

### PR #38 project-fit revision — 2026-10-13

Replaced the hard word budget with an approximately 150-word target that yields to every unresolved decision, material risk, and evidence gap. Removed mandatory status and decision visuals and all box, cell, label-word, and line-count limits. Visuals now apply only when clearer than prose; decisions retain options, tradeoffs, recommendations, prerequisites, irreversible effects, and known no-answer consequences. Updated the bundled visual reference, README, guide, workflow reference, and provenance. The read-only, scoped-history, current-head, invocation-policy, and evidence boundaries remain intact. The unreleased layer retains version `0.8.0`.

On this macOS host, the revised working tree passed structural validation (53 skills, zero problems), all 15 Node tests including the docs build, and all 120 Python tests. Installer tests used isolated fixtures. This is static validation; no fresh host session exercised a multi-decision catch-up or visual rendering.

### PR #38 documentation consistency repairs — 2026-10-13

Aligned the workflow reference and long-work guide with the skill's unknown no-answer consequence and unasked irreversible-step exceptions. Aligned the README and bundled visual guidance with the status-or-decision visual policy. Structural validation passed with 53 skills and zero problems; all four documentation tests, including the docs build, and `git diff --check` passed. These wording-only repairs did not repeat the full runtime suites or live catch-up checks.

## pstack 0.15.23: in-your-own-words — 2026-10-13 {#pstack-0-15-23-in-your-own-words}

Adapted [upstream PRs #602 and #606](provenance.md#pstack-0-15-23) at final merge `dbf49813a39c1a5389c5e28cb8e4c1c2379e2454` as the third layer of the stack. A Herdr Claude Code worker wrote the skill, docs, and tests in an isolated worktree from main `caf7a1f`; the coordinator reviewed the diff, cherry-picked it onto the z-agent layer, and added manifests `0.7.0`, provenance, and this record.

In a clean detached worktree of the layer commit, structural validation reported 53 skills and zero problems; all 15 Node tests and 120 Python tests passed; `git diff --check` passed. `uv run scripts/package_plugin.py` staged the new skill with its Codex policy, and the packaged manifest declared `0.7.0`. The worker's own run on its base matched these totals. These are static checks; no fresh host session invoked the skill.

### PR #37 review repairs

Review found that the docs both implied and denied a confirmation pause, while the skill body says neither. The guide and reference now describe only the restatement and say the skill does not wait for confirmation. The reference adds Hermes and native-plugin invocations. Provenance now names which tests assert the new skill and which existing check covers its Codex policy.

## pstack 0.15.23: z-agent discovery — 2026-10-13 {#pstack-0-15-23-z-agent}

Adapted [upstream PR #597](https://github.com/cursor/plugins/pull/597) at merge `b93e8117880f695bc49ef7b1ef72c09bfcc7c1de` as the second layer of the [pstack 0.15.23 stack](provenance.md#pstack-0-15-23). Both z-agent roles now name per-host search roots for a missing or unusable z-mode path and pick the highest declared version. Manifests declare `0.6.4`.

A script following the Claude Code search rule on this macOS host found four copies: a stale `0.1.0` plugin cache, two packaged `dist` copies without a sibling Claude manifest, and the in-place checkout. It selected the checkout. That run simulated the procedure; no z-agent was launched without a path, and the Codex roots were not exercised. In a clean detached worktree of the layer commit, structural validation reported 52 skills and zero problems; all 15 Node tests and 120 Python tests passed; `git diff --check` passed.

### PR #36 review repairs

Review found that the fallback missed symlinked installs, configured host roots, and project-scoped installs. Its version rule also gave no way to rank a copy found through a link. The roles now search `$CLAUDE_CONFIG_DIR` or `$CODEX_HOME` and the target project's skill directory, follow symlinks, read manifests from real paths, compare versions numerically, and rank unversioned copies last. A script following the revised Claude rule picked a linked `0.10.0` checkout over a cached `0.1.0` copy in two fixtures, one with a custom `CLAUDE_CONFIG_DIR` and one with a project-scoped link. On this host it again picked the in-place checkout. Plain `find` returned nothing for a symlinked skill directory; `find -L` found it. The Codex rule and a live z-agent launch without a path remain unexercised.

## pstack 0.15.23: deep-dig signal — 2026-10-13 {#pstack-0-15-23-signal}

Adapted [upstream PR #604](https://github.com/cursor/plugins/pull/604) at merge `36cecbf2b5089b275254d59cb4612d6f96f00fbd`, starting from main `caf7a1f`, as the bottom layer of the [pstack 0.15.23 stack](provenance.md#pstack-0-15-23). fix-root-causes now proposes a cheap, always-on signal when the deciding fact took a deep dig; the principles reference example matches. Manifests declare `0.6.3`.

Checks ran on this macOS host in a clean detached worktree of the layer commit, with the main checkout's `node_modules` linked: structural validation reported 52 skills and zero problems; all 15 Node tests and 120 Python tests passed; `git diff --check` passed. These are static checks. No native host session exercised the new rule during a live debugging task.

## z-agent hub path — 2026-10-12 {#z-agent-hub-path}

Selectively adapted [upstream PR #577](https://github.com/cursor/plugins/pull/577) at merge `364a77eb358f16292410a7295fd8d103fb7dd40e`, starting from main `17b2916`. z-mode leaf links were already relative to its `SKILL.md`, so only the hub path applied: no brief told a spawned z-agent where that file lives. The delegation contract now requires any brief for a child that should follow z-mode (z-agent, fallback agents, Herdr and Hermes workers) to give that file's absolute real path. The parent derives it from the contract's own location, so it works when z-mode is not loaded. A worker on another machine gets that machine's path, or is told to resolve it locally. Both native z-agent roles read z-mode from the given path. When the path is missing, relative, or unreadable, they locate the installed copy and report the bad path; if no copy is found, they stop.

Validation: structural validation (52 skills, zero problems), 15 Node tests, and 120 Python unit tests pass. These are static checks. A read-only review agent given the absolute path found z-mode and its relative links without searching, but that run used the previous role body. The missing-path fallback and remote Herdr resolution were not exercised live.

## Verification skill readiness — 2026-10-12 {#verification-skill-readiness}

Selectively adapted [upstream PR #573](https://github.com/cursor/plugins/pull/573) at `8dd98e90937149ca1b8dba7103d45dce5003676d`, starting from main `7497a21`. The generator now requires usable state, with stateful targets completing required migrations and seed data from empty isolated state, reports missing seed prerequisites without weakening journeys, and discloses setup gaps when proof uses a stand-in. The workflow reference reflects these limits. Shared native manifests advance to `0.6.1` for this compatible fix; native paths, frontmatter, explicit invocation metadata, helper portability, and the retained MIT license remain intact.

Checks on this macOS host (Node 26.11.1, Homebrew uv 0.13.0):

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the VitePress build, reference anchors, license notices, and isolated installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 120 tests passed, including native hooks, packaging, and bundled helpers.
- `uv run scripts/package_plugin.py`: all 183 tracked packaged resources matched the working tree byte for byte, and the packaged manifest declared `0.6.1`. The generator's frontmatter and the license matched base main exactly.
- `git diff --check`: passed.

Commands used Homebrew uv and a PATH preferring Homebrew tools after the mise shim returned a sandbox permission error. Installer fixtures stayed isolated from personal configuration; packaging wrote ignored `dist/zstack` only. These are structural, documentation, packaging, and regression results. No fresh native host generated and drove an application with the revised instructions; model adherence, empty-data startup, and real-target setup remain behaviorally unverified. No personal installation, merge, or deployment was performed.

The independent oracle review found one provenance ambiguity: the new attribution paragraph interrupted an older commit's PR-workflow attribution. Moving it below that paragraph addressed the finding. No other actionable findings were reported. Final structural, documentation-build, and whitespace rechecks passed after this repair and validation record.

### PR #33 review repairs

Assessed all four review threads on `b40f09f`; both thread and comment pagination were complete. Scoped empty-state initialization to stateful targets, with data directories required only where applicable, while retaining usable readiness for every surface. Clarified that missing seed prerequisites belong in the feature's Gotchas and kept obligation wording in the workflow reference. Provenance explains the compatible-fix version: these changes repair existing real-user-path and honest-proof requirements rather than adding a capability, unlike ketchup's visual guidance.

The request to mark an entire stand-in proof unverified was not adopted. The pinned upstream diff explicitly leaves the uncovered setup steps unverified, preserving evidence for behavior actually exercised in the stand-in; it does not claim that the real target was verified. The existing generator and workflow reference retain that distinction.

On this macOS host, structural validation again reported 52 skills and zero problems; all 15 Node tests and 120 Python tests passed. Rebuilt packaging again matched all 183 tracked resources byte for byte with manifest `0.6.1`. Final documentation and whitespace rechecks passed after adding this record. These checks do not prove native model adherence or startup on a real target; no wording-matching tests were added.

## Ketchup decision visuals — 2026-10-12 {#ketchup-decision-visuals}

Selectively adapted pstack 0.15.18's ketchup update at `ea32d9562a1c9f077d7cdd3be53d07383eb18866` and HumanLayer show-me at `653b6411c1f70c275a18e37673b042ff99f67ceb`. The isolated macOS worktree starts at main `1e363c0f32512cf53db796ddd87eaef9bb95aacf`; no later pstack changes are included. The bundled reference and full HumanLayer MIT notice preserve portable discovery without a separate installation. Existing explicit invocation and read-only catch-up policies remain intact. Review repairs below advance the shared plugin version to `0.6.0` for the new behavior.

Initial checks on this MacBook (Darwin arm64, Node 26.11.1, uv 0.13.0), before the PR review repairs:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the VitePress build, full HumanLayer notice in published output, and both linked-host installers accessing the reference, notice, and policy from temporary configuration roots.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 120 tests passed. The added packaging regression used a disposable Git repository and verified ketchup's entrypoint, visual reference, HumanLayer notice, Codex policy, and retained pstack license byte for byte.
- `uv run --with mypy --with rich --with pyyaml --with types-pyyaml mypy`: no issues in 27 source files.
- The documented `ty` bundled-helper check passed.
- `uv run scripts/package_plugin.py`: packaged 52 skills with manifest `0.5.2`; every tracked packaged resource matched the worktree byte for byte, including the visual reference, HumanLayer notice, invocation policy, hooks, and original pstack license.
- Ruff lint and formatting checks passed for the changed Python regression test. `git diff --check` passed.

Repository-wide Ruff 0.17.0 reported five findings, reproduced identically on an untouched archive of base main `1e363c0`: UP017 in `hooks/xray.py`, `skills/z-mode/scripts/orch/store.py`, and `skills/z-mode/scripts/watch-pr/policy.py`; I001 and RUF100 in `scripts/validate.py`. No new lint findings were introduced; the baseline findings remain outside this change.

Initial dependency fetches failed on sandboxed DNS; the same checks passed after allowing dependency access. Caches and installer fixtures stayed under temporary directories, and the lockfile was unchanged. A disconnection removed the first temporary worktree before validation; the surviving task branch was recreated at the same base, and the prepared changes restored before these checks. The primary checkout was not edited.

A manual synthetic catch-up walkthrough covered an older unresolved label choice, a user-role worker notification, absent screenshots and measurements, unverified acceptance/current-head checks, and unavailable Mermaid rendering. The constructed reply used a current/proposed Markdown table, retained unknowns and the missing-capture disclosure, and took no action. This was an implementing-agent prompt walkthrough, not an independent or native-host behavior test.

These results establish local structure, distribution, rendered documentation, and existing regressions. No fresh Codex, Claude Code, or Hermes session invoked ketchup; live capture display, model adherence, PR/CI catch-up, and running-agent scenarios remain untested. No personal installation, merge, or deployment was performed.

### PR #32 review repairs — 2026-10-12

Assessed all five review threads on head `0c60853`: two identified the same version-policy issue, and three identified documentation gaps. Restored the README's preceding-message boundary, qualified comparisons in the guide and workflow reference by available evidence and rendering, and retained a decision summary with a disclosed gap when a useful visual is unavailable. Advanced all three native manifests to `0.6.0` because the visual guidance adds packaged behavior under the repository's minor-version policy.

On this macOS host, final structural validation passed with 52 skills and zero problems; all 15 Node tests and 120 Python tests passed, including the existing minor-bump, manifest-drift, installer, docs-build, license, and packaging regressions. The rebuilt plugin's 183 tracked resources matched the worktree byte for byte, and its manifest declared `0.6.0`. Whitespace checks passed. The prose corrections were reviewed against ketchup's existing fallback; no brittle tests matching the rewritten sentences were added. Final documentation rechecks include this repair record. Earlier native-host behavior limits and the five unchanged baseline lint findings remain.

## Selective pstack 0.15.16 prompt cleanup — 2026-10-11 {#pstack-0-15-16-cleanup}

Reviewed the pinned upstream diff at `00b14f1df36b32a8dd1529324a3a459f6563b127` and adapted 28 corresponding Markdown files in an isolated macOS worktree based on `e0e57f8` (main after ketchup PR #30). [Provenance](provenance.md#pstack-0-15-16-cleanup) records adopted and skipped areas. All skill frontmatter and invocation metadata remain unchanged; native plugin versions advance together to `0.5.1`.

Across only the 28 changed files under `skills/`, after the PR #31 review repairs, words decrease from 17,968 to 16,545 (1,423 fewer, 7.9%) and bytes from 114,965 to 106,228 (8,737 fewer, 7.6%). Counts include frontmatter. The selection is `git diff --name-only e0e57f8 HEAD -- skills` at this PR's head; compare each file's `git show e0e57f8:<path>` contents with the adaptation contents using `wc -w` and byte lengths. Provenance, validation documentation, and manifests are excluded. These are source-size measurements, not token, latency, cost, or model-adherence results.

Checks on this host:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the actual VitePress build, rendered reference anchors, license notices, and isolated linked-host installer fixtures.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 119 tests passed, including bundled Python helpers, native hooks, registration, packaging, and invocation policy.
- The documented `ty` helper check passed. Project-wide `mypy` passed for 27 source files.
- `uv run scripts/package_plugin.py`: packaged 52 skills and native manifest `0.5.1`. Compared every tracked packaged resource byte for byte with the worktree, including edited prompts, sibling references, hooks, and the unchanged MIT license. Compared changed skill frontmatter against main; all matched. Packaging writes only ignored `dist/zstack`, without refreshing installed plugins.
- `git diff --check`: passed.

Ruff 0.17.0 (`uv run --with ruff ruff check --no-cache --output-format json .`) exits 1 with five findings, all reproduced identically on untouched main: UP017 in `hooks/xray.py`, `skills/z-mode/scripts/orch/store.py`, and `skills/z-mode/scripts/watch-pr/policy.py`; I001 and RUF100 in `scripts/validate.py`. This wording port changes no Python source and leaves those baseline issues outside its scope.

Dependency caches and installer fixtures were isolated under temporary directories. Initial sandboxed uv calls could not resolve PyPI; the suites passed with approved dependency access, Homebrew uv, and a PATH that avoids the restricted mise shim. Locked pnpm dependencies were installed only in this worktree. No personal configuration or globally installed skills changed.

These are structural, rendered-documentation, packaging, and regression results. No fresh Codex, Claude Code, or Hermes session exercised the edited prompts, and no reflection panel or live Datadog/Sentry investigation ran. Semantic preservation was reviewed against the local instructions and upstream diff; model adherence remains behaviorally unverified. The final docs checks also cover this record and its provenance links.

### PR #31 review repairs

Checked all seven review threads against head `6b4339c` and verified the remote and local heads matched before editing. Retained literal expected values and meaningful empty-result assertions; the weak-coverage list no longer treats an assertion method as a verdict. The type example now supplies `{ completedAt: Date | null }` as a non-optional single source. Clarified architect's named skill, the Inferred tier's referent, and within-source link following. Restored the quotation qualifier to match the accurate-paraphrase output option. Seer analyses still supply hypotheses rather than authoritative evidence.

On this macOS host, bounded Node assertions confirmed that an empty-result equality check and a zero-length check reject `undefined`. The nullable completion predicate returned false for `null` and true for a Date; `undefined !== null` reproduced the omitted-field bug. This verifies JavaScript examples with Node's assertion library, not Jest/Vitest execution or native agent adherence to the prose.

After the skill fixes, structural validation again reported 52 skills and zero problems; all 15 Node tests and all 119 Python tests passed; packaging again matched every tracked resource byte for byte with 52 skills and manifest `0.5.1`. The final documentation and whitespace rechecks passed after updating this record, provenance, and the size measurements above. Initial sandboxed runs failed on PyPI DNS, including one Node installer fixture; approved dependency-access reruns passed. No executable source, invocation metadata, personal configuration, or installed skills changed. The unmerged PR retains version `0.5.1`; the five previously reproduced Ruff baseline issues and fresh-host behavior limits remain.

## Ketchup skill — 2026-10-11

Adapted the pinned pstack ketchup source at `978ca6e9c0e012047cd5058b8e829240336e704e` in an isolated worktree on macOS. The final checks below use the ketchup branch based on `main`, excluding the unrelated Herdr board plugin. The port preserves explicit-only invocation, the preceding human-message boundary, read-only inspection, older unresolved decisions, and decision summaries. Shared discovery supplies registration for Codex, Claude Code, and Hermes; the native plugin versions advance together to `0.5.0` under the repository's new-skill versioning policy.

Checks against the implementation:

- `uv run scripts/validate.py`: 52 skills, zero structural problems.
- `node --test scripts/*.test.mjs`: all 15 tests passed, including the VitePress build, rendered reference anchors, license notices, and isolated ketchup link installation/removal for both linked hosts.
- `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`: all 119 tests passed, including explicit invocation policy and Hermes registration from another working directory.
- A disposable Git repository containing copies of the current plugin resources exercised `scripts/package_plugin.py`: all 52 skills were packaged, ketchup instructions and policy matched byte for byte, its sibling references resolved, the manifest declared `0.5.0`, and the MIT license was preserved. No staging, commits, or installation in the real repository or personal configuration were needed.
- `git diff --check`: passed. The original `herdr-plugin` checkout remained clean and on its original branch.

Tool caches and installer fixtures were isolated under temporary directories. The final Node and Python suites passed after allowing dependency access; initial sandboxed attempts encountered blocked PyPI DNS. The generic skill-creator `quick_validate.py` was also tried; it rejects `disable-model-invocation` because its allowed-field list lacks the shared Claude Code flag. The repository validator accepts that required field; the flag was retained rather than weakening invocation policy.

These are local structural, packaging, registration, and installer results. No fresh native host session invoked ketchup, and no live PR/CI or running-agent catch-up scenario was exercised. Model handling of partial history, notification boundaries, stale checks, and decision recommendations remains behaviorally unverified. No global skills were changed.

### PR #30 Codex invocation documentation correction

The long-work guide now distinguishes `$ketchup` for linked Codex skills from selecting `zstack:ketchup` through the native Codex plugin's skill picker, matching the host setup and workflow reference. On macOS, `uv run scripts/validate.py` reported 52 skills and zero structural problems; `node --test scripts/docs.test.mjs` passed all four documentation tests, including the VitePress build; `git diff --check` passed. These are documentation and structural checks; no live native-host invocation was exercised.

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
