# The skill guide

Start with a concrete goal and an observable done condition. Examples show both hosts: Claude Code uses slash syntax, such as `/how`, and Codex uses a dollar sign, such as `$how`. With the native plugins, use the namespaced equivalent: `zstack:how` in the Codex skill picker or `/zstack:how` in Claude Code. See [installation choices](01-setup.md#install).

## How the library works

[Explore the visual guide](visual-guide.md) for an interactive component map, task walkthroughs, and installation diagrams.

A skill is a set of instructions that your coding agent reads, together with any referenced prompts or helper scripts. Invoking a skill gives the agent a process for your request. The host supplies the model, tools, permissions, and any subagents; installing the library does not configure those capabilities.

Use a named skill for a specific job, such as `$how` to trace behavior. Use `$z-mode` for an engineering task: it selects a playbook for the kind of work and reads relevant principles as decisions arise. Playbooks describe workflows; principles guide decisions within those workflows. They are not background services. The mode can work directly or delegate where the selected workflow and host allow it.

The [workflow skill reference](../reference/workflow-skills.md) explains each skill's inputs, process, and results. The [playbook reference](../reference/playbooks.md) gives task examples, and the [principle reference](../reference/principles.md) shows the decisions each principle affects.

To run authorized workers and useful long-running processes in Herdr, follow [Use Herdr with existing workflows](herdr.md). Explicit execution selection applies alongside the normal playbook and its companions.

## Choose a workflow

<Workflow />

| Step | Page | Key skills |
| --- | --- | --- |
| 1 | [Install and route work](01-setup.md) | setup-zstack, z-mode |
| 2 | [Understand and design](02-understand-and-design.md) | how, why, teach, recall, architect, arena, swarm, interrogate |
| 3 | [Build and verify](03-build-and-verify.md) | tdd, no-comments, unslop, create-verification-skill |
| 4 | [Long work and conventions](04-long-work.md) | autonomous-run, pause-safely, orchestrate, automate-me, reflect |
| 5 | [Principles and recipes](05-principles-and-recipes.md) | The 24 principles, example prompts |

Every skill and playbook is listed in the [skill catalog](../skills.md).
