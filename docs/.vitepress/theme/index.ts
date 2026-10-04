import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import Workflow from './Workflow.vue'
import '@fontsource-variable/schibsted-grotesk'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import './style.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Workflow', Workflow)
  },
} satisfies Theme
