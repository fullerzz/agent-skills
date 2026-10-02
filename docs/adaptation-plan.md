# Adapt pstack for Codex and Claude Code

Status: implementation committed as `270ef2348dc92b993297fff8e9c465c3fb435ad5` after scope approval and plan-level oracle review. Both oracle findings are addressed in code and focused checks. Representative native scenarios, subsequent implementation review, and review corrections are recorded in [validation](validation.md). No personal installation, push, or publication was performed.

Make this repository a personal skill library that works in Codex and Claude Code without Cursor. Keep the useful engineering workflows, principles, references, and scripts. Replace assumptions about the host rather than maintaining two copies of every skill.

## Decisions already made

- Support Codex and Claude Code only. Retire Cursor packaging and instructions.
- Use each host's native agents first. Cross-provider orchestration is a later project.
- Keep `skills/` as the canonical source. Separate host-specific agent definitions and metadata where their formats differ.
- Implementation was authorized after plan review. Validate through temporary installations; personal installation and publication remain separate actions.

## Baseline reviewed before implementation

The copied `.cursor-plugin/plugin.json` identifies pstack version `0.15.5`. The copied repository contained 47 top-level skills, including 23 principle skills; 23 poteto-mode playbooks; two agent definitions; a ten-part guide; supporting scripts; and a dormant Benny automation pack with three additional skills.

The original README presented Lauren Tan's personal introduction, Cursor installation, Cursor model routing, and Cursor automations. Preserve the upstream attribution, but make the introduction and usage instructions describe this repository.

Concrete compatibility problems found during review:

| Location | Current assumption | Required change and reason |
| --- | --- | --- |
| `.cursor-plugin/plugin.json` | Cursor discovers the plugin and its components. | Replace the installation path. Merely copying the skills into this repository does not register them in either target host. |
| `skills/setup-pstack/SKILL.md` | Writes `~/.cursor/rules/pstack-models.mdc`; encodes effort in Cursor model slugs. | Use native model and effort settings. Neither host should be given invented Cursor slugs or have unrelated user configuration overwritten. |
| `skills/poteto-mode/SKILL.md` | Cursor mode metadata, `Task` arguments, companion plugins, automatic PR creation, and broad external-action authorization. | Keep routing intent; replace host mechanics and align actions with the user's actual task and authorization. |
| `how`, `why`, `architect`, `arena`, `swarm`, `interrogate`, `reflect` | Named Cursor models and agent arguments; some assume cloud workers or model-family diversity. | Use available native agents, bounded concurrency, and actual model identities. Independent runs on one model are useful but are not cross-provider review. |
| `agents/` | Cursor YAML fields and agent names such as `Comment Sicko`. | Supply native definitions and valid identifiers; preserve the reviewer’s scoped role. |
| `recall`, `automate-me`, `reflect`, session pickup, eval, decision-trail audit | Cursor JSONL locations, schemas, and system-prompt store paths. | Use host-specific, workspace-scoped evidence access or an explicit session digest; do not silently search unrelated chats. |
| Verification generators and playbooks | `.cursor/skills/`, `create-skill`, `deslop`, `control-ui`, and `control-cli`. | Write discoverable skills and use the host's available authoring and verification tools or the project's harness. |
| Multi-phase planning and `scripts/check-plan.mjs` | Every PR requires ten live lanes, screenshots, performance comparisons, and a fixed program template. | Match checks to the actual task; change the validator with the plan contract so it does not force Cursor-scale ceremony. |
| `scripts/worktree-audit.sh` | Cursor transcripts determine recent work; missing evidence can influence a `safe` classification. | Remove the Cursor lookup or replace it with a verified scoped lookup. Unknown history must remain unknown; protect tracked and untracked work. |
| `make-bot-ui` and `automations/benny/` | Cursor routines, secret cards, webhooks, and automation installation. | Exclude from the first supported release. These need an actual replacement runtime, not terminology changes. |

## Proposed structure and installation

Keep the existing `skills/<name>/SKILL.md`, references, playbooks, and scripts. Add small host instructions under `docs/hosts/` and separate native agent definitions under `agents/codex/` and `agents/claude/`.

For the first version, install individual skill-folder symlinks from this checkout into native discovery locations. Support personal installation first, with project installation as an explicit alternative:

| Host | Personal skills | Project skills | Invocation |
| --- | --- | --- | --- |
| Codex | `~/.agents/skills/<name>` | `.agents/skills/<name>` | `$poteto-mode`, `$how`, or skill selection |
| Claude Code | `~/.claude/skills/<name>` | `.claude/skills/<name>` | `/poteto-mode`, `/how` |

Both hosts document support for symlinked skill folders. This allows edits in this repository to remain the source of truth. Codex discovers repository skills under `.agents/skills`; Claude Code uses `.claude/skills`. See [Codex skills](https://learn.chatgpt.com/docs/build-skills) and [Claude Code skills](https://code.claude.com/docs/en/skills).

The installer should show its planned links, refuse collisions with existing skills, and be safe to rerun. Removal should unlink only links it owns. Do not replace an entire user's skills directory, install dormant automations, or change model and permission settings as a side effect of installation.

Use Codex TOML agent definitions and Claude Code Markdown agent definitions. Install the host-specific files from `agents/codex/` or `agents/claude/` into native agent discovery locations; the source directories alone do not register an agent:

| Host | Personal agents | Project agents |
| --- | --- | --- |
| Codex | `~/.codex/agents/<name>.toml` | `.codex/agents/<name>.toml` |
| Claude Code | `~/.claude/agents/<name>.md` | `.claude/agents/<name>.md` |

Include these agent files in the installer's preview, collision checks, rerun handling, and uninstall ownership checks. Verify file-link discovery in both hosts before using links for agents; if a host requires copies, remove only installer-owned copies whose contents have not been changed. Never overwrite an existing agent definition. Their native formats and discovery locations are documented in [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [Claude Code subagents](https://code.claude.com/docs/en/sub-agents). Keep common behavioral instructions referenced from the shared skills where practical.

Resolve bundled scripts and references from the actual installed skill location, independently of the target repository's working directory. Derive absolute script paths from the resolved `SKILL.md` location, quote paths, and keep the target repository as the command's cwd or pass its path explicitly. Do not change into this skills repository to make a relative script command work. Cross-skill references must resolve through installed skill locations, without assuming the target repository contains a `pstack/` checkout.

Plugin distribution can come later. Claude Code plugins use `.claude-plugin/plugin.json` and namespaced skill commands, so a manifest cannot simply be renamed from the Cursor version. See [Claude Code plugin manifest](https://code.claude.com/docs/en/plugins-reference). Local discovery is sufficient for this first personal library.

## Implementation sequence

### 1. Establish identity, provenance, and installation

- Rewrite the README around this repository, two working installation examples, and a short getting-started flow.
- Preserve the MIT license and Lauren Tan's copyright. Record the upstream source and copied manifest version; record an exact source commit only if it can be established.
- Remove the Cursor manifest and obsolete branding assets after checking their references. Keep upstream credit in the README.
- Add the minimal collision-aware installer and host documentation described above, covering both skill folders and native agent files.
- Put repository-maintenance instructions in `AGENTS.md`, including the supplied `xh`, `uv`, `mise`/`brew`, fff, and browser conventions. Use `CLAUDE.md` only if the supported Claude configuration needs an import shim; avoid duplicate instructions. Current [Claude Code memory documentation](https://code.claude.com/docs/en/memory) describes native `AGENTS.md` support and its configuration limits.

Done when both hosts discover a small representative skill from an isolated installation, links resolve to this checkout, and reinstalling does not damage an existing skill.

### 2. Adapt metadata and native agent behavior

- Normalize skill names to their directory identifiers, including `Poteto Mode` to `poteto-mode`. Remove Cursor-only presentation and reminder fields.
- Preserve existing invocation intent. Map Claude's `disable-model-invocation` policy to Codex's `agents/openai.yaml` invocation policy where needed; verify actual loader behavior rather than assuming the fields are equivalent.
- Rewrite `setup-pstack` around native configuration, defaulting to parent-model inheritance. Keep model IDs and reasoning effort separate; never infer entitlement from a fabricated model-name suffix.
- Prefer native configuration over introducing a parallel pstack configuration system. Add role overrides only where a host supports them and an actual workflow needs them.
- Adapt the two agent roles to native formats, with the comment reviewer constrained to reporting. The parent decides and applies accepted edits.
- Replace literal Cursor agent calls in every skill, reference prompt, and playbook with native capability instructions. Handle concurrency and nesting limits explicitly; wait for terminal results and identify missing coverage.
- Remove default cloud placement. Native local agents share local resources; writable workers need exclusive file ownership or isolated worktrees.

Done when the documented clean installation makes both named agent roles discoverable in each host, each host can run a small delegated investigation and a scoped comment review, and results use valid native model settings without assuming Cursor tool fields or cloud VMs exist.

### 3. Port the main router and reusable workflows

- Adapt `poteto-mode` first, then `how`, `why`, `architect`, `arena`, `swarm`, `interrogate`, `teach`, and `blast-radius`.
- Preserve grounding, isolated candidates, independent review, synthesis, and evidence requirements. Replace claims of guaranteed model diversity with the models actually used.
- Let simple work run directly. Keep deliberate fan-out for explicitly selected workflows and tasks that benefit from it; remove universal delegation triggered by every function boundary.
- Replace unavailable companion-skill dependencies with existing host tools or project harnesses. Report a real missing capability when it prevents required proof.
- Keep principle content largely intact. Audit absolute wording for conflicts with task scope, host permissions, and the user's explicit constraints.
- Remove blanket authorization for team chat, tracker changes, and unsolicited PRs. Creating a local artifact, committing, pushing, opening a PR, merging, and deployment remain separate actions governed by the user's request.
- Remove destructive checkout resets as routine recovery. Preserve dirty and concurrent work.
- Make mode persistence an explicit conversation instruction with an opt-out and a resumable handoff, rather than claiming Cursor's `mode` field enforces it.

Done when a read-only question produces an answer without writes, a small fix follows the requested scope, and a review produces findings without applying changes or publishing work.

### 4. Adapt history, verification, and durable evidence

- Port `recall`, `automate-me`, and `reflect` through short host-specific evidence instructions. Inspect only the requested workspace, topic, and time window. Prefer available session exports or native history access; verify any local schema before relying on it.
- Preserve the existing digest fallback in `reflect` and add equivalent fallbacks where appropriate. Label a digest-based review so it is not mistaken for transcript verification.
- Adapt verification-skill generation and maintenance to the chosen host's project discovery path. Generate one canonical skill and link it for both hosts when both are needed.
- Port session pickup, pause, eval, and decision-trail audits. Keep branch, SHA, pending work, evidence paths, and resume commands in a user-owned task directory instead of an assumed Cursor agent store.
- Keep the existing TSV logger. Remove its mandatory cross-family reviewer requirement in native-only runs; report the actual independent reviewer and evidence gaps.
- Reuse existing Bun tools and tests. The orchestration store and PR watcher have useful host-independent code; audit their callers before changing or dropping them. Keep legitimate GitHub reviewer identification, even if a review author's name is `cursor`.
- Fix installed resource paths in script callers, references, and playbooks, including relative `scripts/watch-pr/watch-pr`, `scripts/worktree-audit.sh`, `bun scripts/orch/orch.ts`, and hardcoded `pstack/` prefixes. Preserve the target cwd or pass an explicit target repository so Git-based helpers inspect the user's project rather than this skill library.
- Update worktree-audit evidence handling and the planning validator alongside their documented contracts.

Done when a session can resume from its saved state, history access stays within scope, a generated verification skill loads in its target host, and the existing script checks pass after any necessary edits.

### 5. Port bounded long-running and PR workflows; retire unsupported content

- Adapt babysit and shipping around the existing GitHub CLI and PR watcher. Preserve verification tied to the current head SHA.
- Replace Cursor `/loop`, `/goal`, cloud-sleeper chains, dashboard liveness, and cloud branch arguments with mechanisms actually available in the selected host. If durable background execution is unavailable, save a concrete handoff rather than promise an overnight run.
- Adapt autonomous-run, multi-phase planning, orchestrate, and autopilot playbooks after basic delegation works. Keep explicit done conditions and bounded failure recovery; scale worker counts and validation to the task.
- Rewrite `check-plan.mjs` to enforce the useful plan structure without requiring ten screenshot lanes or performance measurement for unrelated changes.
- Remove `make-bot-ui` from the installable skill set and retire the Benny pack from the supported tree. Record their upstream provenance and the reason in the docs; recover source from upstream when a real replacement is requested.
- Update all guide chapters, examples, links, agent names, and dependency notes. Remove unsupported claims rather than leaving apparently working instructions.

Done when the guide describes only supported behavior, a PR-status request stays read-only unless remediation is requested, and long-running workflows end with either verified completion or a usable handoff.

### 6. Validate the library in both hosts

Use one small structural check plus a few realistic scenarios. Static checks cannot prove that an agent follows a skill.

- Validate frontmatter, unique names, local references, script entrypoints, and host metadata. Flag active Cursor-only paths and APIs while allowing explicit provenance and legitimate external identities.
- Exercise installer reruns, collisions, uninstall ownership, and paths containing spaces in temporary directories for both skills and agent definitions. Preserve any user-modified installed agent copies.
- Run the existing Bun test/typecheck commands for scripts that remain supported; add focused checks only for changed behavior.
- Start isolated Codex and Claude Code sessions with only the intended skills and agent definitions. Test discovery and explicit invocation, routing, delegation completion, scoped read-only review, missing capabilities, session handoff, and a generated verification skill.
- Run an installed workflow from a separate temporary Git repository whose path contains spaces. Verify bundled script and reference resolution, record the repository the helper actually inspects, and assert it is the target repository rather than this skills checkout.
- Check policy behavior separately: existing explicit-only skills stay explicit-only, and reusable principles remain available as intended. Check selected skills through the mode router as well as direct invocation.
- Confirm that a local skill-authoring request does not send messages, file tracker items, push, or open a PR without authorization in that request.
- Record tested CLI versions and any minimum-version requirements demonstrated by the checks. Codex CLI `0.160.0` and Claude Code `2.1.287` have now passed representative native scenarios; see [validation](validation.md) for exact coverage and unresolved limits.

Done when both hosts pass these scenarios, every installed workflow has a supported execution path, and the README's setup steps have been followed successfully from a clean temporary installation.

## Scope to review

Recommended first-release boundary:

- Keep all portable principle and engineering skills, with the changes above.
- Retain `poteto-mode`, `poteto-agent`, and `setup-pstack` names during the port so a bulk rename does not obscure behavioral changes. Personal naming can follow separately.
- Exclude Cursor automations and cross-provider panels. Do not build a replacement automation server, universal model router, or custom agent daemon.
- Use local installation first; defer marketplaces and public plugin packaging until both native workflows pass.
- Implement in the sequence above. Treat phase completion as an evidence checkpoint, not an automatic commit, PR, or merge request.

The user approved this first-release scope and sequence, including the lightweight installation approach and removal of automatic publication and fixed ten-lane ceremony.

## Oracle review resolution

| Finding | Correction | Acceptance evidence |
| --- | --- | --- |
| P2: Agent source directories are outside native discovery paths, but installation covered only skills. | Added native agent destinations and included agent files in preview, collision, rerun, and uninstall handling. | Phase 2 verifies discovery and use of both named agent roles through the documented clean installation; phase 6 checks installer ownership and collisions. |
| P2: Bundled resource paths were unspecified relative to the target working directory. | Added skill-relative resource resolution, target-repository cwd/argument requirements, and removal of hardcoded checkout prefixes. | Phase 6 runs an installed workflow from a separate Git repository with spaces in its path and checks both resource resolution and the repository inspected. |

Both corrections are implemented. Native agents are owned copies, avoiding an assumption about agent-file symlink discovery; modified copies are preserved. Skills remain canonical folder links. Native role runs exercised both hosts. The separate target-repository test resolves installed resources to this checkout while the helper reports the target Git root, including paths containing spaces.

## Implementation checkpoints

| Phase | Local result |
| --- | --- |
| 1 | README, provenance, native host guides, maintenance instructions, and preview-first installer implemented. MIT attribution retained. |
| 2 | Shared metadata normalized; native invocation policy and both host-specific roles installed and exercised in temporary fixtures. |
| 3 | Router, engineering workflows, reference prompts, and conflicting principle wording adapted. Native read-only review and a direct scoped fix exercised. |
| 4 | Scoped history/digest contract, durable handoffs, verification generator, logger resource paths, worktree audit, and plan validator adapted. |
| 5 | All 23 playbooks and ten guide chapters ported. Unsupported automation, manifest, and branding retired. Bun orchestration bookkeeping and PR watcher retained. |
| 6 | Structural validation, five focused checks, 52 existing Bun tests, and typecheck pass. Native discovery, roles, explicit mode routing, permission gaps, and Codex resume exercised. See validation for the generated-skill scenario and limits. |

The acceptance criteria above remain the approved intent, not a claim that every skill and long-running workflow was exhaustively evaluated. Native tests cover representative behavior; live GitHub publication, cross-provider workflows, and unattended execution are outside this implementation.
