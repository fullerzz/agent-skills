# Verify before publication

Use the project's existing harness first. [create-verification-skill](../../skills/create-verification-skill/SKILL.md) generates native project instructions from real launch/doctor/drive/evidence/cleanup behavior, then executes one mapped path. [maintenance](../../skills/maintain-verification-skill/SKILL.md) stays within that skill directory and reports product regressions.

Local edits, commit, push, PR, merge, and deployment are separate requested actions. [Opening a PR](../../skills/poteto-mode/playbooks/opening-a-pr.md) runs only for requested publication. [Babysit](../../skills/poteto-mode/playbooks/babysit.md) keeps status questions read-only; [shipping](../../skills/poteto-mode/playbooks/shipping.md) needs explicit landing authority and current-head evidence.
