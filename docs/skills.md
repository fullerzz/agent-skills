<script setup>
import { data } from './skills.data'
import { withBase } from 'vitepress'
</script>

# Skill catalog

Every skill, principle, and z-mode playbook in this library, read from the source files at build time. Skills are explicit-only unless marked <Badge type="tip" text="model-invocable" />: invoke them by name, such as `/how` in Claude Code or `$how` in Codex. Playbooks load through [z-mode](#z-mode).

Select an entry for examples, how it works, expected results, and requirements. Each reference includes a link to the underlying instructions.

## Workflow skills

<div class="catalog">
  <a v-for="s in data.skills" :id="s.id" :key="s.id" class="catalog-card no-icon" :href="withBase(s.guide)">
    <span class="catalog-name">{{ s.name }} <Badge v-if="s.modelInvocable" type="tip" text="model-invocable" /></span>
    <span class="catalog-desc">{{ s.description }}</span>
  </a>
</div>

## Principles

Principles are leaves that z-mode reads when they change a decision. See [Use principles](./guide/05-principles-and-recipes.md).

<div class="catalog">
  <a v-for="s in data.principles" :id="s.id" :key="s.id" class="catalog-card no-icon" :href="withBase(s.guide)">
    <span class="catalog-name">{{ s.name }}</span>
    <span class="catalog-desc">{{ s.description }}</span>
  </a>
</div>

## Playbooks

The z-mode router selects a playbook from the request.

<div class="catalog">
  <a v-for="s in data.playbooks" :id="s.id" :key="s.id" class="catalog-card no-icon" :href="withBase(s.guide)">
    <span class="catalog-name">{{ s.name }}</span>
    <span class="catalog-desc">{{ s.description }}</span>
  </a>
</div>
