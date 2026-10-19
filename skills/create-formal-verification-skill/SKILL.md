---
name: create-formal-verification-skill
description: "Generate a reusable project-local skill for model checking or proving code-linked properties. Use explicitly for /create-formal-verification-skill, model-checking a race, or proving an invariant; UI and service journey checks belong to create-verification-skill."
disable-model-invocation: true
---

# Create a formal verification skill

Choose a consequential property within the requested area, verify it within a stated scope, and leave a project-local skill that another agent can rerun after a relevant change. Formal verification covers a model, bounded inputs, or a theorem under assumptions; it does not establish whole-system correctness.

Resolve resources from the real loaded skill location, independently of the target cwd. Follow the [native host contract](../z-mode/references/native-hosts.md). This workflow creates verification artifacts and isolated broken variants; it does not authorize product fixes, global installation, commits, publication, messages, or tracker writes.

## Choose the property and tool

Start at the user's named code or bug. Otherwise identify a promise whose violation would harm users and whose failure cases are hard to reach with ordinary tests. Read the actual callers and state transitions before choosing a target. State the property and the harm in plain language; keep the initial scope small enough to rerun routinely.

Choose the least costly tool that answers the question. For event-order questions, default to TLA+ to model the design regardless of the implementation language; prefer existing project tooling where it fits. A verifier operating on source can check memory safety, arithmetic, or data-structure invariants; an unbounded claim may need a proof assistant. If no verifier supports the implementation language, disclose that limitation and test the real code with generated inputs, not a handwritten model of the function. Label this fallback as testing, not formal proof, and record the input scope and any random seed so the evidence can be reproduced. Record why the tool fits, its reproducible version, the exact command, prerequisites, and a run budget. Do not install tools globally without authorization.

For each property, record:

- The guarded source paths and symbols, their relevant callers, and the model or proof elements corresponding to them.
- Assumptions, input and state-space bounds, excluded behaviors, and any fairness or environment assumptions. Every modeled atomic step must match an actual indivisible operation or justified synchronization boundary in the code; do not hide interleavings by merging separate operations.
- What a pass establishes and what remains unverified, including the trust placed in handwritten models, tool implementations, and external systems.
- How changes to guarded code invalidate the correspondence review. Use a reproducible source snapshot, digest, or equivalent drift check; a changed digest means review required, not a proved bug. Refresh it only after reviewing code/model correspondence.

If current code violates the property, retain the finding and explain the counterexample as steps using the code's names. Do not weaken a property, narrow a bound, add an assumption, or alter the model just to obtain a pass. Correct demonstrated modeling errors with an explanation and rerun affected checks. Do not fix product code unless requested.

## Generate the reusable skill

Honor a requested source location. Otherwise use `verify-formal-<area>/SKILL.md` in the selected host's project discovery directory: `.agents/skills/` for Codex or `.claude/skills/` for Claude Code. For Hermes, or when the host's project discovery contract is unavailable, use an ordinary project source folder such as `verification/skills/verify-formal-<area>/` and report registration pending; do not guess another host's discovery path or install globally. The same fallback applies when permissions block discovery-directory writes.

Before writing, inspect the canonical destination, including existing files and symlinks. Update an existing skill only when the request targets that same formal-verification skill. Otherwise preserve it and choose an unused descriptive name; if the user requires an occupied exact path, report the collision before writing. Never merge into or replace a runtime feature-map skill. For both Codex and Claude Code, keep one canonical folder and link it into the other directory only after checking for collisions; preserve existing files and links.

Use valid YAML frontmatter with a matching kebab-case name and a description naming the guarded area and relevant changes. Preserve an existing skill's invocation policy. For a new skill, retain this workflow's explicit-only policy with `disable-model-invocation: true` and `agents/openai.yaml` containing `policy.allow_implicit_invocation: false`, unless the user requests otherwise.

Write real commands, paths, and properties with no placeholders. Include:

- **Scope and correspondence:** the property records above, a way to detect relevant source changes, and instructions to review correspondence before accepting a new result. For handwritten models, explicitly distinguish the model's result from evidence about the implementation.
- **Run:** prerequisites, pinned or otherwise reproducible tool version, one rerun command, expected successful output, and interpretation of counterexamples, drift, timeouts, and tool failures. Report inconclusive runs as inconclusive; successful process exit alone is not proof.
- **Evidence and findings:** durable locations for source identity, commands, versions, outputs, counterexamples, and mutation evidence. Explain failures in product terms and preserve verification limits beside the result.
- **Maintenance:** how to revalidate correspondence and rerun relevant checks after intended changes, without silently weakening claims or approving source changes by updating a digest alone.
- **Cleanup:** remove only scratch state and processes owned by the run; retain evidence. Name how interrupted or failed runs are cleaned up.

Bundle models, proofs, and helpers only where they make the check reusable. Derive a quoted absolute `VERIFY_DIR` from the real loaded entrypoint. Resolve bundled assets from that directory and source files from an explicit target-repository argument; never assume the skill is beside a checkout. Helpers must be invocable from another cwd and document their commands. Use `uv` for Python helpers.

## Demonstrate detection in isolation

Run the generated instructions against the selected source snapshot and retain a baseline result per property. Preserve existing uncommitted work in that snapshot; a worktree based only on HEAD does not include it. Create a disposable copy or worktree for deliberate breakage, with isolated data and no production side effects. Never introduce mutations into the user's checkout or reset their work.

For every claimed property, introduce a targeted broken variant of the real guarded code, such as removing a guard or splitting a synchronized operation. Run the generated workflow unchanged and retain the mutation diff, command, result, and property-specific evidence. A syntax error, missing dependency, timeout, unchanged pre-existing failure, or generic changed-source warning does not demonstrate detection of the violated property.

With a handwritten model, first show that a real code mutation triggers the correspondence review; then carry that semantic change into the model and show the relevant property failing. Record the manual translation and its limits. A model-only mutation proves only that the model's check can fail; neither it nor a drift alarm establishes automatic detection of an implementation regression. Claim implementation-level detection only when the verification actually establishes that connection.

If the baseline already fails, retain its finding and distinguish the additional mutation's counterexample from the baseline failure. If the tool stops at the original failure, isolate the mutation check without removing the original finding or weakening the property. If detection cannot be distinguished, mark that property's mutation validation incomplete.

Keep the intended broken behavior fixed during validation. Repair a faulty harness or correspondence procedure rather than changing the mutation to an easier case merely to make it detectable. Afterward discard only owned scratch changes, rerun the original snapshot, and confirm the baseline result is restored. Retain all evidence outside scratch cleanup. Exercise bundled helpers through their absolute resource paths from a different cwd with the target supplied explicitly.

## Hand off

Report the generated skill path, discovery status, property, tool choice, exact rerun command, findings, assumptions, bounds, and exclusions. Distinguish automated checks from manual correspondence review and model evidence from implementation evidence. Give each property's baseline and mutation outcome. Missing tools, timeouts, inconclusive results, undetected mutations, or an unexecuted workflow leave the affected verification draft or blocked; do not present it as validated. Existing confirmed findings can remain in a validated workflow when mutation detection is independently demonstrated and the unchanged baseline is restored.

This is separate from the runtime verification skill's feature-map maintenance loop; maintain the properties and correspondence records with the guarded code.
