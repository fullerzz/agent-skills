---
outline: [2, 3]
---

<script setup>
import StackMap from '../.vitepress/theme/StackMap.vue'
import TaskRoute from '../.vitepress/theme/TaskRoute.vue'
import InstallMap from '../.vitepress/theme/InstallMap.vue'
</script>

# How zstack fits together

zstack is an instruction library for your coding agent. It connects a goal to a workflow, the guidance needed for decisions, and checks of the result. The host—Codex or Claude Code—provides execution capabilities.

Use these maps to explore three different questions: what each component does, how a request moves through a workflow, and where installed files live. The controls only change the illustrations; they never execute commands.

## The component map

**Skills define processes. Playbooks sequence work. Principles guide decisions.** z-mode connects them for an engineering task. You can also invoke a focused skill directly without using the mode.

<StackMap />

### Reading the connections

- **Request to instructions:** `$how` asks for a focused behavior trace; `$z-mode` selects a workflow for a broader task. Claude Code uses `/how` and `/z-mode`.
- **Mode to playbook:** the mode reads the selected playbook, not every workflow. A playbook can call for companion skills and relevant principles.
- **Instructions to execution:** the host executes within its available tools and permissions. A native role is a scoped worker, not a second workflow engine. The parent waits for terminal results and inspects artifacts.
- **Execution to evidence:** a test exit, observed UI behavior, or cited source supports the result. Starting a worker or writing a test does not prove the outcome.

Explore the [workflow skills](../reference/workflow-skills.md), [playbooks](../reference/playbooks.md), and [principles](../reference/principles.md) for the full contracts. If delegation is unavailable, the agent works directly and discloses missing independent coverage.

## Follow a request

Choose a task to see its input, selected playbook, main steps, decision guidance, and output. These are representative examples; z-mode has other routes for performance, reviews, queues, and more.

<TaskRoute />

### Evidence controls the next step

The path is not always linear. A failed repro sends a bug fix back to tracing. An unavailable tool leaves an explicit proof gap. A resumed session rechecks the current files and branch before trusting a saved handoff.

Publication is a separate requested action. Passing local checks does not grant permission to commit, push, open a PR, merge, or deploy. See [build and verify](03-build-and-verify.md) and [long work and handoffs](04-long-work.md).

## From checkout to host

**For linked installations, skills are linked and agents are copied.** Switch hosts and installation scopes to see why the stable checkout, discovery directories, and ownership receipt all matter.

<InstallMap />

The [native Codex plugin](../hosts/codex.md#native-plugin) uses a different path: checkout → `dist/zstack` → Codex plugin cache. It packages skills and a session hook, with no installer receipt or bundled agent registration. Rebuild and refresh the plugin to apply checkout changes. The [Claude Code plugin](../hosts/claude-code.md#native-plugin) loads skills, the hook, and both agent roles in place from the checkout; changes apply at the next session or `/reload-plugins`.

The installed link leads back to the real skill directory for references and helpers. Commands that operate on your product still run in the target repository. The library checkout and the target project can live in entirely different places.

Follow [install and route work](01-setup.md) for collision handling, updates, removal, and checkout relocation. The [Codex](../hosts/codex.md) and [Claude Code](../hosts/claude-code.md) pages cover native configuration and discovery limits.
