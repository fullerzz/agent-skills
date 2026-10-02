# Validation

## Python script migration, 2026-10-01

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
cd skills/poteto-mode/scripts
bun install --frozen-lockfile
bun run test
bun run typecheck
```

| Check | Observed result |
| --- | --- |
| Shared metadata, identifiers, native definitions, explicit-only mappings, local references, supported entrypoints, active retired host APIs | 46 skills; zero structural problems. |
| Installer and helper behavior | Six tests pass after the implementation review below. Preview has no writes; both-host collisions preflight; reruns update unchanged owned copies; user edits and foreign links survive removal; interrupted copy updates reconcile. |
| Installed resources in a separate target Git repository | Paths contain spaces. Resource links resolve to this library; audit reports the target root. Clean unknown history stays review-required; untracked work is preserved. TSV logger sanitizes field separators and formula prefixes. |
| Task-sized plan contract | Valid small plan accepted; missing phase verification rejected. |
| Existing Bun tools | Frozen install succeeds; 52 tests pass, 206 assertions; strict typecheck passes. |
| Whitespace | Structural validator covers untracked Markdown; git diff --check passes. |

These checks leave no personal installation. Temporary fixtures own all installer mutations. The installer does not change model, permission, or trust settings.

## Native behavior

The documented project installer was applied to a separate temporary Git repository named `target repo` beneath a directory containing spaces. Its real module was `export function add(a,b){return a+b;}`, with a license comment and a redundant narration comment. Prompts required local scoped work and forbade external actions.

| Scenario | Observed result |
| --- | --- |
| Codex discovery | Native app-server skills/list returned all 46 repository skills enabled, real paths in this checkout, and no loader errors. Temporary native config disabled conflicting personal sources and trusted only the fixture. |
| Claude discovery and explicit mode invocation | Native initialization listed both named roles and explicit commands. The run read this checkout's installed poteto-mode, host contract, and investigation instructions. |
| Both native roles in both hosts | poteto-agent investigated the real module; comment-sicko kept the legal comment and reported the redundant comment without editing. Both reached terminal results. No provider diversity was claimed. |
| Missing execution permission | Claude's restricted review inferred the return value from source and reported that denied Node execution prevented runtime proof. It did not claim the command passed. |
| Codex handoff/resume | A named persistent parent session resumed and synthesized its two completed native child results. Child rollout metadata identified the requested roles and fixture cwd; terminal receipts confirmed completion. |
| Explicit-only selection sample | A natural-language Codex question about calc.mjs read the product source directly without loading the explicit-only how or poteto-mode skills. This is one observed non-selection sample, separate from the explicit-mode runs. |
| Direct fix through mode router | Codex read the mode and bug-fix playbook, changed only greeting.mjs from helo to hello, and exercised the real function. The assertion failed before and passed after; no delegation, commit, or publication. |

Native smoke tests used bounded CLI print/exec runs with JSON output. For a reproduction, install into a fresh small Git fixture, start a new host session, select poteto-mode explicitly, and ask for a read-only investigation by poteto-agent plus a reporting-only comment-sicko review. Wait for terminal results and inspect file contents and actual command exits. Follow with a one-file fix and a saved-session resume. Use native settings to resolve duplicate skill sources rather than changing the user's existing installation.

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

## Independent implementation review, 2026-10-01

Reviewed the committed implementation against the approved plan, rather than treating the earlier check results as proof. Coverage included the installer and its ownership transitions, structural and plan validators, worktree audit, both native roles, all 23 playbooks, the core investigation/design/delegation skills and reference prompts, history/digest handling, verification generation, and the watcher/orchestration entrypoints and callers. This was a single-reviewer implementation review, not an additional oracle panel or an exhaustive upstream comparison; the copied upstream commit remains unknown.

### Findings resolved

| Finding | Correction and evidence |
| --- | --- |
| Personal Claude installation ignored `CLAUDE_CONFIG_DIR`, so an alternate native profile did not receive the skills or agents. | Installer now uses the configured native root for Claude skills, agents, and receipts. A regression reproduced the missing destination before the fix. It now checks installation/removal and that explicit `--home`/`--project` remain isolated. Codex skill discovery remains separate from `CODEX_HOME`. The native directory override is documented in [Claude's environment reference](https://code.claude.com/docs/en/env-vars#variables). |
| Plan validation accepted blank phase values because `\\s*` consumed the newline and matched the next bullet as content. | Restrict whitespace after the colon to spaces/tabs. The regression failed before the fix and now rejects empty Depends on, Files, Acceptance, and Verification values. |
| Reflection reviewers and synthesis advised tuning missed triggers without respecting explicit-only invocation. | All four reference prompts now require reading invocation metadata and treat ordinary non-selection of explicit-only skills as expected. This is an instruction review correction; an end-to-end reflection panel was not run. |
| The standalone proof principle and decision-trail skill conditioned commits on task size without expressly requiring authorization. | Both now require commit authority from the user's request. No commit was made during this review. |
| Plan status denied the existing implementation commit and still described native compatibility as untested. | Updated the status and phase-6 wording while retaining representative-coverage limits. |

The audit required no behavior change: added checks demonstrate that ignored files in a detached worktree, locked worktrees, and missing/prunable worktrees remain held. Installer checks also now cover restoration of a missing owned copy and preservation of a foreign dangling link. Concurrency and arbitrary process termination at every write boundary remain outside the tested contract.

### New native observations

Versions were rechecked: Codex CLI 0.160.0, Claude Code 2.1.287, Node 24.21.0, Bun 1.4.2. The fresh fixture was `/private/tmp/pstack review ZfE8TP/target repo`; preview and both-host project installation succeeded. Product `calc.mjs` remained unchanged. Raw logs are retained only in temporary task directories and are not committed.

| Scenario | Observed result and limit |
| --- | --- |
| Claude clean profile | A new empty `CLAUDE_CONFIG_DIR`, project-only settings, and strict MCP configuration exposed all 46 library skills and both named roles alongside native built-ins. Authentication then returned `Not logged in · Please run /login`. No credentials were copied and no personal configuration changed. Clean authenticated execution is still unproven. |
| Claude non-selection | A bounded ordinary question used Read on `calc.mjs` only; no skill invocation or skill source reads appeared. One sample with Read available, not a universal selection guarantee. |
| Claude companion composition | A direct `/poteto-mode` prompt read the project-linked how companion and minimize-reader-load principle. Both real paths resolve into this checkout. Read and Skill were the only tools available; product files were unchanged. A separate model-side `Skill(poteto-mode)` attempt was rejected for `disable-model-invocation`; that attempt did not execute the mode and is not counted as successful composition. |
| Codex generated-skill execution | Directly invoked the earlier canonical verify-calc. Tool output confirmed doctor, drive, post-drive doctor, and cleanup exits of 0 from `/private/tmp`. Evidence recorded real `add(2,3) === 5`, an unchanged module hash, and retained proof after scratch removal. |
| Codex authoring from the reviewed source | After excluding the personal-copy sample, an exact project-linked invocation read this checkout's generator and native-host contract. It created `skills/verify-calc-reviewed`, a feature map, and an executable helper. Doctor, drive (four public addition cases), and cleanup each exited 0 from `/private/tmp`. Parsed JSON artifacts independently confirmed the invocation cwd, exits, retained evidence, and preserved product/previous-fixture hashes. Registration was deliberately left pending. This is a bounded source-pinned authoring result, not proof that an ambiguous skill name selects the project copy. |
| Claude scoped digest | Invoked recall with a supplied fixture-only digest and transcript access unavailable. It read this checkout's history contract, checked local Git/source state, labeled its output digest-based, and did not scan other chats. This proves the digest path, not a local transcript parser or the reflect/automate-me workflows. |
| Claude native resume | The first sandboxed sample returned a session ID but resuming it reported no conversation found. A fresh scoped sample run through the approved outer execution path persisted successfully; `claude -p --resume <that-id>` with tools disabled recalled the inspected function, pending work, and unverified digest basis. Native resume works when persistence is available; the sandboxed result is not evidence of a general host defect. |

Codex could not initialize its app-server inside the outer sandbox. Approved outer execution retained Codex's own workspace-write sandbox. No authentication link was recreated. One authoring sample selected a conflicting personal generator and was excluded as validation of this checkout; source identity must be checked even when the requested skill name matches.

The six Node tests, structural check (46 skills, zero problems), frozen Bun install, 52 existing Bun tests (206 assertions), strict typecheck, and whitespace checks passed. These do not certify every host behavior or validator field. Publication, messages, trackers, merges, deployment, provider diversity, and unattended execution remain deferred, not failed acceptance tests.

Remaining clean-profile action: the user can authenticate the isolated Claude profile through its native login flow, then rerun the same bounded source/role checks. This review did not move or copy credentials to make that test pass.

## Watcher review remediation, 2026-10-01

Addressed both findings from the subsequent delegated review. Review-thread reads now follow GraphQL cursors before filtering resolved threads and calculating Bugbot pass counts; missing pagination cursors fail closed. The regression covers 100 resolved threads followed by an unresolved thread on page two, including pass counts across pages.

The shared polling loop caps normal and retry sleeps to the remaining deadline and returns the appropriate timeout without another query after that sleep. Injected-clock regressions cover simple and queued modes, including query time consumed before sleeping. A 10-second timeout with a 3600-second interval and a 2-second query sleeps only 8 seconds. This does not cancel an already-running GitHub command.

Validation: 58 bundled Bun tests (226 assertions), strict typecheck, structural validation, six Node tests, and whitespace checks pass. These are deterministic local checks; no live GitHub calls or external mutations were used for remediation.
