# Opening a PR
Run only when publication is part of the user's request.
1. Verify repository, branch, base, dirty state, and task files. Preserve unrelated work. Use an isolated worktree when needed; never routine reset --hard recovery.
2. Read repository requirements and run appropriate checks. Stage intended files explicitly and commit only with authorization.
3. Use the available forge tooling. For GitHub prefer gh with a body file containing real newlines. Follow repository templates and requested draft/ready state.
4. Write a title/body around the concrete problem, resulting behavior, tradeoffs that matter, and actual validation. Use technical-writing and unslop guidance where helpful.
5. Push/open the PR if requested, then read back its head, base, and URL. Opening does not authorize merge, auto-merge, or unsolicited babysitting.
Return what was published, the link, checks, and limits. Local fixes remain local when publication was not requested.
