"""Read-only GitHub or GitLab PR watcher CLI. NDJSON is the default output."""

from __future__ import annotations

import argparse
import math
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from typing import TYPE_CHECKING, TextIO

from github import GitHubReader, QueryError, Reader, order_stack, parse_remote, pr_number, resolve_context, run
from gitlab import GitLabReader, parse_gitlab_remote
from policy import Clock, Options, WatchClock, run_queued, run_simple, status_query_verdict, verdict_factory
from render import render_json, render_pretty

if TYPE_CHECKING:
    from schema import Context, Event, Mode, Verdict


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
    values = [integer(part.strip().removeprefix("#")) for part in value.split(",")]
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("contains a duplicate PR")
    return values


def gitlab_host(origin: str, forge: str | None, env_host: str | None) -> str | None:
    """Return the GitLab host to watch, or None to watch GitHub; forge None means auto-detect from origin."""
    parsed = parse_gitlab_remote(origin)
    # parse_remote rejects explicit ports, so also recognize a github.com origin by its hostname.
    github_origin = parse_remote(origin) is not None or (parsed is not None and parsed[0].split(":")[0] == "github.com")
    if forge == "github" or (forge is None and github_origin):
        return None
    # A forced GitLab watch from a GitHub checkout must not reuse github.com as the GitLab host.
    if not github_origin and parsed is not None and (forge == "gitlab" or "gitlab" in parsed[0]):
        return parsed[0]
    if forge is None:
        return None
    return (env_host or "").strip().split("://", 1)[-1].rstrip("/") or "gitlab.com"


def origin_url() -> str:
    try:
        result = run(["git", "remote", "get-url", "origin"])
    except QueryError:
        return ""
    return result.stdout if result.returncode == 0 else ""


def detect_reader(forge: str | None) -> Reader:
    host = None if forge == "github" else gitlab_host(origin_url(), forge, os.environ.get("GITLAB_HOST"))
    return GitHubReader() if host is None else GitLabReader(host)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="watch-pr", description=__doc__, allow_abbrev=False)
    parser.add_argument("--forge", choices=("github", "gitlab"), help="default: detect from the origin remote")
    parser.add_argument("--owner", help="owner or GitLab namespace, such as group/subgroup")
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
    reader, clock = reader or detect_reader(args.forge), clock or Clock()
    mode: Mode = "queued-stack" if args.queued_stack else "stack" if args.stack else "single"
    options = Options(
        interval=args.interval,
        sweep_interval=args.sweep_interval,
        timeout=args.timeout,
        max_query_errors=args.max_query_errors,
        allow_draft=args.allow_draft,
    )
    render = partial(render_pretty, forge=reader) if args.pretty else render_json

    def emit(event: Event) -> None:
        stdout.write(render(event))
        stdout.flush()

    try:
        seed = resolve_context(
            reader, args.owner, args.repo, args.pr or (args.stack_prs[0] if args.stack_prs else None)
        )
        contexts: list[Context] = (
            [{**seed, "number": n} for n in args.stack_prs]
            if args.stack_prs
            else [seed]
            if mode == "single"
            else order_stack(seed, reader.open_pull_requests(seed))
        )
    except QueryError as error:
        verdict: Verdict = status_query_verdict(verdict_factory(clock, mode), 1, error.failure)
    else:
        verdict = (
            run_queued(reader, clock, emit, contexts, options)
            if mode == "queued-stack" and not args.status_only
            else run_simple(reader, clock, emit, contexts, options, mode, args.status_only)
        )
    emit(verdict)
    return verdict["exitCode"]
