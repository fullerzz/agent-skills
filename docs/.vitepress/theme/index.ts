import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import Workflow from './Workflow.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Workflow', Workflow)
  },
} satisfies Theme
