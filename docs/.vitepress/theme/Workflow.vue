<script setup lang="ts">
import { withBase } from 'vitepress'

const steps = [
  { title: 'Understand', skills: 'how · why · teach', link: '/guide/02-understand-and-design#understand-before-changing' },
  { title: 'Design', skills: 'architect · arena · interrogate', link: '/guide/02-understand-and-design#design-and-review' },
  { title: 'Build', skills: 'poteto-mode · tdd', link: '/guide/03-build-and-verify#build-a-scoped-change' },
  { title: 'Verify', skills: 'create-verification-skill', link: '/guide/03-build-and-verify#verify-before-publication' },
  { title: 'Publish', skills: 'opening-a-pr · shipping', link: '/guide/03-build-and-verify#publish-on-request' },
]
</script>

<template>
  <ol class="workflow">
    <li v-for="(step, i) in steps" :key="step.title">
      <a :href="withBase(step.link)">
        <span class="workflow-index">{{ i + 1 }}</span>
        <span class="workflow-title">{{ step.title }}</span>
        <span class="workflow-skills">{{ step.skills }}</span>
      </a>
    </li>
  </ol>
</template>

<style scoped>
.workflow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin: 24px 0;
  padding: 0;
  list-style: none;
}

.workflow li {
  position: relative;
  margin: 0;
}

.workflow a {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100%;
  padding: 16px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  text-decoration: none;
  transition: border-color 0.25s, transform 0.25s;
}

.workflow a:hover {
  border-color: var(--vp-c-brand-1);
  transform: translateY(-2px);
}

.workflow-index {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--vp-c-brand-soft);
  color: var(--vp-c-brand-1);
  font-size: 14px;
  font-weight: 600;
}

.workflow-title {
  margin-top: 8px;
  font-weight: 600;
}

.workflow-skills {
  color: var(--vp-c-text-2);
  font-family: var(--vp-font-family-mono);
  font-size: 12px;
  line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
  .workflow a {
    transition: none;
  }

  .workflow a:hover {
    transform: none;
  }
}
</style>
