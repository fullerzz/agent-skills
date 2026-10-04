# Pause safely
Pause only on explicit pause/stop or when the session cannot continue.
1. Stop at an atomic boundary. Cancel/drain children and record unfinished work. For Herdr assignments, confirm worker state through [pause guidance](../../herdr-workflow/references/operations.md#pickup-pause-and-cleanup); detaching a client does not pause work. Report any worker that could not be stopped.
2. Preserve tracked, untracked, and concurrent files. Do not commit, push, or discard as a side effect of pausing.
3. Write a durable note in a user-owned task directory (default .agent-work/<slug>, excluded locally from Git when appropriate).
4. Record goal, active mode, execution preference, action authority, repository/worktree, branch/base/head SHAs, dirty files, completed checks and artifacts, decisions, children, blockers, and the exact first resume command/action. For Herdr include endpoint, task-to-agent/pane mapping, and remaining supporting processes. Never copy executable session controls into the handoff.
5. Link an existing decision trail rather than duplicating it. Verify the note survives process teardown.
Return note path, on-disk state, and first next action. A new session re-checks live state before continuing.
