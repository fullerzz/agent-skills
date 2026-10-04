#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate the task-sized Markdown plan contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def check(text: str) -> tuple[int, list[str]]:
    for fence in ("~~~", "```"):
        text = re.sub(r"^" + fence + r"[^\n]*\n[\s\S]*?^" + fence + r"[^\n]*$", "", text, flags=re.M)
    problems = []
    if not re.search(r"^# .+$", text, re.M):
        problems.append("Missing H1 title")
    sections = [
        (part.partition("\n")[0].strip(), part.partition("\n")[2].strip())
        for part in re.split(r"^## ", text, flags=re.M)[1:]
    ]
    for name in ("Outcome", "Scope", "Phases", "Risks", "Handoff"):
        found = [body for title, body in sections if title == name]
        if len(found) != 1 or not found[0]:
            problems.append("Need one nonempty ## " + name)
    body = next((body for name, body in sections if name == "Phases"), "")
    phases = re.split(r"^### ", body, flags=re.M)[1:]
    if not phases:
        problems.append("Phases needs at least one H3 unit")
    for phase in phases:
        title = phase.split("\n")[0].strip()
        problems.extend(
            title + ": missing nonempty " + field + " bullet"
            for field in ("Depends on", "Files", "Acceptance", "Verification")
            if not re.search(r"^- " + field + r":[ \t]*\S", phase, re.M)
        )
    return len(phases), problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: uv run check-plan.py <plan.md>", file=sys.stderr)
        return 2
    try:
        count, problems = check(Path(argv[0]).read_text(encoding="utf-8"))
        print(f"{count} phases, {len(problems)} problems")
        for problem in problems:
            print(f"{argv[0]}: {problem}", file=sys.stderr)
        return int(bool(problems))
    except (OSError, UnicodeError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
