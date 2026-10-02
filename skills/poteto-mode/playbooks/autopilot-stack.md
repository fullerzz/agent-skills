# Autopilot-stack
Build dependent changes for review without landing them.
1. Pin the ordered queue and acceptance criteria.
2. Assign exclusive native owners; dependencies relay source context and verified outputs.
3. One coordinator owns base-branch topology. Independent changes can run in parallel; dependent changes follow their parent.
4. Verify each exact base/head patch with appropriate harnesses and independent review where needed.
5. If publication is authorized, root targets trunk and each child targets its parent branch. Rebase/retarget only with covered authority and re-check affected results.
6. No merge or auto-merge. Deliver the ordered artifacts or published chain plus current evidence.
If interrupted save a handoff. Return root/tip when published, per-unit verdicts/SHAs, and excluded or blocked work.
