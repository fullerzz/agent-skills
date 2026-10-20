---
name: maintain-formal-verification-skill
description: "Refresh a project's formal checks after covered code changes, distinguish verification drift from product bugs, and retain per-check coverage checkpoints. Use explicitly for /maintain-formal-verification-skill or auditing whether a model still describes the code."
disable-model-invocation: true
---

# Maintain a formal verification skill

A passing check can describe code that no longer exists. Review correspondence before accepting that pass. This workflow maintains project-local model checks, proofs, source verifiers, and explicitly labeled generated-input testing fallbacks; runtime feature maps belong to [maintain-verification-skill](../maintain-verification-skill/SKILL.md).

Follow the [native host contract](../z-mode/references/native-hosts.md). Edit only verification artifacts and their skill: models, harnesses, properties, coverage records, and evidence. Preserve invocation policy, unrelated edits, and product code. Product fixes, global installation, commits, publication, messages, and tracker writes need their own authorization.

## Locate and baseline

Find checks by what they do, not a fixed skill name; follow links to canonical project files. Respect a named target and enumerate the selected checks. If none exists, direct the user to explicitly invoke [create-formal-verification-skill](../create-formal-verification-skill/SKILL.md); do not bypass its invocation policy.

For each check, read its property, covered source paths and symbols, relevant callers, model correspondence, bounds, assumptions, command, tool version, evidence, and last verified commit. A checkpoint records reviewed correspondence, not absence of bugs. Keep checkpoints per check so a runnable check cannot advance a blocked sibling.

If a checkpoint is absent, use the last commit changing that check's verification artifacts as a provisional comparison base and disclose the inference; it is not prior verification evidence. If history is missing or that base cannot be resolved, report the gap and review the current correspondence in full before establishing a new checkpoint.

Record the current source identity, including staged, unstaged, and relevant untracked files. Run each existing check before editing and retain its output. A stale pass proves only the old description; a failure may be drift, a product bug, or a tool failure.

## Review and update

Compare each check's base with the current source, including working-tree changes. Read intervening diffs and commit intent, then trace renamed, moved, or split functions and new callers or writers of guarded state outside the old file list. Classify changes against the actual verification:

- **No effect:** the change does not alter covered behavior.
- **Drift:** the model or harness no longer describes the code's steps, branches, ranges, or synchronization.
- **Intentional promise change:** cite tests, documentation, or other change evidence before revising the property; retain its old and new wording.
- **Possible bug:** the promise remains and changed behavior may violate it.

Update correspondence from the code before rerunning. Match modeled atomic steps to real indivisible operations or justified synchronization boundaries. Never weaken a property, narrow a bound, or add an assumption merely to get a pass. Explain any necessary bound or assumption change and its lost coverage.

## Rerun and challenge

Run the revised checks and interpret their results:

- **Pass:** demonstrate property-specific detection with a deliberate real-code mutation in a disposable copy or worktree containing the evaluated source, including relevant uncommitted changes. Never mutate or reset the user's checkout. Follow the generator's [isolated detection procedure](../create-formal-verification-skill/SKILL.md#demonstrate-detection-in-isolation): for a handwritten model, show the code change triggering correspondence review, translate that semantic change into the model, and retain the failing property and manual-translation limits. A model-only failure or drift alarm is not implementation-regression detection.
- **Counterexample:** replay each step against the real code. Correct and explain impossible model steps, then rerun. A realizable violation is a product finding; retain the property and describe the harm. Attribute an introducing commit only with evidence, otherwise say it is unknown. Keep any reproduction isolated from product edits.
- **Tool failure, timeout, inconclusive result, or missing mutation evidence:** mark the affected check blocked rather than treating process exit or partial output as verification.

Retain commands, versions, outputs, correspondence evidence, mutation diffs, and counterexamples outside scratch cleanup. Remove only owned scratch state and processes; rerun the unmutated source and confirm its baseline result is restored. Existing bugs remain visible; they cannot stand in for independent mutation detection when claiming that detection.

## Refresh the record

Update coverage, commands, bounds, assumptions, and evidence, then follow the revised skill once as the next agent would. Advance a check's last verified commit only after correspondence review and the required reruns and detection evidence complete. A confirmed bug may accompany a correspondence checkpoint, but record the failing result beside it. A blocked check retains its previous checkpoint, even when another check succeeds.

Do not label dirty source as verified at HEAD. Retain the previous commit checkpoint and record the evaluated working-tree diff or digest separately until the exact source is committed and verified. A legacy check without a defensible base remains uncheckpointed until the current-source review and validation complete.

## Report

For each check, report **in sync**, **updated**, **bug**, or **blocked**; an updated check may also expose a bug. Include the source identity and history reviewed, old/new checkpoint, verification changes and reasons, rerun and mutation results, findings, and coverage limits. Say when a stale pass became a real counterexample. Distinguish model evidence, implementation evidence, and generated-input testing; none establishes whole-system correctness. Keep verification changes separate from any separately authorized product fix.
