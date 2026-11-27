---
name: papercut
description: "Record zstack friction as a short, private, local report: a wrong instruction, a missing prerequisite, a silent failure, or a needed workaround. List, show, and delete reports, or export one as an editable Markdown issue draft. Use for /papercut, 'record a papercut', or 'record papercuts as you go' during z-mode."
disable-model-invocation: true
---

# Papercut

A papercut is one concrete problem with zstack itself, recorded while the evidence is fresh, even if the task still succeeded. Examples: a skill or playbook gave a wrong instruction, left out a prerequisite, failed silently, errored, or forced a workaround. Bugs in the user's project, host bugs that zstack did not cause, and style preferences are not papercuts.

Reports stay on this machine. Nothing in capture or export uses the network, a browser, a token, or an issue tracker. The helper needs a local secret scanner on `PATH`: BetterLeaks when installed, otherwise gitleaks. It runs the scanner on stdin with its default rules and live validation off, ignoring scanner settings in the environment. Without either scanner, or if a scan fails, nothing is saved or exported.

## When to record

- **Explicit.** The user invokes this skill or asks you to record a papercut. Record that report.
- **Opted in.** During a selected z-mode workflow, the user explicitly asks you to record papercuts as you go. Record each distinct friction point once, with `"capture": "opt-in"`, without asking first. List the saved IDs in your final report. Opt-in lasts only for that workflow in this conversation. It ends when the user declines or says to stop, when z-mode stops or switches style, or when the workflow ends. Put the opt-in, and any opt-out, in resume notes. Forks, workers, and new sessions do not inherit it. Workers report friction to their coordinator, and the coordinator records it.

Installing or enabling zstack, z-mode, or Herdr never opts in. Without one of the two cases above, write nothing.

## Record

Set `PAPERCUT_DIR` to the real parent directory of this `SKILL.md` (resolve links). Run every command with `uv run --offline --no-python-downloads`, so uv never reaches the network; without Python 3.12 or newer installed, the command fails instead of downloading one. Pass one JSON object on stdin. A quoted heredoc keeps the shell from expanding the text:

```sh
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" record <<'EOF'
{"component": "z-mode/playbooks/feature.md", "host": "claude-code", "kind": "missing-prerequisite",
 "summary": "Feature playbook omits the Codex package check",
 "tried": "Followed the feature playbook after adding a skill.",
 "expected": "The playbook names every required check.",
 "actual": "The package check appears only in AGENTS.md, so it was skipped.",
 "blocked": false, "workaround": "Ran uv run scripts/package_plugin.py by hand."}
EOF
```

| Field | Value |
| --- | --- |
| `component` | The zstack skill, playbook, reference, helper, or hook path, such as `baton` or `z-mode/references/native-hosts.md`. One line, at most 80 characters. |
| `host` | `claude-code`, `codex`, `hermes`, or `other`. |
| `kind` | `bad-instruction`, `missing-prerequisite`, `silent-failure`, `tool-error`, or `other`. |
| `summary` | One line, at most 120 characters. It becomes the suggested issue title. |
| `tried`, `expected`, `actual` | What you did, what the instructions led you to expect, and what happened. |
| `blocked` | `true` if the problem stopped progress, otherwise `false`. |
| `workaround` | Optional. What got you past it. |
| `suspected_fix` | Optional. Your untested guess at the fix, kept apart from the observations. |
| `zstack_version` | Optional. The helper reads it from the installed plugin manifest when omitted. |
| `capture` | `explicit` (the default) or `opt-in`. |

Write observations in your own words. Text fields hold up to 1,000 characters and 12 lines, which leaves room for one short quoted error line, not a transcript or log. Never include credentials or proprietary project details. Paths, hosts, and error text that show what zstack did may stay, because the saved report is private local evidence. When it saves a report, the helper removes the credentials the scanner finds. If the scanner still finds one afterward, such as a credential inside base64, nothing is saved. The helper also removes the value of an `Authorization` header that starts with an auth scheme such as `Basic` or `Bearer`, the `name=value` pairs of a `Cookie` header, and the user part of a URL; the scanners miss these shapes. Everything else stays as written. Export redacts much more, as described below.

The helper prints `saved <id>: <path>` only after the report is on disk. Any other result means nothing was saved, and the task continues either way:

- **Explicit capture.** Tell the user it was not saved, and why. If a host sandbox denied the write (`Operation not permitted`, `Permission denied`, or `Read-only file system`), ask once for an unsandboxed rerun through the host's permission flow. If that is refused or unavailable, give the user the command to run outside the sandbox, such as with Claude Code's `!` prefix or in their own terminal.
- **Opted-in capture.** Do not prompt or retry. Stop opted-in writes for this session. In your final report, put `papercut not saved: <reason>` with the report's component and summary. Do not repeat the rest of the report, because it did not pass the scan. The user can ask you to record it again.

## Inspect and delete

```sh
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" list        # oldest first
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" list --component baton
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" list --json # every full report
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" show <id>
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" delete <id> [<id>...]
uv run --offline --no-python-downloads "$PAPERCUT_DIR/scripts/papercut.py" path        # the store directory
```

`list` shows each report's ID, component, kind, whether it blocked progress, and summary. It skips a malformed report file with a warning. `delete` removes each report and its default draft. It handles each ID on its own, reports the ones it could not delete, and finishes a partial delete when rerun. Drafts written with `--output` are the user's files to delete.

To look for repeats, read `list --json` and group reports by component and by what went wrong. Report the groups and their IDs. Do not merge or delete reports unless the user asks.

## Export

`export <id>` writes `<store>/drafts/<id>.md`, or the file given with `--output`. It refuses to replace an existing draft, because the user may have edited it, unless they ask you to pass `--force`. A forced export swaps in the new draft only once it is fully written, so a failed write leaves the old draft in place. The draft opens with an HTML comment that holds the suggested title and a review reminder, followed by the issue body.

Give the user the draft's path and suggested title, and ask them to check it for sensitive details the scrub missed. Export redacts aggressively and accepts losing harmless text. The scanner removes credentials first. Then each word is checked on its own and replaced if it is any of these:

- a path, including one split by spaces;
- a URL other than this repository's public links;
- an email or anything else with `@`;
- a `name:number` other than a file reference such as `SKILL.md:12`;
- a domain name;
- the value of a `key=value`;
- a long mixed-case token;
- the word after a credential key, a credential flag such as `--token`, or a session ID label.
- any of these inside angle brackets, such as a Markdown autolink.

So `exit:127` becomes `<host>`, and `Passwordless=true` loses its value. Finally the scanner checks the finished draft, and any finding stops the export before anything is written. The user restores what they want while editing. Redaction is still best-effort. Never file the report: no `gh issue create`, API call, prefilled issue URL, or browser. The user edits the draft and decides whether to file it. The zstack repository does not accept external issues, so its maintainer files their own reports by hand.

## Store

Reports live in `$ZSTACK_PAPERCUT_DIR` when it is set to an absolute path. Otherwise they live in `$XDG_STATE_HOME/zstack/papercuts`, which defaults to `~/.local/state/zstack/papercuts`, or `%LOCALAPPDATA%\zstack\papercuts` on Windows. The helper refuses any of these inside a Git checkout or the zstack install tree. It ignores a repository rooted at your home directory or above, such as a dotfiles repository. Each report is one owner-only JSON file under `reports/`, and drafts go under `drafts/`. The helper creates missing directories as owner-only and leaves the mode of an existing directory alone. Commands that read or write reports refuse the store when its `reports/` or `drafts/` is a symbolic link, and `--output` cannot point into the store outside `drafts/`. Export and delete take a lock in the store, so they cannot remove or leave behind each other's drafts. On Windows, owner-only modes are not enforced; privacy there comes from `%LOCALAPPDATA%` being per-user. The store belongs to the operating-system user, so Claude Code, Codex, and Hermes on one machine share it. It is not synced to other machines. Because it sits outside checkouts and plugin install trees, reports survive new sessions, plugin refreshes, and reinstalls. Delete the directory to remove every report.
