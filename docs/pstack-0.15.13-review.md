# Upstream pstack 0.15.10–0.15.13 review

Reviewed 2026-10-05 against upstream [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack). The selective documentation port below is implemented; the help skill is excluded. See [validation](validation.md) for observed checks and limits.

## Baseline

Before this documentation port, zstack last ported upstream #495 and #496 in `a56cb17`. Four later commits touch pstack:

| Commit | Version | Change |
| --- | --- | --- |
| [4e5b1cf2](https://github.com/cursor/plugins/commit/4e5b1cf2) (#502) | 0.15.10 | Adds the `poteto-help` skill, plus README and guide pointers to it. |
| [00b52d95](https://github.com/cursor/plugins/commit/00b52d95) (#506) | 0.15.11 | Makes `poteto-help` explicit-only (`disable-model-invocation: true`). |
| [807c0310](https://github.com/cursor/plugins/commit/807c0310) (#507) | 0.15.12 | Adds `poteto-help/references/prompting.md` and `references/recipes.md`. |
| [2cbf5850](https://github.com/cursor/plugins/commit/2cbf5850) (#508) | 0.15.13 | Refreshes all ten guide pages. |

## Decision: do not port the help skill

Commits #502, #506, and #507 build a routing skill for newcomers. Skip it:

- Its setup and execution guidance includes Cursor-specific features: Custom Mode via Option+Enter, `/add-plugin`, the `pstack-models.mdc` rule, cloud subagents, `make-bot-ui`, and `cursor-team-kit`.
- Its portable routing table overlaps [the skill catalog](skills.md); prompting and usage guidance can live in the guide without a second routing map.
- The #506 fix needs no port because zstack has no help skill to fix. Shared frontmatter keeps all skills except `setup-zstack` explicit in Claude Code; Codex deliberately permits automatic `how` and `why` selection through native metadata. Preserve both policies.
- zstack is maintained for personal use with no user support, so onboarding routing does not justify its context and maintenance cost.

The prompting guidance in #507 is useful, but it belongs in the guide rather than in a skill.

## Decision: selectively port guide content from #508

Before this port, the local guide (`docs/guide/02`–`05`) omitted `benchmark-checklist`, prototyping, plan sequencing, and trust before unattended work, although the matching skills and playbooks existed locally.

| Upstream content | Local target | Port |
| --- | --- | --- |
| What goes in a prompt: goal, pass/fail done check, requested proof, known facts, real constraints. Leave implementation choices open unless the method is a requirement; ask for a restatement of noisy reports before sharing a theory. | `guide/05-principles-and-recipes.md` | Yes |
| Resolve experimentally answerable design questions with prototypes, then write the plan after the design settles. Preserve early review of scope, dependencies, and authority. | `guide/02-understand-and-design.md` | Yes; no blanket prototype or review requirement |
| `benchmark-checklist` for vetting a measured number. | `guide/03-build-and-verify.md` | Yes; closes a guide discovery gap |
| Inspectable proof, an explicit project verification-skill example, and reproduction against the current baseline. | `guide/03-build-and-verify.md` | Yes; existing harness first, isolated baseline checkout |
| Earn trust before a loop: task done once by hand, agent has your tools and signals, every stage proves its work and can stop the line, repeated failures turned into checks. | `guide/04-long-work.md` | Yes |
| New pitfalls: leading with your theory, accepting an unresolved design, polishing untested assumptions, repeating unchecked work, trusting an unvetted number, correcting the same mistake by hand. | `guide/05` pitfalls | Yes |
| Read-only investigation prompt ("don't change any code yet"). | `guide/05` recipes | Yes; one line per host |
| Worked `correct` example. | `guide/04` code group | Yes; local fixes and independent-incident evidence |
| Cost controls. | `guide/05` | Yes; use z-mode when rigor helps, verified native model/effort settings, and bounded review panels; omit pstack model rules |
| Cursor Projects, cloud subagents, Benny automation pack. | — | No; Cursor-specific or retired here |
| Scheduled daily verification maintenance. | `guide/03` and `guide/04` | Adapt; maintain on drift, choose cadence only on request. Verified, requested native scheduling is compatible with the no-replacement-daemon policy |

## Implementation and validation

1. Updated the four guide pages above with short additions in the existing Claude Code/Codex `code-group` style. Keep unsupported Cursor commands out of `docs/guide/`.
2. Added a [provenance](provenance.md) entry citing `2cbf5850` and `807c0310` as a selective guide port, with the help skill deliberately excluded and no upstream version bump applied.
3. Run `uv run scripts/validate.py`, `node --test scripts/*.test.mjs`, and `uv run --with rich --with pyyaml python -m unittest discover -s scripts -p 'test_*.py'`.
4. Build the VitePress site to confirm links resolve, then record the checks in [validation](validation.md).
