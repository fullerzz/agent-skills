# Autopilot-full
Execute an independent queue with explicit done conditions. The name does not grant merge authority.
1. Pin items, dependencies, operator-owned gates, scope, and authorized actions.
2. Assign native owners exclusive worktrees/files. Each produces a verified artifact and terminal report; queue within host limits.
3. Independent native reviewers verify material behavior at exact heads. Read their receipts and return confirmed defects to the owner.
4. Publish or merge only items explicitly covered by the user's request. Otherwise deliver local artifacts or merge-ready state.
5. Re-check current heads before any authorized merge. Never bypass enforced approvals or assume root approval replaces the operator.
6. Honor stop immediately; reconcile children and use pause-safely if the host cannot persist.
Return item/owner/status/head, verification, actual publication, and remaining gates.
