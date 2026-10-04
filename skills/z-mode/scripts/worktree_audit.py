#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Report worktree evidence without declaring unknown history safe."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def run(argv: list[str], cwd: str | Path) -> str:
    return subprocess.run(  # noqa: S603 - Fixed Git/gh/gt argument vectors from local callers; no shell.
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        check=True,
    ).stdout


def read_prs(repo: str) -> tuple[list[dict[str, Any]], str]:
    try:
        value = json.loads(
            run(["gh", "pr", "list", "--state", "all", "--limit", "1000", "--json", "number,state,headRefName"], repo)
        )
        if not isinstance(value, list) or any(
            not isinstance(p, dict) or not {"number", "state", "headRefName"} <= p.keys() for p in value
        ):
            raise ValueError("invalid PR list")
        return value, "not-found"
    except (OSError, subprocess.CalledProcessError, ValueError):
        print("PR lookup unavailable; PR state is unknown.", file=sys.stderr)
        return [], "unknown"


def local_evidence(wt: str, head: str) -> tuple[str, str, str]:
    dirty, merged, bucket = "unknown", "unknown", "review-unknown"
    try:
        status = run(["git", "status", "--porcelain", "--untracked-files=all", "--ignored=matching"], wt)
        dirty = "has-files" if status else "clean"
        try:
            run(["git", "merge-base", "--is-ancestor", head, "refs/remotes/origin/main"], wt)
            merged = "yes-local-ref"
        except subprocess.CalledProcessError:
            merged = "no-or-unknown"
        bucket = "hold-files" if status else "review-history-unknown"
    except (OSError, subprocess.CalledProcessError):
        pass
    return dirty, merged, bucket


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    paths = [arg for arg in argv if arg != "--with-prs"]
    try:
        if len(paths) > 1 or any(p.startswith("-") for p in paths):
            raise ValueError("Usage: uv run worktree_audit.py [repo-path] [--with-prs]")
        repo = run(["git", "rev-parse", "--show-toplevel"], Path(paths[0] if paths else ".").absolute()).strip()
        prs, evidence = read_prs(repo) if "--with-prs" in argv else ([], "unknown")
        raw = run(["git", "worktree", "list", "--porcelain", "-z"], repo)
        print("REPO\t" + repo)
        print("HEAD\tMERGED\tDIRTY\tPR\tHISTORY\tBUCKET\tWORKTREE")
        for block in filter(None, raw.split("\0\0")):
            record = {}
            for field in filter(None, block.split("\0")):
                key, separator, value = field.partition(" ")
                record[key] = value if separator else "true"
            wt = record["worktree"]
            if wt == repo:
                continue
            dirty, merged, bucket = local_evidence(wt, record["HEAD"])
            if record.get("locked") or record.get("prunable"):
                bucket = "hold-unavailable"
            raw_branch = record.get("branch", "")
            branch = raw_branch.removeprefix("refs/heads/") if isinstance(raw_branch, str) else ""
            matches = [p for p in prs if p["headRefName"] == branch]
            pr = ",".join(f"#{p['number']}/{p['state']}" for p in matches) if matches else evidence
            if any(p["state"] == "OPEN" for p in matches):
                bucket = "hold-open-pr"
            print(
                "\t".join(
                    re.sub(r"[\t\r\n]", " ", str(c))
                    for c in [record.get("HEAD", "unknown"), merged, dirty, pr, "unknown", bucket, wt]
                )
            )
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
