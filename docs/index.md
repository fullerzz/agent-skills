---
layout: home

hero:
  name: zstack
  text: Engineering workflows for Codex and Claude Code
  tagline: A personal skill library adapted from Lauren Tan's pstack. One shared source, native agents on each host.
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
    - theme: alt
      text: Install
      link: /guide/01-setup

features:
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/></svg>
    title: Shared skills
    details: 48 skills, 24 engineering principles, and 23 workflow playbooks live once in skills/ and serve both hosts.
    link: /skills
    linkText: Browse the catalog
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3"/><path d="M13 15h4"/></svg>
    title: Native agents
    details: Each host uses its own native agent roles and model configuration.
    link: /guide/01-setup#host-differences
    linkText: Compare hosts
  - icon: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
    title: Safe installer
    details: Previews every file, refuses collisions, and never changes model or permission configuration.
    link: /guide/01-setup#install
    linkText: Install
---

## Quick install

Install Git, uv, and your chosen host first; uv resolves Python 3.14+ and the installer's dependencies. Clone to a stable location because installed skills link back to it:

```sh
git clone https://github.com/fullerzz/agent-skills.git "$HOME/Code/agent-skills"
cd "$HOME/Code/agent-skills"
```

Preview first, resolve any collisions, then apply. Start a new host session afterward.

::: code-group

```sh [Claude Code]
uv run scripts/install.py --host claude
uv run scripts/install.py --host claude --apply
```

```sh [Codex]
uv run scripts/install.py --host codex
uv run scripts/install.py --host codex --apply
```

:::

Use `--host both` for both hosts, or add `--project "/absolute/path/to/project"` for an existing project. Check discovery with `$how` in Codex or `/how` in Claude Code. See [first-time setup, updates, and safe removal](./guide/01-setup.md) before moving the checkout.

## Workflow

Each step links to its guide section.

<Workflow />
