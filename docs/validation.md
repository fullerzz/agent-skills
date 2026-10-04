---
outline: [2, 3]
---

# Validation

Historical observations below retain the names used during those runs (`pstack`, `poteto-mode`, and `poteto-agent`). Current equivalents are `zstack`, `z-mode`, and `z-agent`; those earlier observations do not establish live behavior under the new names.

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
