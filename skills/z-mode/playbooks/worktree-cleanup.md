# Worktree cleanup
1. Resolve the bundled scripts/worktree-audit.py with uv run and pass the target repository explicitly. The default audit uses local Git only; --with-prs requests a read-only GitHub lookup.
2. Treat buckets as advice, never deletion authorization. Untracked/ignored work, active agents/processes, locked trees, and unknown history require inspection.
3. Review branch/head/base, diffs, files, upstream/PR state, and known active sessions for every candidate. A CLOSED PR is not evidence of merge.
4. Remove only specifically authorized, clean, unused worktrees using git worktree remove without --force. Stop on dirty/ignored files; never bulk rm -rf user state.
5. Report reclaimed space and every held candidate with reason. Simulator/cache deletion needs its own named scope and usage check.
Unknown session history never produces a "safe" classification.
