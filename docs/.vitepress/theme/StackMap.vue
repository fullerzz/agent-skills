<script setup lang="ts">
import { withBase } from 'vitepress'
import './visuals.css'

const layers = [
  { name: 'Workflow skills', role: 'Give a named job a repeatable process', examples: 'how · why · architect · tdd · recall', detail: 'Invoke a focused skill directly, or let the explicitly selected mode read a relevant companion. Each SKILL.md supplies instructions; references and scripts support that process.', link: '/reference/workflow-skills' },
  { name: 'z-mode', role: 'Route an engineering request', examples: 'One selected workflow, task-sized context', detail: 'The mode chooses the matching playbook and loads principle leaves when they affect a decision. Small work runs directly. The mode persists in conversation until you stop it; a handoff carries that context into another session.', link: '/reference/workflow-skills#z-mode' },
  { name: 'Playbooks', role: 'Describe the steps for this kind of work', examples: 'investigation · bug-fix · feature · pause-safely', detail: 'A bug starts with reproduction; an investigation stays read-only; a feature starts with observable acceptance. Playbooks live under z-mode and are read as workflow instructions, not installed as separate commands.', link: '/reference/playbooks' },
  { name: 'Principles', role: 'Guide decisions inside the workflow', examples: 'fix root causes · prove it works · boundary discipline', detail: 'Principle skills are decision guidance, loaded only when relevant. They do not add authority or require every task to run through every principle.', link: '/reference/principles' },
]
</script>

<template>
  <figure class="z-visual" aria-label="zstack component relationships">
    <div class="z-request"><strong>Your request</strong><span>Goal + scope + observable done condition</span></div>
    <div class="z-connector">Choose a focused skill or invoke z-mode <span aria-hidden="true">↓</span></div>
    <div class="z-library">
      <div class="z-band"><strong>Shared library</strong><code>skills/</code></div>
      <p class="z-hint">Expand a layer to see its responsibility.</p>
      <details v-for="layer in layers" :key="layer.name" class="z-layer">
        <summary><span><strong>{{ layer.name }}</strong><span class="z-muted">{{ layer.role }}</span></span><span aria-hidden="true" class="z-expand">+</span></summary>
        <div class="z-layer-body"><p>{{ layer.detail }}</p><p class="z-examples">{{ layer.examples }}</p><a :href="withBase(layer.link)">Explore {{ layer.name }}</a></div>
      </details>
      <div class="z-support"><strong>References &amp; helper scripts</strong><span>Resolve from the real skill directory. Run target commands in the target repository.</span></div>
    </div>
    <div class="z-connector">Instructions are read by the host <span aria-hidden="true">↓</span></div>
    <div class="z-host-boundary">
      <div class="z-band"><strong>Native host</strong><span>Codex or Claude Code</span></div>
      <p>The host supplies the model, tools, permissions, sessions, and available delegation.</p>
      <div class="z-pair">
        <div><strong>Direct execution</strong><span>One agent handles a scoped task and checks the result.</span></div>
        <div><strong>Delegation, when allowed</strong><span><code>z-agent</code> owns an engineering slice. <code>comment-sicko</code> reports comment findings; the parent applies accepted edits.</span></div>
      </div>
    </div>
    <div class="z-connector">Inspect artifacts and actual checks <span aria-hidden="true">↓</span></div>
    <div class="z-result"><strong>Result + evidence + limits</strong><span>An explanation, verified local change, or durable handoff.</span></div>
    <figcaption>Solid layers are instructions; the dashed boundary marks capabilities controlled by the host. Installing zstack does not grant permissions or start background services.</figcaption>
  </figure>
</template>
