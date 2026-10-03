<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import './visuals.css'

const host = ref('codex')
const scope = ref('personal')
const paths = computed(() => {
  const base = scope.value === 'personal' ? '~/' : '<project>/'
  const native = base + (host.value === 'codex' ? '.codex' : '.claude')
  return { skills: base + (host.value === 'codex' ? '.agents' : '.claude') + '/skills/<name>', agents: native + '/agents/', receipt: native + '/zstack-install.json' }
})
const command = computed(() => `uv run scripts/install.py --host ${host.value}${scope.value === 'project' ? ' --project "/absolute/path/to/project"' : ''}`)
</script>

<template>
  <figure class="z-visual" aria-label="Installation source and destination map">
    <div class="z-controls">
      <label>Host <select v-model="host" aria-label="Host"><option value="codex">Codex</option><option value="claude">Claude Code</option></select></label>
      <label>Scope <select v-model="scope" aria-label="Scope"><option value="personal">Personal</option><option value="project">Project</option></select></label>
    </div>
    <div aria-live="polite" aria-atomic="true">
      <div class="z-band"><strong>Stable library checkout</strong><span>Keep this location available</span></div>
      <div class="z-transfer">
        <div><code>skills/&lt;name&gt;/</code><span>One canonical source for both hosts</span></div>
        <div class="z-transfer-label"><strong>Link</strong><span aria-hidden="true">↓</span></div>
        <div><code>{{ paths.skills }}</code><span>Resolves back to the checkout, including referenced resources</span></div>
      </div>
      <div class="z-transfer">
        <div><code>agents/{{ host }}/</code><span>{{ host === 'codex' ? 'Standalone TOML roles' : 'Markdown roles with frontmatter' }}</span></div>
        <div class="z-transfer-label"><strong>Copy</strong><span aria-hidden="true">↓</span></div>
        <div><code>{{ paths.agents }}</code><span>Owned copies of z-agent and comment-sicko</span></div>
      </div>
      <div class="z-support"><strong>Ownership receipt</strong><code>{{ paths.receipt }}</code><span>Records source and owned files for updates and safe removal.</span></div>
      <p v-if="scope === 'personal'" class="z-hint">Default paths shown. {{ host === 'codex' ? 'CODEX_HOME changes the native agent and receipt root; skills stay in ~/.agents/skills.' : 'CLAUDE_CONFIG_DIR changes the skills, agents, and receipt root.' }} Explicit --home uses an isolated root instead.</p>
      <p v-else class="z-hint">Paths are inside the existing target project. Personal environment overrides do not change these project destinations.</p>
      <div class="z-command"><strong>Preview from the library checkout</strong><code>{{ command }}</code><span>Review the plan, then repeat with <code>--apply</code>. Start a new host session.</span></div>
    </div>
    <details class="z-layer"><summary><strong>What changes on update or removal?</strong><span class="z-expand" aria-hidden="true">+</span></summary><div class="z-layer-body"><p>Linked skills reflect checkout changes. Rerun installation to create new links and update unchanged owned agent copies. Edited agent copies produce a collision.</p><p>Uninstall removes this checkout’s links and unchanged owned copies; modified or unowned files remain. Complete removal in every scope before moving the checkout.</p><a :href="withBase('/guide/01-setup#uninstall-or-move-the-checkout')">Full update and removal procedure</a></div></details>
    <figcaption>This map explains file ownership. It does not install anything, grant project trust, enable agents, or change model and permission settings.</figcaption>
  </figure>
</template>
