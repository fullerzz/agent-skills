# Validation

Checked on 2026-10-01 using Codex CLI 0.160.0, Claude Code 2.1.287, Node 24.21.0, and Bun 1.4.2. The installer uses Node 20+ APIs; older host versions have not been tested.

## Repeatable local checks

Run from this checkout:

```sh
bun scripts/validate.mjs
node --test scripts/*.test.mjs
cd skills/poteto-mode/scripts
bun install --frozen-lockfile
bun run test
bun run typecheck
```

| Check | Observed result |
| --- | --- |
| Shared metadata, identifiers, native definitions, explicit-only mappings, local references, supported entrypoints, active retired host APIs | 46 skills; zero structural problems. |
| Installer and helper behavior | Five tests pass. Preview has no writes; both-host collisions preflight; reruns update unchanged owned copies; user edits and foreign links survive removal; interrupted copy updates reconcile. |
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
