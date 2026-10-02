# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "rich>=15.0.0",
# ]
# ///

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Never, NotRequired, TypedDict

from rich.console import Console
from rich.segment import Segment, Segments

ROOT = Path(__file__).resolve().parent.parent
console = Console(soft_wrap=True, highlight=False, markup=False)
errors = Console(stderr=True, soft_wrap=True, highlight=False, markup=False)


class Receipt(TypedDict):
    source: str
    agents: dict[str, str | list[str]]


class Entry(TypedDict):
    source: Path
    target: Path
    kind: str
    name: NotRequired[str]
    op: NotRequired[str]


class Plan(TypedDict):
    receipt: Path
    saved: Receipt
    entries: list[Entry]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def owns_link(path: Path, source: Path) -> bool:
    return (
        path.is_symlink()
        and Path(os.path.abspath(path.parent / path.readlink())) == source
    )


def atomic_write(target: Path, contents: bytes) -> None:
    temporary = target.with_name(f"{target.name}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(contents)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def save(plan: Plan) -> None:
    plan["receipt"].parent.mkdir(parents=True, exist_ok=True)
    atomic_write(plan["receipt"], (json.dumps(plan["saved"], indent=2) + "\n").encode())


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError(message)


def main() -> None:
    parser = Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("action", nargs="?", default="install")
    parser.add_argument("--host", default="both")
    parser.add_argument("--home")
    parser.add_argument("--project")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--help", action="store_true")
    args = parser.parse_args()
    if args.help:
        console.print(
            "uv run scripts/install.py [install|uninstall] --host codex|claude|both [--project PATH | --home PATH] [--apply]\nPreview by default. Skills are links; agents are owned copies. No model or permission settings are changed."
        )
        return
    if args.action not in ("install", "uninstall") or args.host not in (
        "both",
        "codex",
        "claude",
    ):
        raise ValueError("Invalid action or host. See --help.")
    if args.home == "" or args.project == "":
        raise ValueError("--home and --project paths must not be empty.")
    if args.project and args.home:
        raise ValueError("Choose --project or --home.")
    home = Path(os.path.abspath(args.home)) if args.home else Path.home()
    project = Path(args.project).resolve(strict=True) if args.project else None
    hosts = ["codex", "claude"] if args.host == "both" else [args.host]
    plans: list[Plan] = []
    for host in hosts:
        base = project or home
        configured = os.environ.get(
            "CODEX_HOME" if host == "codex" else "CLAUDE_CONFIG_DIR"
        )
        native = (
            Path(os.path.abspath(configured))
            if not project and not args.home and configured
            else base / f".{host}"
        )
        skills = base / ".agents/skills" if host == "codex" else native / "skills"
        receipt = native / "pstack-install.json"
        if present(receipt) and (receipt.is_symlink() or not receipt.is_file()):
            raise ValueError(f"Receipt is not a regular file: {receipt}")
        saved: Receipt = (
            json.loads(receipt.read_text())
            if receipt.exists()
            else {"source": str(ROOT), "agents": {}}
        )
        if (
            not isinstance(saved, dict)
            or saved.get("source") != str(ROOT)
            or not isinstance(saved.get("agents"), dict)
        ):
            raise ValueError(
                f"Receipt belongs to another checkout or is invalid: {receipt}"
            )
        if any(
            not isinstance(value, str)
            and not (
                isinstance(value, list) and all(isinstance(item, str) for item in value)
            )
            for value in saved["agents"].values()
        ):
            raise ValueError(
                f"Receipt belongs to another checkout or is invalid: {receipt}"
            )
        entries: list[Entry] = [
            {"source": skill, "target": skills / skill.name, "kind": "link"}
            for skill in sorted((ROOT / "skills").iterdir())
            if skill.is_dir()
            and not skill.is_symlink()
            and (skill / "SKILL.md").exists()
        ]
        entries += [
            {
                "source": agent,
                "target": native / "agents" / agent.name,
                "kind": "copy",
                "name": agent.name,
            }
            for agent in sorted((ROOT / "agents" / host).iterdir())
        ]
        for entry in entries:
            target, source = entry["target"], entry["source"]
            exists = present(target)
            hashes = saved["agents"].get(source.name)
            owned_hashes = hashes if isinstance(hashes, list) else [hashes]
            owned = (
                owns_link(target, source)
                if entry["kind"] == "link"
                else exists
                and target.is_file()
                and not target.is_symlink()
                and digest(target) in owned_hashes
            )
            if args.action == "install":
                entry["op"] = (
                    (
                        "update"
                        if entry["kind"] == "copy" and digest(source) != digest(target)
                        else "keep"
                    )
                    if exists and owned
                    else "collision"
                    if exists
                    else "create"
                )
            else:
                entry["op"] = (
                    ("remove" if owned else "preserve") if exists else "absent"
                )
        plans.append({"receipt": receipt, "saved": saved, "entries": entries})
    for plan in plans:
        for entry in plan["entries"]:
            console.print(
                Segments(
                    [Segment(f"{entry['op']}\t{entry['target']}\t{entry['source']}\n")]
                ),
                end="",
            )
    if any(entry["op"] == "collision" for plan in plans for entry in plan["entries"]):
        raise ValueError(
            "Existing files conflict. Nothing installed; choose another scope or resolve the named collisions."
        )
    if not args.apply:
        console.print("Preview only. Add --apply to perform these operations.")
        return
    for plan in plans:
        for entry in plan["entries"]:
            target, source = entry["target"], entry["source"]
            if entry["op"] in ("create", "update"):
                target.parent.mkdir(parents=True, exist_ok=True)
                if entry["kind"] == "link":
                    target.symlink_to(source, target_is_directory=True)
                else:
                    # An interrupted update may leave either the old or the new owned copy.
                    next_hash = digest(source)
                    old = plan["saved"]["agents"].get(entry["name"])
                    old_hashes = old if isinstance(old, list) else [old]
                    plan["saved"]["agents"][entry["name"]] = list(
                        dict.fromkeys(
                            value for value in [*old_hashes, next_hash] if value
                        )
                    )
                    save(plan)
                    if entry["op"] == "create":
                        with target.open("xb") as stream:
                            stream.write(source.read_bytes())
                    else:
                        atomic_write(target, source.read_bytes())
                    plan["saved"]["agents"][entry["name"]] = next_hash
            elif entry["op"] == "remove":
                target.unlink()
                if entry["kind"] == "copy":
                    plan["saved"]["agents"].pop(entry["name"], None)
            elif entry["kind"] == "copy" and entry["op"] == "absent":
                plan["saved"]["agents"].pop(entry["name"], None)
        if plan["saved"]["agents"]:
            save(plan)
        elif present(plan["receipt"]):
            plan["receipt"].unlink()
    if args.action == "uninstall" and any(
        entry["op"] == "preserve" for plan in plans for entry in plan["entries"]
    ):
        console.print(
            "Preserved unowned or modified files. Their receipts remain for inspection."
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        errors.print(str(error))
        sys.exit(1)
