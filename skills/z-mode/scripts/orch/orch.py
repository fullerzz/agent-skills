#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Manage plain-file orchestration records without changing the target cwd."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import POINTER_FIELDS, UNIT_FIELDS, VERDICTS, NotFoundError, Store, UserError, count_line, positive

if TYPE_CHECKING:
    from collections.abc import Sequence


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"error: {message}\n")


def integer(value: str) -> int:
    try:
        return (
            positive(int(value)) if value.isascii() and value.isdecimal() and not value.startswith("0") else positive(0)
        )
    except (ValueError, UserError) as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error


def parser() -> Parser:
    common = Parser(add_help=False)
    common.add_argument("--store", default=argparse.SUPPRESS, help="store directory (or ORCH_STORE)")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--force", action="store_true", default=argparse.SUPPRESS)
    root = Parser(prog="orch", description=__doc__, parents=[common], allow_abbrev=False)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        commands.add_parser(name, parents=[common], allow_abbrev=False)
    specs = {
        "unit": ["add", "set", "get", "list", "counts"],
        "ledger": ["record", "check", "summary"],
        "inbox": ["push", "drain", "count"],
        "gate": ["park", "list", "resolve"],
        "frontier": ["set", "show"],
        "standing": ["add", "show"],
    }
    for group, names in specs.items():
        parent = commands.add_parser(group, parents=[common], allow_abbrev=False)
        leaves = parent.add_subparsers(dest="action", required=True)
        for name in names:
            leaf = leaves.add_parser(name, parents=[common], allow_abbrev=False)
            configure_leaf(leaf, group, name)
    return root


def configure_unit(leaf: Parser, name: str) -> None:
    if name in ("add", "set", "get"):
        leaf.add_argument("id")
    if name == "add":
        leaf.add_argument("--track", required=True)
        leaf.add_argument("--brief")
    if name == "set":
        leaf.add_argument("--state", required=True)
        leaf.add_argument("--branch")
        leaf.add_argument("--pr", type=integer)
        leaf.add_argument("--sha")
    if name == "list":
        leaf.add_argument("--state")
        leaf.add_argument("--track")


def configure_ledger(leaf: Parser, name: str) -> None:
    if name in ("record", "check"):
        leaf.add_argument("pr", type=integer)
        leaf.add_argument("sha")
    if name == "record":
        leaf.add_argument("verdict", choices=VERDICTS)
        leaf.add_argument("--evidence", required=True)
        leaf.add_argument("--verifier")


def configure_leaf(leaf: Parser, group: str, name: str) -> None:
    if group == "unit":
        configure_unit(leaf, name)
    elif group == "ledger":
        configure_ledger(leaf, name)
    elif group == "inbox":
        if name == "push":
            for arg in ("agent", "unit", "status"):
                leaf.add_argument(arg)
            leaf.add_argument("--report")
        elif name == "drain":
            leaf.add_argument("--peek", action="store_true")
    else:
        configure_other_leaf(leaf, group, name)


def configure_other_leaf(leaf: Parser, group: str, name: str) -> None:
    if group == "gate":
        if name in ("park", "resolve"):
            leaf.add_argument("id")
        if name == "park":
            for arg in ("question", "options", "default"):
                leaf.add_argument("--" + arg, required=True)
        elif name == "resolve":
            leaf.add_argument("--answer", required=True)
    elif (group, name) == ("frontier", "set"):
        leaf.add_argument("--repo", default=os.environ.get("ORCH_REPO"))
        leaf.add_argument("--prs", type=lambda x: [integer(n) for n in x.split(",")])
    elif (group, name) == ("standing", "add"):
        leaf.add_argument("line")


def rows_text(rows: list[dict[str, Any]], fields: Sequence[str], empty: str, limit: int | None = 4) -> str:
    visible = rows if limit is None else rows[:limit]
    lines = ["\t".join(str(row[key]) for key in fields) for row in visible]
    if limit is not None and len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more; use --json")
    return "\n".join(lines) or empty


def compact_status(value: dict[str, Any]) -> str:
    summary = value["summary"]
    ids = summary["openGateIds"]
    suffix = "; ids=" + ",".join(ids[:4]) + (f",+{len(ids) - 4} more" if len(ids) > 4 else "") if ids else ""
    return (
        f"counts: units={len(value['units'])}; states={count_line(summary['unitStates'])}; "
        f"ledger={count_line(summary['ledgerVerdicts'])}\nchanged: {value['changed']}\n"
        f"gates open: {len(ids)}{suffix}"
    )


def compact_rows(command: str, rows: list[dict[str, Any]]) -> str:
    if command == "unit":
        return rows_text(rows, UNIT_FIELDS, "(no units)")
    if command == "inbox":
        return rows_text(rows, POINTER_FIELDS, "(empty)", None)
    if command == "gate":
        return rows_text(rows, ["id", "question", "options", "defaultAnswer"], "(no open gates)")
    if command == "standing":
        lines = [f"{r['number']}. {r['line']}" for r in rows[:4]]
        if len(rows) > 4:
            lines.append(f"... {len(rows) - 4} more; use --json")
        return "\n".join(lines) or "(no standing orders)"
    raise UserError("unknown row command")


def compact(command: str, action: str | None, value: dict[str, Any] | list[dict[str, Any]] | int) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return compact_rows(command, value)
    if command == "init":
        return f"initialized {value['store']}"
    if command == "status":
        return compact_status(value)
    if (command, action) in [("unit", "counts"), ("ledger", "summary")]:
        return count_line(value)
    if command in ("unit", "standing"):
        return compact_rows(command, [value])
    return compact_record(command, action, value)


def compact_record(command: str, action: str | None, value: dict[str, Any]) -> str:
    if command == "ledger":
        return value["verdict"] if action == "check" else "\t".join(value[k] for k in ("pr", "sha", "verdict"))
    if command == "inbox":
        return f"{value['pointer']['unit']}\t{value['pointer']['status']}\t{value['filename']}"
    if command == "gate":
        return f"{value['id']}\t{value['kind']}" + (f"\t{value['answer']}" if action == "resolve" else "")
    if command == "frontier":
        prs = ",".join(f"{r['branches']}#{r['pr']}@{r['sha']}:{r['state']}" for r in value["prs"]) or "none"
        return f"generation={value['generation']} prs={prs} lowest-unmerged={value['lowestUnmerged'] or 'none'}"
    raise UserError("unknown command")


def main(argv: list[str] | None = None) -> int:
    args = vars(parser().parse_args(argv))
    directory = args.pop("store", os.environ.get("ORCH_STORE"))
    as_json, force = args.pop("json", False), args.pop("force", False)
    command, action = args.pop("command"), args.pop("action", None)
    store = None
    try:
        if directory is None or not directory.strip():
            raise UserError("set --store <dir> or ORCH_STORE")
        if (command, action) == ("frontier", "set") and not (args["repo"] or "").strip():
            raise UserError("set --repo <dir> or ORCH_REPO")
        store = Store(directory, force=force)
        method = command if action is None else command + "_" + action
        if method == "inbox_drain":
            method = "inbox_peek" if args.pop("peek") else method
        value = getattr(store, method)(**args)
        output = value
        if (command, action) == ("inbox", "push"):
            output = value["pointer"]
        if (command, action) == ("inbox", "count"):
            output = {"count": value}
        print(json.dumps(output, indent=2, ensure_ascii=False) if as_json else compact(command, action, value))
        return 0
    except NotFoundError as error:
        if error.output is None:
            print(f"error: {error}", file=sys.stderr)
        else:
            print(json.dumps(error.output, indent=2) if as_json else str(error))
        return 2
    except (UserError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
