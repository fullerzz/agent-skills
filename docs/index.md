---
layout: home

hero:
  name: zstack
  text: Engineering workflows for Codex, Claude Code, and Hermes
  tagline: A personal skill library adapted from Lauren Tan's pstack. Shared skills and native plugins for three hosts, plus linked installation for Codex and Claude Code.
  image:
    src: /logo.svg
    alt: Stacked layers logo
  actions:
    - theme: brand
      text: Read the guide
      link: /guide/
    - theme: alt
      text: Explore the visual guide
      link: /guide/visual-guide
    - theme: alt
      text: Browse skills
      link: /skills

features:
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/></svg>
    title: Shared skills
    details: 50 skills, 24 engineering principles, and 23 workflow playbooks live once in skills/ and serve all three hosts.
    link: /skills
    linkText: Browse the catalog
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3"/><path d="M13 15h4"/></svg>
    title: Native plugins
    details: Namespaced skills for Codex, Claude Code, and Hermes. Codex and Claude Code also provide a session hook for explicitly selected z-mode.
    link: /guide/01-setup#install
    linkText: Choose a plugin
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
    title: Safe installer
    details: Previews every file, refuses collisions, and never changes model or permission configuration.
    link: /guide/01-setup#install
    linkText: Install
---

## Quick install

Install Git, uv, and your chosen host first; uv resolves Python 3.14+ and the installer's dependencies. Clone the library; linked installations need a stable checkout path:

```sh
git clone https://github.com/fullerzz/agent-skills.git "$HOME/Code/agent-skills"
cd "$HOME/Code/agent-skills"
```

Use the native plugin commands for your host. Start a new host session afterward. Existing linked users should follow the [Codex](./hosts/codex.md#native-plugin) or [Claude Code](./hosts/claude-code.md#native-plugin) migration steps first.

::: code-group

```sh [Claude Code plugin]
claude plugin marketplace add "$PWD"
claude plugin install zstack@zstack-local
```

```sh [Codex plugin]
uv run scripts/package_plugin.py
codex plugin marketplace add "$PWD"
codex plugin add zstack@zstack-local
```

```sh [Hermes plugin]
hermes plugins install fullerzz/agent-skills --no-enable
hermes plugins enable zstack
```

:::

In Hermes, ask to load `zstack:how` with `skill_view`. Decline any Node dependency prompt; the plugin does not need the docs site's dependencies. See [Hermes setup](./hosts/hermes.md) for installation from a draft PR and manual checks.

Select `zstack:how` in the Codex skill picker or invoke `/zstack:how` in Claude Code to check discovery. Review Codex hook trust separately; installation does not activate z-mode. See plugin setup, updates, and removal for [Codex](./hosts/codex.md#native-plugin) and [Claude Code](./hosts/claude-code.md#native-plugin).

The [linked installer](./guide/01-setup.md#linked-installer) supports both hosts with `--host both` and project scope with `--project "/absolute/path/to/project"`. It installs native agent copies; the Codex plugin does not. See [updates and safe removal](./guide/01-setup.md) before moving a linked checkout.

## Workflow

Each step links to its guide section.

<Workflow />
