# Autopilot-stack
Build dependent changes for review without landing them.
1. Pin the ordered queue and acceptance criteria.
2. Assign exclusive owners through the [selected execution method](../references/native-hosts.md#execution-selection); dependencies relay source context and verified outputs. Use a fresh owner for each next item or fix round under the [agent lifecycle rules](../references/native-hosts.md#agent-lifecycle). With Herdr, release dependents only after artifact acceptance, not merely a ready agent state.
3. One coordinator owns base-branch topology. Independent changes can run in parallel; dependent changes follow their parent.
4. Verify each exact base/head patch with appropriate harnesses and independent review where needed.
5. If publication is authorized, follow [Opening a PR](opening-a-pr.md) for tooling, descriptions, and readiness. Root targets trunk and each child targets its parent branch. Rebase/retarget only with covered authority and re-check affected results.
6. No merge or auto-merge. Deliver the ordered artifacts or published chain plus current evidence.
If interrupted save a handoff. Return root/tip when published, per-unit verdicts/SHAs, and excluded or blocked work.
