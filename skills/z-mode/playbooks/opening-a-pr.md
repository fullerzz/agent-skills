# Opening a PR
Run only when publication is part of the user's request.
1. Verify repository, branch, base, dirty state, and task files. Preserve unrelated work. Use an isolated worktree when needed; never routine reset --hard recovery.
2. Read repository requirements and run appropriate checks. Stage intended files explicitly and commit only with authorization.
3. Resolve the forge and the available PR tools. Use the host's built-in PR tool for creation, edits, retargeting, and readiness when it supports that operation, following its instructions. For unsupported operations or when no built-in tool exists, use the repository's forge or stack tooling; for GitHub the fallback is gh with a body file containing real newlines. Complete any host-required PR attachment or registration after creation, including CLI creation. An attachment-only tool does not replace a creation tool.
4. Write a title/body around the concrete problem and resulting behavior, using the description format below unless the repository template or user requests another format. Use technical-writing and unslop guidance where helpful.
5. Push/open the PR if requested, then read back its head, base, and URL. Opening does not authorize merge, auto-merge, or unsolicited babysitting.
Return what was published, the link, checks, and limits. Local fixes remain local when publication was not requested.

## Description format

Keep the briefing readable in under a minute, normally under 40 lines. Use actual `##` headings rather than bold lead-ins. Keep these sections in order. Only `## Tradeoffs` and `## Blast Radius` are optional, under the conditions below:

- `## Why`: one to three short sentences stating the problem and approach.
- `## What changed`: one to three bullets. Name symbols or paths only when they explain the change; name both sides of a rename.
- `## Scope`: one to three items stating what this PR covers and any deliberate exclusions, follow-ups, or known gaps. Do not invent exclusions or enumerate every file.
- `## Tradeoffs`: only alternatives a reviewer would reasonably ask about; omit when there was no meaningful choice.
- `## Blast Radius`: one or two sentences identifying affected users or behavior and material risks; omit when there is no material risk or cost to report. If this repairs a red main, explain the cost of leaving it broken.
- `## Verification`: one to three bullets naming actual checks and outcomes. For performance changes, use one primary before/after number with units and link the supporting run evidence.

Link detailed logs, measurements, and review artifacts instead of pasting SHA lists, worker reports, or file-by-file recitals. Attach screenshots or video when they prove a claim.

## Stacks and readiness

For a requested stack, the first PR targets trunk and each child targets its parent branch. Create or retarget through the chosen tool and read back the actual base. Keep each layer's title and body about that layer's diff.

Follow the user's requested draft/ready state and repository policy. Otherwise open ready for review, setting the state explicitly when the tool defaults to draft. Verify the actual state after creation and correct it through the chosen tool when necessary. Ready does not authorize merge or auto-merge.
