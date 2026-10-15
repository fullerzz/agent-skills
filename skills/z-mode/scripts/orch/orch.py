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
from typing import TYPE_CHECKING, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import (
    POINTER_FIELDS,
    UNIT_FIELDS,
    VERDICTS,
    NotFoundError,
    Store,
    UserError,
    count_line,
    positive,
    row_cells,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from store import Frontier, StandingOrder, StatusReport, UnitRow


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


def rows_text(rows: Sequence[Mapping[str, object]], fields: Sequence[str], empty: str, limit: int | None = 4) -> str:
    visible = rows if limit is None else rows[:limit]
    lines = ["\t".join(map(str, row_cells(row, fields))) for row in visible]
    if limit is not None and len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more; use --json")
    return "\n".join(lines) or empty


def units_text(rows: Sequence[UnitRow]) -> str:
    return rows_text(rows, UNIT_FIELDS, "(no units)")


def standing_text(rows: Sequence[StandingOrder]) -> str:
    lines = [f"{r['number']}. {r['line']}" for r in rows[:4]]
    if len(rows) > 4:
        lines.append(f"... {len(rows) - 4} more; use --json")
    return "\n".join(lines) or "(no standing orders)"


def status_text(report: StatusReport) -> str:
    summary = report["summary"]
    ids = summary["openGateIds"]
    suffix = "; ids=" + ",".join(ids[:4]) + (f",+{len(ids) - 4} more" if len(ids) > 4 else "") if ids else ""
    return (
        f"counts: units={len(report['units'])}; states={count_line(summary['unitStates'])}; "
        f"ledger={count_line(summary['ledgerVerdicts'])}\nchanged: {report['changed']}\n"
        f"gates open: {len(ids)}{suffix}"
    )


def frontier_text(frontier: Frontier) -> str:
    prs = ",".join(f"{r['branches']}#{r['pr']}@{r['sha']}:{r['state']}" for r in frontier["prs"]) or "none"
    return f"generation={frontier['generation']} prs={prs} lowest-unmerged={frontier['lowestUnmerged'] or 'none'}"


# Each handler returns the --json value and the compact text for one command.
type Output = tuple[object, str]


def init_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    result = store.init()
    return result, f"initialized {result['store']}"


def status_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    report = store.status()
    return report, status_text(report)


def unit_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "add":
            row = store.unit_add(args.id, args.track, brief=args.brief)
        case "set":
            row = store.unit_set(args.id, args.state, branch=args.branch, pr=args.pr, sha=args.sha)
        case "get":
            row = store.unit_get(args.id)
        case "list":
            rows = store.unit_list(state=args.state, track=args.track)
            return rows, units_text(rows)
        case "counts":
            states = store.unit_counts()
            return states, count_line(states)
        case _:
            raise UserError(f"unknown unit action {action}")
    return row, units_text([row])


def ledger_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "record":
            row = store.ledger_record(args.pr, args.sha, args.verdict, args.evidence, verifier=args.verifier)
            return row, "\t".join((row["pr"], row["sha"], row["verdict"]))
        case "check":
            row = store.ledger_check(args.pr, args.sha)
            return row, row["verdict"]
        case "summary":
            verdicts = store.ledger_summary()
            return verdicts, count_line(verdicts)
        case _:
            raise UserError(f"unknown ledger action {action}")


def inbox_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "push":
            receipt = store.inbox_push(args.agent, args.unit, args.status, report=args.report)
            pointer = receipt["pointer"]
            return pointer, f"{pointer['unit']}\t{pointer['status']}\t{receipt['filename']}"
        case "drain":
            pointers = store.inbox_peek() if args.peek else store.inbox_drain()
            return pointers, rows_text(pointers, POINTER_FIELDS, "(empty)", None)
        case "count":
            count = store.inbox_count()
            return {"count": count}, str(count)
        case _:
            raise UserError(f"unknown inbox action {action}")


def gate_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "park":
            gate = store.gate_park(args.id, args.question, args.options, args.default)
            return gate, f"{gate['id']}\t{gate['kind']}"
        case "list":
            gates = store.gate_list()
            return gates, rows_text(gates, ["id", "question", "options", "defaultAnswer"], "(no open gates)")
        case "resolve":
            resolved = store.gate_resolve(args.id, args.answer)
            return resolved, f"{resolved['id']}\t{resolved['kind']}\t{resolved['answer']}"
        case _:
            raise UserError(f"unknown gate action {action}")


def frontier_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "set":
            if not (args.repo or "").strip():
                raise UserError("set --repo <dir> or ORCH_REPO")
            frontier = store.frontier_set(args.repo, args.prs)
        case "show":
            frontier = store.frontier_show()
        case _:
            raise UserError(f"unknown frontier action {action}")
    return frontier, frontier_text(frontier)


def standing_command(store: Store, action: str | None, args: argparse.Namespace) -> Output:
    match action:
        case "add":
            order = store.standing_add(args.line)
            return order, standing_text([order])
        case "show":
            orders = store.standing_show()
            return orders, standing_text(orders)
        case _:
            raise UserError(f"unknown standing action {action}")


COMMANDS: dict[str, Callable[[Store, str | None, argparse.Namespace], Output]] = {
    "init": init_command,
    "status": status_command,
    "unit": unit_command,
    "ledger": ledger_command,
    "inbox": inbox_command,
    "gate": gate_command,
    "frontier": frontier_command,
    "standing": standing_command,
}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    # The common flags are suppressed when absent so a subcommand cannot reset a value given before it.
    directory = getattr(args, "store", os.environ.get("ORCH_STORE"))
    as_json, force = getattr(args, "json", False), getattr(args, "force", False)
    store = None
    try:
        if directory is None or not directory.strip():
            raise UserError("set --store <dir> or ORCH_STORE")
        store = Store(directory, force=force)
        output, text = COMMANDS[args.command](store, getattr(args, "action", None), args)
        print(json.dumps(output, indent=2, ensure_ascii=False) if as_json else text)
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
