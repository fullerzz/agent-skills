<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import './visuals.css'

const routes = [
  { name: 'Investigate', playbook: 'investigation', prompt: 'explain the retry path; no edits', input: 'A concrete behavior question', steps: [
    ['Trace', 'Read entry points and callers with how. Use why when motivation matters.'],
    ['Compare', 'For a decision, compare relevant alternatives against the evidence.'],
    ['Report', 'Return a cited explanation and name any gaps.'],
  ], principle: 'Guard the context window', principleId: 'guard-the-context-window', reason: 'Load only context that advances the question.', output: 'Cited answer; product files unchanged.', boundary: 'An investigation does not authorize a fix or an unsolicited prototype.' },
  { name: 'Fix a bug', playbook: 'bug-fix', prompt: 'fix duplicate output; reproduce first; keep changes local', input: 'A reproducible failure on the reported surface', steps: [
    ['Reproduce', 'Run the reported path with the project’s harness. Record missing capabilities if it cannot run.'],
    ['Trace & fix', 'Follow the mechanism through callers and history; change the smallest shared root cause.'],
    ['Prove', 'Use a meaningful failing-then-passing check; rerun the original repro and regressions.'],
  ], principle: 'Fix root causes', principleId: 'fix-root-causes', reason: 'Repair the mechanism shared by affected callers.', output: 'Scoped fix, regression evidence, and practical limits.', boundary: 'Local repair does not by itself authorize a commit, push, or PR.' },
  { name: 'Build a feature', playbook: 'feature', prompt: 'add a --json flag; keep text output unchanged and verify both forms', input: 'Observable acceptance for the new behavior', steps: [
    ['Ground', 'Inspect entry points, existing patterns, caller contracts, and the simplest interface.'],
    ['Implement', 'Keep small work direct. When useful and permitted, delegate exclusive slices; adapt affected consumers.'],
    ['Verify', 'Exercise observable behavior with the existing harness; use live proof where required.'],
  ], principle: 'Prove it works', principleId: 'prove-it-works', reason: 'Evidence must demonstrate the requested outcome.', output: 'Working behavior, evidence, and open decisions.', boundary: 'Delegation depends on the workflow and host. Publication still follows the user’s request.' },
  { name: 'Pause safely', playbook: 'pause-safely', prompt: 'pause; record the exact resume action', input: 'An explicit pause/stop or a session that cannot continue', steps: [
    ['Stabilize', 'Stop at an atomic boundary; cancel or drain children and preserve concurrent files.'],
    ['Record', 'Save goal, mode, authority, branch and SHAs, dirty files, evidence, decisions, blockers, and next action.'],
    ['Resume later', 'Verify the note survives teardown. A new session checks live state before continuing.'],
  ], principle: 'Boundary discipline', principleId: 'boundary-discipline', reason: 'Carry the granted scope forward without expanding it.', output: 'Durable handoff and an exact first resume action.', boundary: 'Pausing does not commit, push, or discard work. A saved note is not a running daemon.' },
]
const selected = ref(0)
const route = computed(() => routes[selected.value])
</script>

<template>
  <figure class="z-visual" aria-label="Interactive z-mode routing examples">
    <div class="z-controls" role="group" aria-label="Choose a task">
      <button v-for="(item, index) in routes" :key="item.playbook" type="button" :aria-pressed="selected === index" @click="selected = index">{{ item.name }}</button>
    </div>
    <div aria-live="polite" aria-atomic="true">
      <div class="z-request"><strong>{{ route.input }}</strong><code>$z-mode {{ route.prompt }}</code><span>Claude Code uses <code>/z-mode</code> with the same request.</span></div>
      <div class="z-connector">z-mode selects <a :href="withBase('/reference/playbooks#playbook-' + route.playbook)">{{ route.playbook }}</a><span aria-hidden="true">↓</span></div>
      <ol class="z-route">
        <li v-for="(step, index) in route.steps" :key="route.playbook + index"><span class="z-step" aria-hidden="true">{{ index + 1 }}</span><div><strong>{{ step[0] }}</strong><p>{{ step[1] }}</p></div></li>
      </ol>
      <aside class="z-principle"><strong>Decision lens: <a :href="withBase('/reference/principles#principle-' + route.principleId)">{{ route.principle }}</a></strong><span>{{ route.reason }} Other relevant principles may be read as needed.</span></aside>
      <div class="z-connector">Return observed evidence <span aria-hidden="true">↓</span></div>
      <div class="z-result"><strong>{{ route.output }}</strong><span>{{ route.boundary }}</span></div>
    </div>
    <figcaption>Illustrative routes, not an executing agent. Failed or inconclusive verification leads back to investigation; it is not a successful completion.</figcaption>
  </figure>
</template>
