# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "rich>=15.0.0",
# ]
# ///

# abspath normalizes lexically; resolve would follow symlinks and change ownership/scope.
# ruff: noqa: PTH100

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Never, NotRequired, TypedDict

from rich.console import Console, Group
from rich.panel import Panel
from rich.segment import Segment, Segments
from rich.table import Table
from rich.text import Text

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
    host: str
    receipt: Path
    legacy_receipt: NotRequired[Path]
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
    return path.is_symlink() and Path(os.path.abspath(path.parent / path.readlink())) == source


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


OPS = {
    "collision": ("bold red", "exists and is not owned; blocks install"),
    "create": ("green", "new"),
    "update": ("cyan", "owned copy changed in checkout"),
    "replace": ("yellow", "overwritten by --force"),
    "remove": ("red", "owned by this checkout"),
    "preserve": ("magenta", "unowned or modified; left in place"),
    "keep": ("dim", "already installed"),
    "absent": ("dim", "not installed"),
}
HOSTS = {"codex": "Codex", "claude": "Claude Code"}


def tilde(path: Path) -> str:
    home = Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


def show(plans: list[Plan], action: str) -> None:
    # Pipes and tests get one tab-separated line per entry.
    if not console.is_terminal:
        for plan in plans:
            for entry in plan["entries"]:
                console.print(
                    Segments([Segment(f"{entry['op']}\t{entry['target']}\t{entry['source']}\n")]),
                    end="",
                )
        return
    console.print(Text.assemble((f"zstack {action}", "bold"), " from ", tilde(ROOT)))
    for plan in plans:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(no_wrap=True)
        grid.add_column(justify="right")
        grid.add_column()
        dirs = {entry["kind"]: entry["target"].parent for entry in plan["entries"]}
        for kind, label in (("link", "skills"), ("copy", "agents")):
            grid.add_row(Text(label, "dim"), "", Text(tilde(dirs[kind]), "dim", overflow="fold"))
        grid.add_row()
        for op, (style, note) in OPS.items():
            names = [entry["target"].name for entry in plan["entries"] if entry["op"] == op]
            if names:
                grid.add_row(
                    Text(op, style),
                    str(len(names)),
                    Group(
                        Text(note, "dim italic"),
                        Text("  ".join(names), overflow="fold"),
                    ),
                )
        console.print(
            Panel(
                grid,
                title=Text(HOSTS[plan["host"]], "bold"),
                title_align="left",
                border_style="dim",
            )
        )


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError(message)


def load_receipt(native: Path) -> tuple[Path, Receipt]:
    receipt = native / "zstack-install.json"
    legacy_receipt = native / "pstack-install.json"
    if present(legacy_receipt):
        if present(receipt):
            raise ValueError(f"Both current and legacy receipts exist: {receipt}, {legacy_receipt}")
        receipt = legacy_receipt
    if present(receipt) and (receipt.is_symlink() or not receipt.is_file()):
        raise ValueError(f"Receipt is not a regular file: {receipt}")
    saved: Receipt = json.loads(receipt.read_text()) if receipt.exists() else {"source": str(ROOT), "agents": {}}
    if not isinstance(saved, dict) or saved.get("source") != str(ROOT) or not isinstance(saved.get("agents"), dict):
        raise ValueError(f"Receipt belongs to another checkout or is invalid: {receipt}")
    if any(
        not isinstance(value, str) and not (isinstance(value, list) and all(isinstance(item, str) for item in value))
        for value in saved["agents"].values()
    ):
        raise ValueError(f"Receipt belongs to another checkout or is invalid: {receipt}")
    return receipt, saved


def assign_operation(entry: Entry, saved: Receipt, install: bool, force: bool) -> None:
    target, source = entry["target"], entry["source"]
    exists = present(target)
    hashes = saved["agents"].get(source.name)
    owned_hashes = hashes if isinstance(hashes, list) else [hashes]
    owned = (
        owns_link(target, source)
        if entry["kind"] == "link"
        else exists and target.is_file() and not target.is_symlink() and digest(target) in owned_hashes
    )
    if install:
        entry["op"] = (
            ("update" if entry["kind"] == "copy" and digest(source) != digest(target) else "keep")
            if exists and owned
            else "replace"
            if exists and force and entry["kind"] == "link"
            else "collision"
            if exists
            else "create"
        )
    else:
        entry["op"] = ("remove" if owned else "preserve") if exists else "absent"


def build_plan(host: str, home: Path, project: Path | None, args: argparse.Namespace) -> Plan:
    base = project or home
    configured = os.environ.get("CODEX_HOME" if host == "codex" else "CLAUDE_CONFIG_DIR")
    native = Path(os.path.abspath(configured)) if not project and not args.home and configured else base / f".{host}"
    skills = base / ".agents/skills" if host == "codex" else native / "skills"
    receipt, saved = load_receipt(native)
    legacy_receipt = native / "pstack-install.json"
    entries: list[Entry] = [
        {"source": skill, "target": skills / skill.name, "kind": "link"}
        for skill in sorted((ROOT / "skills").iterdir())
        if skill.is_dir() and not skill.is_symlink() and (skill / "SKILL.md").exists()
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
    # Retire only links and copies whose ownership still matches this checkout.
    retired: list[Entry] = [
        {
            "source": ROOT / "skills" / name,
            "target": skills / name,
            "kind": "link",
        }
        for name in ("poteto-mode", "setup-pstack")
    ]
    old_agent = "poteto-agent.toml" if host == "codex" else "poteto-agent.md"
    retired.append(
        {
            "source": ROOT / "agents" / host / old_agent,
            "target": native / "agents" / old_agent,
            "kind": "copy",
            "name": old_agent,
        }
    )
    entries += retired
    for entry in entries:
        assign_operation(entry, saved, args.action == "install" and entry not in retired, args.force)
    plan: Plan = {
        "host": host,
        "receipt": native / "zstack-install.json",
        "saved": saved,
        "entries": entries,
    }
    if receipt == legacy_receipt:
        plan["legacy_receipt"] = legacy_receipt
    return plan


def apply_entry(entry: Entry, plan: Plan) -> None:
    target, source = entry["target"], entry["source"]
    if entry["op"] in ("create", "update", "replace"):
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["kind"] == "link":
            if entry["op"] == "replace":
                if target.is_symlink() or not target.is_dir():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            target.symlink_to(source, target_is_directory=True)
        else:
            # An interrupted update may leave either the old or the new owned copy.
            next_hash = digest(source)
            old = plan["saved"]["agents"].get(entry["name"])
            old_hashes = old if isinstance(old, list) else [old]
            plan["saved"]["agents"][entry["name"]] = list(
                dict.fromkeys(value for value in [*old_hashes, next_hash] if value)
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


def validate_arguments(args: argparse.Namespace) -> None:
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


def main() -> None:
    parser = Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("action", nargs="?", default="install")
    parser.add_argument("--host", default="both")
    parser.add_argument("--home")
    parser.add_argument("--project")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--help", action="store_true")
    args = parser.parse_args()
    if args.help:
        console.print(
            "uv run scripts/install.py [install|uninstall] --host codex|claude|both "
            "[--project PATH | --home PATH] [--force] [--apply]\n"
            "Preview by default. --force replaces conflicting skills on install; --apply is still required. "
            "Skills are links; agents are owned copies. No model or permission settings are changed."
        )
        return
    validate_arguments(args)
    home = Path(os.path.abspath(args.home)) if args.home else Path.home()
    project = Path(args.project).resolve(strict=True) if args.project else None
    hosts = ["codex", "claude"] if args.host == "both" else [args.host]
    plans = [build_plan(host, home, project, args) for host in hosts]
    show(plans, args.action)
    if any(entry["op"] == "collision" for plan in plans for entry in plan["entries"]):
        raise ValueError(
            "Existing files conflict. Nothing installed; choose another scope or resolve the named collisions."
        )
    if not args.apply:
        console.print(
            "Preview only. Add --apply to perform these operations.",
            style="bold yellow",
        )
        return
    for plan in plans:
        if "legacy_receipt" in plan:
            plan["legacy_receipt"].replace(plan["receipt"])
        for entry in plan["entries"]:
            apply_entry(entry, plan)
        if plan["saved"]["agents"]:
            save(plan)
        elif present(plan["receipt"]):
            plan["receipt"].unlink()
    if any(entry["op"] == "preserve" for plan in plans for entry in plan["entries"]):
        console.print(
            "Preserved unowned or modified files. Their receipts remain for inspection.",
            style="magenta",
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        errors.print(str(error), style="bold red")
        sys.exit(1)
