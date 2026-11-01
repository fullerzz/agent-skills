# Use Herdr with existing workflows

Zstack selects the playbook and owns session preferences. The installed **herdr-zstack:hc-workflow** companion owns native hc execution, including preflight, workers, collection, pause, pickup and cleanup. Start with [herdr-zstack installation](https://github.com/fullerzz/herdr-zstack/blob/main/docs/installation.md), then read its [hc-workflow skill](https://github.com/fullerzz/herdr-zstack/blob/main/skills/hc-workflow/SKILL.md) and [execution contract](https://github.com/fullerzz/herdr-zstack/blob/main/docs/execution-contract.md).

## Enable it for a session

Start the coordinator in a live hc terminal and explicitly select z-mode with Herdr:

| Host | Example invocation |
| --- | --- |
| Codex plugin | Select `zstack:z-mode` and say “Use Herdr execution for this session.” |
| Claude Code plugin | `/zstack:z-mode Use Herdr execution for this session.` |
| Hermes | `Load zstack:z-mode with skill_view and enable Herdr execution for this session.` |

Linked installations use `$z-mode` in Codex or `/z-mode` in Claude Code. The `herdr-workflow` compatibility entrypoint can select execution without activating z-mode when explicitly requested. Loading a skill or discussing Herdr does not enable execution.

The session hook resolves the installed companion through its host's installation records, or reports a capability gap for missing or ambiguous installs. Resolve other layouts through the host catalog. Read the resolved installed skill before operating; never substitute legacy commands. Enabling the preference does not attach an outside session to hc.

## Session preferences

“Disable Herdr execution” selects native execution while retaining z-mode. “Stop z-mode” clears both preferences. Native hooks remember selection for the same session ID; new sessions and children need their own explicit selection. Linked installations without hooks preserve it conversationally. Controls change preferences, not processes; reconcile assigned workers before changing execution methods.

The selected playbook still decides scope, whether to delegate, ownership and acceptance. Small work and brief checks stay direct. Follow the [shared host contract](../../skills/z-mode/references/native-hosts.md#execution-selection) for permissions, concurrency and fallback boundaries.

## Pause, pickup and cleanup

Use the installed companion's [operations](https://github.com/fullerzz/herdr-zstack/blob/main/skills/hc-workflow/references/operations.md#pause-and-pickup) and [worker lifecycle](https://github.com/fullerzz/herdr-zstack/blob/main/docs/worker-lifecycle.md). Reconcile live assignments before input; never replay a saved brief automatically. See [long work and handoffs](04-long-work.md) for zstack's handoff requirements and [validation](../validation.md#legacy-herdr-retirement) for actual coverage.

## Codex launch requirements {#known-codex-shared-daemon-issue}

Follow the companion's current [launch instructions](https://github.com/fullerzz/herdr-zstack/blob/main/skills/hc-workflow/references/operations.md#3-launch) for Codex flags and host readiness. The earlier local plugin proposal is retained only as an [archived snapshot](../archive/herdr-plugin-plan.md).
