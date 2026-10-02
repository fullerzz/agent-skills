---
outline: [2, 3]
---

# Validation

Historical observations below retain the names used during those runs (`pstack`, `poteto-mode`, and `poteto-agent`). Current equivalents are `zstack`, `z-mode`, and `z-agent`; those earlier observations do not establish live behavior under the new names.

## Forced skill replacement <Badge type="info" text="2026-10-02" />

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
