# Shipping
Only run merges when the user explicitly authorized landing.
1. Pin the bottom-to-top dependency list, exact base/head SHAs, and relevant verification receipts. Use an independent verifier for substantial behavior changes under the native contract.
2. Re-check each patch and current-head CI/reviews/mergeability. A rewritten SHA needs fresh checks; a changed base-to-head patch needs relevant re-verification. Do not reuse a stale self-report.
3. Land only the contiguous verified run from the bottom. Prepare one frontier PR at a time; preserve shared branches and never weaken forge approvals.
4. Use the requested merge strategy. Arm merge-when-ready only when requested and only for the current frontier.
5. Wait for confirmed merged state, fetch/read trunk, and recompute the next base/head. Pending checks with BLOCKED are not proof of failure.
6. Stop at the first unverified or unauthorized item. If durable watching is unavailable, save the state and exact next check.
Return actual merges, current SHAs, verifier identities/receipts, remaining ceiling, and handoff. Do not post verdict comments unless posting was authorized.
