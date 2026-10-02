# Scoped session evidence

Use only the requested workspace, topic, and time window. Default an unspecified recent window to seven days and state it. A complete supplied handoff can replace mining. Never scan all personal chats to find a workspace.

Prefer the current conversation, an explicit session export, or native history access. Codex can resume by session ID (`codex resume <id>`); Claude Code can resume by ID (`claude --resume <id>`) or continue the current project's latest session (`claude --continue`). Resume commands start sessions; they are not read-only history probes.

If local history is necessary, first consult the installed host's help and inspect a single known session's metadata. Verify its workspace, ID, timestamp, and record schema before querying further. Codex storage and Claude Code JSONL layouts may change. Do not derive paths by replacing slashes in the project path or assume every JSONL line is one user message. Exclude eval/test children unless specifically in scope.

If the transcript cannot be verified or read, use a digest of visible conversation plus Git state. Label the result **digest-based; transcript not verified**. Cite evidence by real session/turn IDs or artifact paths. Missing access is a gap, not evidence of no prior work.

Historical claims need current checks when relevant: branch, SHA, dirty files, PR head/checks, and open blockers. Read-only status checks do not authorize remediation or replies to other people. Keep private excerpts out of public artifacts.
