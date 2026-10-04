<script setup lang="ts">
import { withBase } from 'vitepress'

const steps = [
  { title: 'Understand', skills: 'how · why · teach', link: '/guide/02-understand-and-design#understand-before-changing' },
  { title: 'Design', skills: 'architect · arena · interrogate', link: '/guide/02-understand-and-design#design-and-review' },
  { title: 'Build', skills: 'z-mode · tdd', link: '/guide/03-build-and-verify#build-a-scoped-change' },
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
/* A rail: the steps are a sequence, so they share one line. */
.workflow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin: 28px 0;
  padding: 0;
  list-style: none;
}

.workflow li {
  position: relative;
  margin: 0;
}

.workflow li:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 15px;
  left: 40px;
  right: -8px;
  height: 2px;
  background: var(--vp-c-divider);
}

.workflow a {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100%;
  padding-right: 8px;
  color: var(--vp-c-text-1);
  text-decoration: none;
}

.workflow-index {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 2px solid var(--vp-c-brand-1);
  border-radius: 50%;
  color: var(--vp-c-brand-1);
  font-size: 14px;
  font-weight: 700;
  transition: background-color 0.2s, color 0.2s;
}

.workflow a:hover .workflow-index {
  background: var(--vp-c-brand-1);
  color: var(--vp-c-bg);
}

.workflow-title {
  margin-top: 10px;
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.workflow a:hover .workflow-title {
  color: var(--vp-c-brand-1);
}

.workflow-skills {
  color: var(--vp-c-text-2);
  font-family: var(--vp-font-family-mono);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .workflow {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .workflow li {
    padding-bottom: 20px;
  }

  .workflow li:not(:last-child)::after {
    top: 40px;
    bottom: 4px;
    left: 15px;
    right: auto;
    width: 2px;
    height: auto;
  }

  .workflow a {
    display: grid;
    grid-template-columns: 32px 1fr;
    column-gap: 16px;
  }

  .workflow-title {
    margin-top: 4px;
  }

  .workflow-skills {
    grid-column: 2;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workflow-index {
    transition: none;
  }
}
</style>
