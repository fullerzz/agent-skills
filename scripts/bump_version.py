# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0.3"]
# ///
"""Bump the shared 0.MINOR.PATCH version of all native plugins."""

import json
import re
import sys
from pathlib import Path

import yaml

MANIFESTS = (".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "plugin.yaml")
VERSION = re.compile(r"0\.(\d+)\.(\d+)")
FIELD = re.compile(r'("version"\s*:\s*")[^"]*(")')
YAML_FIELD = re.compile(r"^(version:[ \t]*)[^\r\n]+()$", re.MULTILINE)


def read_version(file: Path) -> object:
    text = file.read_text(encoding="utf-8")
    manifest = yaml.safe_load(text) if file.suffix == ".yaml" else json.loads(text)
    if not isinstance(manifest, dict):
        raise ValueError(f"Expected a plugin manifest mapping in {file}")
    return manifest.get("version")


def bump(root: Path, part: str) -> str:
    files = [root / name for name in MANIFESTS]
    versions = {read_version(file) for file in files}
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
    updates = []
    for file in files:
        field = YAML_FIELD if file.suffix == ".yaml" else FIELD
        text, count = field.subn(rf"\g<1>{new}\g<2>", file.read_text(encoding="utf-8"), count=1)
        if count != 1:
            raise ValueError(f"No version field in {file}")
        updates.append((file, text))
    for file, text in updates:
        file.write_text(text, encoding="utf-8")
    return new


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: bump_version.py minor|patch")
    try:
        print(bump(Path(__file__).resolve().parent.parent, sys.argv[1]))
    except (OSError, ValueError, yaml.YAMLError) as error:
        sys.exit(str(error))
