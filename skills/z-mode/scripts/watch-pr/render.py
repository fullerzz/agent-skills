"""Human and machine renderers for the same watcher events."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, assert_never

if TYPE_CHECKING:
    from schema import Blocker, Context, Event, ReadyVerdict, Snapshot, TimeoutVerdict, WaitingEvent


class Forge(Protocol):
    forge: str

    def web_url(self, context: Context) -> str: ...


def render_json(event: Event) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


def status_table(rows: list[Snapshot], forge: Forge) -> str:
    lines = ["| PR | CI | Review | Merge |", "| --- | --- | --- | --- |"]
    for row in rows:
        context = row["context"]
        if row["kind"] != "open":
            ci, review, merge = "—", "—", "✅ merged" if row["kind"] == "merged" else "❌ closed"
        else:
            c, facts = row["ci"], row["facts"]
            was = ", was ✅" if c["hadPreviousPassingCi"] else ""
            if c["kind"] == "ci-clean":
                ci = "✅"
            elif c["kind"] == "ci-pending":
                ci = f"⏳ {len(c['pending'])} pending{was}"
            elif c["kind"] == "ci-failing":
                ci = f"❌ {len(c['failed'])} failed" + (f", {len(c['pending'])} pending" if c["pending"] else "") + was
            else:
                ci = f"❌ {forge.forge} reports failing checks" + was
            n = len(row["threads"])
            review = (
                ("🤖 running" + (f", {n} open" if n else ""))
                if row["reviewAutomationRunning"]
                else f"📝 {n} open"
                if n
                else "✅"
            )
            merge = (
                "⏸ draft"
                if facts["isDraft"]
                else "⚠️ changes requested"
                if facts["reviewDecision"] == "CHANGES_REQUESTED"
                else "⚠️ conflict"
                if facts["mergeable"] == "CONFLICTING" or facts["mergeStateStatus"] in ("DIRTY", "CONFLICTING")
                else "✅"
            )
        lines.append(f"| [#{context['number']}]({forge.web_url(context)}) | {ci} | {review} | {merge} |")
    return "\n".join(lines) + "\n"


def blocker_text(blocker: Blocker, forge: Forge) -> str:
    if blocker["kind"] == "status-query":
        return (
            f"BLOCKER: status-query\nfailures={blocker['failures']}\n"
            f"detail={blocker['failure']['detail']}\n"
            f"action=verify current PR context, {forge.forge} authentication, and API availability, then rearm"
        )
    title = blocker["reason"] if blocker["kind"] == "merge-gate" else blocker["kind"]
    lines = [f"BLOCKER: {title}", f"pr={blocker['pr']['number']}"]
    if blocker["kind"] == "merge-conflicts":
        lines += [
            f"mergeable={blocker['facts']['mergeable']}",
            f"mergeStateStatus={blocker['facts']['mergeStateStatus']}",
            "action=resolve merge conflicts before waiting for CI",
        ]
    elif blocker["kind"] == "review-threads":
        lines.append(f"unresolved={len(blocker['threads'])}")
        for thread in blocker["threads"]:
            c = thread["firstComment"]
            path, line, author = (c["path"], c["line"], c["authorLogin"]) if c else (None, None, None)
            body = c["body"].split("\n")[0].removesuffix("\r")[:180] if c else ""
            lines.append(
                f"{thread['id']} {path} {line} {author} "
                f"isBugBot={str(thread['isBugbot']).lower()} bugbotReviewPasses={thread['bugbotReviewPasses']} {body}"
            )
    elif blocker["kind"] == "failing-checks":
        ci = blocker["ci"]
        lines.append(f"failed={len(ci['failed'])}")
        lines += [f"{c['name']} {c['reportedState']} {c['description']} {c['link']}" for c in ci["failed"]]
        if ci["kind"] == "ci-github-rejected":
            lines += [
                f"mergeStateStatus={ci['github']['mergeStateStatus']}",
                f"headRollupState={ci['github']['headRollupState']}",
            ]
    elif blocker["kind"] == "merge-gate":
        actions = {
            "closed-without-merge": "restore or remove the closed PR from the queued stack",
            "draft-pr": "mark the PR ready for review before waiting for the merge queue",
            "changes-requested": "resolve the changes-requested review before waiting for the merge queue",
        }
        lines.append("action=" + actions[blocker["reason"]])
    # Empty trailing fields (a thread without a comment, a check without a link) would leave trailing spaces.
    return "\n".join(line.rstrip() for line in lines)


def plural(n: int) -> str:
    return "" if n == 1 else "s"


def render_ready(event: ReadyVerdict) -> str:
    detail = ""
    if event["scope"]["kind"] == "single" and event["scope"]["pr"]["kind"] == "ready-pr":
        proof = event["scope"]["pr"]["proof"]
        draft = proof["gate"]["draft"] == "draft-allowed"
        review = proof["gate"]["reviewDecision"]
        detail = (
            f"\nmergeStateStatus={proof['ci']['github']['mergeStateStatus']}\n"
            f"reviewDecision={'null' if review is None else review}\nisDraft={str(draft).lower()}"
        )
        if draft:
            detail += "\nnote=draft allowed (--allow-draft); leave draft — do not mark ready"
    return "READY: no merge conflicts, no unresolved review threads, no failing or pending checks" + detail + "\n"


def render_timeout(event: TimeoutVerdict, forge: Forge) -> str:
    reason = event["reason"]
    if reason["kind"] == "pending-checks":
        return "TIMEOUT: checks still pending\n"
    if reason["kind"] == "status-unavailable":
        return f"TIMEOUT: {forge.forge} status remained unavailable\n"
    n = reason["unmergedCount"]
    return f"TIMEOUT: queued stack still has {n} PR{plural(n)} unmerged; frontier=#{reason['frontier']['number']}\n"


def render_waiting(event: WaitingEvent) -> str:
    reason, n = event["reason"], event["frontier"]["number"]
    if reason["kind"] == "pending-checks":
        count = len(reason["pending"])
        return f"WAITING: frontier=#{n}; {count} check{plural(count)} pending\n"
    count = reason["unmergedCount"]
    return f"WAITING: frontier=#{n} is blocker-free; waiting for merge queue ({count} PR{plural(count)} unmerged)\n"


def render_pretty(event: Event, forge: Forge) -> str:
    if event["kind"] == "STATUS":
        return status_table(event["rows"], forge)
    if event["kind"] == "QUEUE":
        n = len(event["queue"])
        return (
            f"QUEUE: captured {n} PR{plural(n)} bottom-to-top: "
            + ",".join(f"#{c['number']}" for c in event["queue"])
            + "\n"
        )
    if event["kind"] == "WAITING":
        return render_waiting(event)
    if event["kind"] == "ADVANCE":
        return (
            f"ADVANCE: merged #{event['merged']['number']}; next=#{event['frontier']['number']}; "
            f"remaining={event['remaining']}\n"
        )
    if event["kind"] == "RETRY":
        return (
            f"RETRY: {forge.forge} status query failed; retrying in {event['retryInSeconds']:g}s\n"
            f"detail={event['failure']['detail']}\n"
        )
    if event["kind"] == "BLOCKER":
        return blocker_text(event["blocker"], forge) + "\n"
    if event["kind"] == "READY":
        return render_ready(event)
    if event["kind"] == "COMPLETE":
        n = len(event["queue"])
        return f"COMPLETE: queued stack merged ({n} PR{plural(n)})\n"
    if event["kind"] == "TIMEOUT":
        return render_timeout(event, forge)
    assert_never(event)
