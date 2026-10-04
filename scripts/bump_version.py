# /// script
# requires-python = ">=3.11"
# ///
"""Bump the shared 0.MINOR.PATCH version of the Codex and Claude Code plugins."""

import json
import re
import sys
from pathlib import Path

MANIFESTS = (".codex-plugin/plugin.json", ".claude-plugin/plugin.json")
VERSION = re.compile(r"0\.(\d+)\.(\d+)")
FIELD = re.compile(r'("version"\s*:\s*")[^"]*(")')


def bump(root: Path, part: str) -> str:
    files = [root / name for name in MANIFESTS]
    versions = {json.loads(file.read_text(encoding="utf-8")).get("version") for file in files}
    if len(versions) != 1:
        raise ValueError(f"Plugin versions differ: {sorted(map(str, versions))}")
    current = versions.pop()
    match = VERSION.fullmatch(str(current))
    if match is None:
        raise ValueError(f"Expected a 0.MINOR.PATCH version, found {current}")
    minor, patch = map(int, match.groups())
    if part == "minor":
        new = f"0.{minor + 1}.0"
    elif part == "patch":
        new = f"0.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Unknown part {part!r}; use minor or patch")
    # Substitute in place so each manifest keeps its hand-written layout.
    for file in files:
        text, count = FIELD.subn(rf"\g<1>{new}\g<2>", file.read_text(encoding="utf-8"), count=1)
        if count != 1:
            raise ValueError(f"No version field in {file}")
        file.write_text(text, encoding="utf-8")
    return new


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: bump_version.py minor|patch")
    try:
        print(bump(Path(__file__).resolve().parent.parent, sys.argv[1]))
    except (OSError, ValueError) as error:
        sys.exit(str(error))
