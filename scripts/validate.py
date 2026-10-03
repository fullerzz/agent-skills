# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "rich>=15.0.0",
#     "pyyaml>=6.0.3",
# ]
# ///

import json
import re
import stat
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote

import yaml
from rich.console import Console

# Codex opts in only these read-only workflows; Claude retains explicit invocation.
CODEX_IMPLICIT_SKILLS = {"how", "why"}


class YamlLoader(yaml.SafeLoader):
    pass


# YAML 1.2 booleans match Bun; names such as "on" remain strings.
YamlLoader.yaml_implicit_resolvers = {
    key: [
        (tag, pattern) for tag, pattern in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


YamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_yaml(text: str):
    return yaml.load(text, Loader=YamlLoader)


def frontmatter(file: Path) -> dict:
    match = re.match(
        r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)", file.read_text(encoding="utf-8")
    )
    if not match:
        raise ValueError("Missing YAML frontmatter")
    meta = load_yaml(match[1])
    if (
        not isinstance(meta, dict)
        or not isinstance(meta.get("name"), str)
        or not isinstance(meta.get("description"), str)
        or not meta["description"].strip()
    ):
        raise ValueError("Need scalar name and nonempty description")
    if (
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", meta["name"])
        or len(meta["name"]) > 64
        or len(meta["description"]) > 1024
    ):
        raise ValueError("Invalid identifier or metadata length")
    return meta


def validate(root: Path) -> tuple[int, list[str]]:
    failures = []
    names = set()

    def fail(file, message):
        failures.append(f"{file}: {message}")

    def walk(directory):
        for path in sorted(directory.iterdir()):
            if path.name in {
                "node_modules",
                "dist",
                ".git",
                ".agent-work",
                ".venv",
                "__pycache__",
            }:
                continue
            if path.is_symlink():
                continue
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield path

    allowed = {
        "name",
        "description",
        "disable-model-invocation",
        "metadata",
        "license",
        "compatibility",
        "allowed-tools",
    }
    unsupported = re.compile(
        r"\.cursor/|cursor-team-kit|(?:pstack|zstack)-models\.mdc|run_in_background|cloud_base_branch|subagent_type|grok-4|claude-opus-5-5|gpt-5\.6-sol|/loop\b|/goal\b"
    )
    for file in walk(root):
        relative = file.relative_to(root).as_posix()
        try:
            if file.name == "SKILL.md":
                meta = frontmatter(file)
                if meta["name"] != file.parent.name:
                    fail(relative, "Name must match directory")
                if meta["name"] in names:
                    fail(relative, "Duplicate skill name")
                names.add(meta["name"])
                for key in meta:
                    if key not in allowed:
                        fail(relative, f"Unsupported shared metadata: {key}")
                if "disable-model-invocation" in meta and not isinstance(
                    meta["disable-model-invocation"], bool
                ):
                    fail(relative, "Invocation flag must be boolean")
                if meta.get("disable-model-invocation") is True:
                    policy_file = file.parent / "agents/openai.yaml"
                    policy = (
                        load_yaml(policy_file.read_text(encoding="utf-8"))
                        if policy_file.exists()
                        else None
                    )
                    policy = policy.get("policy") if isinstance(policy, dict) else None
                    if (
                        not isinstance(policy, dict)
                        or policy.get("allow_implicit_invocation")
                        is not (meta["name"] in CODEX_IMPLICIT_SKILLS)
                    ):
                        fail(relative, "Explicit-only Codex policy missing" if meta["name"] not in CODEX_IMPLICIT_SKILLS else "Read-only Codex implicit policy missing")
            if relative.startswith("agents/codex/"):
                meta = tomllib.loads(file.read_text(encoding="utf-8"))
                for key in ("name", "description", "developer_instructions"):
                    if not isinstance(meta.get(key), str) or not meta[key].strip():
                        fail(relative, f"Missing {key}")
                if meta.get("name") != file.name.removesuffix(".toml"):
                    fail(relative, "Agent name mismatch")
            if relative.startswith("agents/claude/"):
                meta = frontmatter(file)
                if (
                    meta["name"] != file.name.removesuffix(".md")
                    or meta.get("model") != "inherit"
                ):
                    fail(relative, "Agent name/model mismatch")
            if file.suffix == ".yaml":
                load_yaml(file.read_text(encoding="utf-8"))
            if file.suffix != ".md":
                continue
            text = file.read_text(encoding="utf-8")
            if re.search(r"[ \t]+$", text, re.MULTILINE):
                fail(relative, "Trailing whitespace")
            prose = re.sub(
                r"^```[^\n]*\n[\s\S]*?^```[^\n]*$", "", text, flags=re.MULTILINE
            )
            for match in re.finditer(r"\]\(([^)]+)\)", prose):
                link = match[1]
                if re.match(r"(?:https?:|mailto:|#)", link) or re.search(r"[<>]", link):
                    continue
                path = unquote(link.split("#")[0], errors="strict")
                if not (file.parent / path).exists():
                    fail(relative, f"Broken local link: {link}")
            if relative.startswith(
                ("skills/", "docs/guide/", "agents/")
            ) and unsupported.search(text):
                fail(relative, "Active unsupported host instruction")
        except (OSError, ValueError, yaml.YAMLError) as error:
            fail(relative, str(error))

    for path in (
        "scripts/check-plan.mjs",
        "scripts/worktree-audit.sh",
        "scripts/worktree-audit.mjs",
        "scripts/watch-pr/watch-pr",
        "scripts/orch/orch.ts",
    ):
        if not (root / "skills/z-mode" / path).exists():
            fail(path, "Missing tool entrypoint")
    for relative in (
        "skills/show-me-your-work/scripts/log.sh",
        "skills/z-mode/scripts/watch-pr/watch-pr",
    ):
        try:
            if not (root / relative).stat().st_mode & (
                stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            ):
                fail(relative, "Helper not executable")
        except OSError as error:
            fail(relative, str(error))
    for path in (".cursor-plugin", "automations/benny", "skills/make-bot-ui"):
        if (root / path).exists():
            fail(path, "Retired content remains")
    manifest_file = root / ".codex-plugin/plugin.json"
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            if (
                manifest.get("skills") != "./skills/"
                or manifest.get("name") != "zstack"
                or not re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", ""))
            ):
                fail(".codex-plugin/plugin.json", "Invalid native plugin identity")
            hooks = manifest["hooks"]
            if hooks != "./hooks/hooks.json" or not (root / hooks).is_file():
                fail(".codex-plugin/plugin.json", "Missing bundled hook configuration")
            if not (root / "skills").is_dir() or not (root / "LICENSE").is_file():
                fail(".codex-plugin/plugin.json", "Missing shared skills or license")
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            fail(".codex-plugin/plugin.json", str(error))
    return len(names), failures


def main() -> int:
    count, failures = validate(Path(__file__).resolve().parent.parent)
    Console().print(
        f"{count} skills, {len(failures)} structural problems",
        style="red" if failures else "green",
        markup=False,
    )
    console = Console(stderr=True)
    for failure in failures:
        console.print(failure, style="red", markup=False, highlight=False)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
