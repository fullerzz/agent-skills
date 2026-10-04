# Autopilot-full
Execute an independent queue with explicit done conditions. The name does not grant merge authority.
1. Pin items, dependencies, operator-owned gates, scope, and authorized actions.
2. Assign owners exclusive worktrees/files through the [selected execution method](../references/native-hosts.md#execution-selection). Each produces a verified artifact and terminal report; queue within host limits. Use a fresh owner for each next item or fix round under the [agent lifecycle rules](../references/native-hosts.md#agent-lifecycle). A retained Herdr pane does not imply reuse of its agent conversation.
3. Independent reviewers verify material behavior at exact heads. Read their receipts and assign confirmed defects to a fresh owner with a consolidated brief containing the original scope, later directives, prior report, and branch/artifact paths. Follow the agent lifecycle rules above for state-dependent reuse and safe writer handoff.
4. Publish or merge only items explicitly covered by the user's request. For publication follow [Opening a PR](opening-a-pr.md). Otherwise deliver local artifacts or merge-ready state.
5. Re-check current heads before any authorized merge. Never bypass enforced approvals or assume root approval replaces the operator.
6. Honor stop immediately; reconcile children and use pause-safely if the host cannot persist.
Return item/owner/status/head, verification, actual publication, and remaining gates.
