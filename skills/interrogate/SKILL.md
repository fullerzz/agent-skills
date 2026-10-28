---
name: interrogate
description: "Adversarial review of a requested diff or design; only findings that a rerun reproduction proves survive."
disable-model-invocation: true
---

# Interrogate

Adversaries try to break the requested change or design. A finding survives only when a run proves it. Report findings; do not apply fixes.

1. Pin scope: what the user names, otherwise the branch diff from its merge base through the working tree. State the intent per [in-your-own-words](../in-your-own-words/SKILL.md) from the request, commits, and PR description. Ask when the intent is unclear.
2. Give each of 2-3 adversaries its own detached worktree outside the target checkout, with the scope's uncommitted changes copied in, untracked files included. Build patches with `git diff --no-ext-diff --binary`, since an external diff tool yields no applicable patch. Run them through the [selected execution method](../z-mode/references/native-hosts.md#execution-selection) and record actual identities; same-model independence is not provider diversity. The target checkout and its unrelated work stay untouched.
3. Brief each adversary with the scope, the intent, and: "Break this change. Prove each finding with a run against the real code: a failing test, a repro script, or command output showing the wrong behavior. For a design or plan, run a prototype or probe the current tree. Keep repros in your own worktree. Report each finding with a title, the exact command, the output it printed, and the output the intent requires. Leave out anything you did not run, including style, naming, structure, and risks that need a future change to matter. No findings is a valid result."
4. Wait for terminal results. Rerun each finding's command yourself in a fresh isolated worktree at the scope, carrying over only the repro files it names. Keep a finding when the output shows the failure and the failure breaks the intent; drop the rest. Merge findings that share a root cause. Keep every verified finding, not one adversary's list.
5. Remove the worktrees you created.

Return:
- **Intent**: the restatement.
- **Findings**: for each verified finding, the command, its output, how it breaks the intent, and the adversaries that found it. Say "no verified findings" when none survive.
- **Dropped**: for each adversary, the count of dropped findings and why.

If agents are unavailable, label a parent-only interrogation. A finding nobody could run stays dropped, not promoted on argument.
