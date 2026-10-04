"""Human and machine renderers for the same watcher events."""

from __future__ import annotations

import json
from typing import Any


def render_json(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


def status_table(rows: list[dict[str, Any]]) -> str:
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
                ci = "❌ GitHub reports failing checks" + was
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
        url = f"https://github.com/{context['owner']}/{context['repo']}/pull/{context['number']}"
        lines.append(f"| [#{context['number']}]({url}) | {ci} | {review} | {merge} |")
    return "\n".join(lines) + "\n"


def blocker_text(blocker: dict[str, Any]) -> str:
    kind = blocker["kind"]
    if kind == "status-query":
        return (
            f"BLOCKER: status-query\nfailures={blocker['failures']}\n"
            f"detail={blocker['failure']['detail']}\n"
            "action=verify current PR context, GitHub authentication, and API availability, then rearm"
        )
    lines = [f"BLOCKER: {blocker['reason'] if kind == 'merge-gate' else kind}", f"pr={blocker['pr']['number']}"]
    if kind == "merge-conflicts":
        lines += [
            f"mergeable={blocker['facts']['mergeable']}",
            f"mergeStateStatus={blocker['facts']['mergeStateStatus']}",
            "action=resolve merge conflicts before waiting for CI",
        ]
    elif kind == "review-threads":
        lines.append(f"unresolved={len(blocker['threads'])}")
        for thread in blocker["threads"]:
            c = thread["firstComment"] or {}
            body = c.get("body", "").split("\n")[0].removesuffix("\r")[:180]
            lines.append(
                f"{thread['id']} {c.get('path')} {c.get('line')} {c.get('authorLogin')} "
                f"isBugBot={str(thread['isBugbot']).lower()} bugbotReviewPasses={thread['bugbotReviewPasses']} {body}"
            )
    elif kind == "failing-checks":
        ci = blocker["ci"]
        lines.append(f"failed={len(ci['failed'])}")
        lines += [f"{c['name']} {c['reportedState']} {c['description']} {c['link']}" for c in ci["failed"]]
        if ci["kind"] == "ci-github-rejected":
            lines += [
                f"mergeStateStatus={ci['github']['mergeStateStatus']}",
                f"headRollupState={ci['github']['headRollupState']}",
            ]
    elif kind == "merge-gate":
        actions = {
            "closed-without-merge": "restore or remove the closed PR from the queued stack",
            "draft-pr": "mark the PR ready for review before waiting for the merge queue",
            "changes-requested": "resolve the changes-requested review before waiting for the merge queue",
        }
        lines.append("action=" + actions[blocker["reason"]])
    return "\n".join(lines)


def plural(n: int) -> str:
    return "" if n == 1 else "s"


def render_ready(event: dict[str, Any]) -> str:
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


def render_timeout(event: dict[str, Any]) -> str:
    reason = event["reason"]
    if reason["kind"] == "pending-checks":
        return "TIMEOUT: checks still pending\n"
    if reason["kind"] == "status-unavailable":
        return "TIMEOUT: GitHub status remained unavailable\n"
    n = reason["unmergedCount"]
    return f"TIMEOUT: queued stack still has {n} PR{plural(n)} unmerged; frontier=#{reason['frontier']['number']}\n"


def render_waiting(event: dict[str, Any]) -> str:
    reason, n = event["reason"], event["frontier"]["number"]
    if reason["kind"] == "pending-checks":
        count = len(reason["pending"])
        return f"WAITING: frontier=#{n}; {count} check{plural(count)} pending\n"
    count = reason["unmergedCount"]
    return f"WAITING: frontier=#{n} is blocker-free; waiting for merge queue ({count} PR{plural(count)} unmerged)\n"


def render_pretty(event: dict[str, Any]) -> str:
    kind = event["kind"]

    if kind == "STATUS":
        return status_table(event["rows"])
    if kind == "QUEUE":
        n = len(event["queue"])
        return (
            f"QUEUE: captured {n} PR{plural(n)} bottom-to-top: "
            + ",".join(f"#{c['number']}" for c in event["queue"])
            + "\n"
        )
    if kind == "WAITING":
        return render_waiting(event)
    if kind == "ADVANCE":
        return (
            f"ADVANCE: merged #{event['merged']['number']}; next=#{event['frontier']['number']}; "
            f"remaining={event['remaining']}\n"
        )
    if kind == "RETRY":
        return (
            f"RETRY: GitHub status query failed; retrying in {event['retryInSeconds']:g}s\n"
            f"detail={event['failure']['detail']}\n"
        )
    if kind == "BLOCKER":
        return blocker_text(event["blocker"]) + "\n"
    if kind == "READY":
        return render_ready(event)
    if kind == "COMPLETE":
        n = len(event["queue"])
        return f"COMPLETE: queued stack merged ({n} PR{plural(n)})\n"
    if kind == "TIMEOUT":
        return render_timeout(event)
    raise ValueError(f"unknown verdict {kind}")
