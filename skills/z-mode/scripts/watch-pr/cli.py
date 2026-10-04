"""Read-only PR watcher CLI. NDJSON is the default output."""

from __future__ import annotations

import argparse
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, TextIO

from github import GitHubReader, QueryError, Reader, order_stack, pr_number, resolve_context
from policy import Clock, WatchClock, run_queued, run_simple, status_query_verdict, verdict_factory
from render import render_json, render_pretty


def number(value: str, allow_zero: bool = False) -> float:
    try:
        result = float(value)
        if not math.isfinite(result) or result < 0 or (not allow_zero and result == 0):
            raise ValueError()
        return result
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "must be nonnegative" if allow_zero else "must be greater than zero"
        ) from error


def integer(value: str) -> int:
    try:
        result = number(value)
        if not result.is_integer():
            raise ValueError()
        return pr_number(int(result))
    except (ValueError, argparse.ArgumentTypeError) as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error


def prs(value: str) -> list[int]:
    values = [integer(part.removeprefix("#")) for part in value.split(",")]
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("contains a duplicate PR")
    return values


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="watch-pr", description=__doc__, allow_abbrev=False)
    parser.add_argument("--owner")
    parser.add_argument("--repo")
    parser.add_argument("--pr", type=lambda v: integer(v.removeprefix("#")))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--stack", action="store_true")
    modes.add_argument("--queued-stack", action="store_true")
    parser.add_argument("--stack-prs", type=prs)
    parser.add_argument("--interval", type=number, default=60)
    parser.add_argument("--sweep-interval", type=number, default=300)
    parser.add_argument("--timeout", type=lambda v: number(v, True), default=0)
    parser.add_argument("--max-query-errors", type=integer, default=5)
    for flag in ("status-only", "allow-draft", "pretty"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(argv)
    if args.stack_prs is not None and not args.queued_stack:
        parser.error("--stack-prs requires --queued-stack")
    return args


def main(
    argv: list[str] | None = None,
    *,
    reader: Reader | None = None,
    clock: WatchClock | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            args = parse_args(argv)
    except SystemExit as error:
        return 0 if error.code == 0 else 64
    reader, clock = reader or GitHubReader(), clock or Clock()
    mode = "queued-stack" if args.queued_stack else "stack" if args.stack else "single"
    options = {
        "interval": args.interval,
        "sweepInterval": args.sweep_interval,
        "timeout": args.timeout,
        "maxQueryErrors": args.max_query_errors,
        "allowDraft": args.allow_draft,
    }
    render = render_pretty if args.pretty else render_json

    def emit(event: dict[str, Any]) -> None:
        stdout.write(render(event))
        stdout.flush()

    try:
        seed = resolve_context(
            reader, args.owner, args.repo, args.pr or (args.stack_prs[0] if args.stack_prs else None)
        )
        contexts = (
            [seed | {"number": n} for n in args.stack_prs]
            if args.stack_prs
            else [seed]
            if mode == "single"
            else order_stack(seed, reader.open_pull_requests(seed))
        )
    except QueryError as error:
        verdict = status_query_verdict(verdict_factory(clock, mode), 1, error.failure)
    else:
        verdict = (
            run_queued(reader, clock, emit, contexts, options)
            if mode == "queued-stack" and not args.status_only
            else run_simple(reader, clock, emit, contexts, options, mode, args.status_only)
        )
    emit(verdict)
    return verdict["exitCode"]
