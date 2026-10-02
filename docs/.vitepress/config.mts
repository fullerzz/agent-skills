import path from 'node:path'
import { defineConfig } from 'vitepress'
import { loadCatalog, repo, repoRoot } from './skills'

const docsDir = path.join(repoRoot, 'docs')

const escape = (text: string) =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// The search splitter only recognizes headings that contain an anchor link.
const heading = (level: number, id: string, text: string) =>
  `<h${level} id="${id}">${escape(text)} <a class="header-anchor" href="#${id}"></a></h${level}>`

// Local search cannot see the client-rendered catalog cards, so index them directly.
function catalogSearchHtml() {
  const catalog = loadCatalog()
  const sections: [string, string, keyof typeof catalog][] = [
    ['Workflow skills', 'workflow-skills', 'skills'],
    ['Principles', 'principles', 'principles'],
    ['Playbooks', 'playbooks', 'playbooks'],
  ]
  return (
    heading(1, 'skill-catalog', 'Skill catalog') +
    sections
      .map(
        ([title, id, key]) =>
          heading(2, id, title) +
          catalog[key].map((e) => heading(3, e.id, e.name) + `<p>${escape(e.description)}</p>`).join('')
      )
      .join('')
  )
}

export default defineConfig({
  title: "zstack",
  description: 'A personal engineering skill library for Codex and Claude Code.',
  cleanUrls: true,
  lastUpdated: true,
  head: [['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }]],
  rewrites: { 'guide/README.md': 'guide/index.md' },
  markdown: {
    config(md) {
      // Docs link to skills and LICENSE outside docs/. Skill and playbook files go to the
      // catalog; anything else, or a link into a section, goes to GitHub.
      md.core.ruler.push('repo-links', (state) => {
        for (const token of state.tokens) {
          for (const child of token.children ?? []) {
            const href = child.type === 'link_open' && child.attrGet('href')
            if (!href || /^[a-z]+:|^[#/]/i.test(href)) continue
            const [file, hash] = href.split('#')
            const target = path.resolve(path.dirname(state.env.path), file)
            if (target.startsWith(docsDir + path.sep)) continue
            const relative = path.relative(repoRoot, target).split(path.sep).join('/')
            const skill = !hash && relative.match(/^skills\/([^/]+)\/SKILL\.md$/)
            const playbook = !hash && relative.match(/^skills\/z-mode\/playbooks\/([^/]+)\.md$/)
            child.attrSet(
              'href',
              skill
                ? `/skills#${skill[1]}`
                : playbook
                  ? `/skills#playbook-${playbook[1]}`
                  : `${repo}/blob/main/${relative}${hash ? `#${hash}` : ''}`
            )
          }
        }
      })
    },
  },
  themeConfig: {
    logo: '/logo.svg',
    externalLinkIcon: true,
    nav: [
      { text: 'Guide', link: '/guide/', activeMatch: '/guide/' },
      { text: 'Skills', link: '/skills' },
      {
        text: 'Hosts',
        items: [
          { text: 'Claude Code', link: '/hosts/claude-code' },
          { text: 'Codex', link: '/hosts/codex' },
        ],
      },
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Overview', link: '/guide/' },
          { text: 'Install and route work', link: '/guide/01-setup' },
          { text: 'Understand and design', link: '/guide/02-understand-and-design' },
          { text: 'Build and verify', link: '/guide/03-build-and-verify' },
          { text: 'Long work and conventions', link: '/guide/04-long-work' },
          { text: 'Principles and recipes', link: '/guide/05-principles-and-recipes' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Skill catalog', link: '/skills' },
          { text: 'Workflow skills', link: '/reference/workflow-skills' },
          { text: 'Playbooks', link: '/reference/playbooks' },
          { text: 'Principles', link: '/reference/principles' },
          { text: 'Claude Code', link: '/hosts/claude-code' },
          { text: 'Codex', link: '/hosts/codex' },
        ],
      },
      {
        text: 'Project',
        collapsed: true,
        items: [
          { text: 'Validation', link: '/validation' },
          { text: 'Provenance', link: '/provenance' },
          { text: 'Adaptation plan', link: '/adaptation-plan' },
        ],
      },
    ],
    socialLinks: [{ icon: 'github', link: repo }],
    editLink: { pattern: `${repo}/edit/main/docs/:path`, text: 'Edit this page on GitHub' },
    footer: {
      message: `Released under the MIT License. Adapted from Lauren Tan's <a href="https://github.com/cursor/plugins/tree/main/pstack">pstack</a>.`,
      copyright: 'Copyright © 2026 Lauren Tan',
    },
    search: {
      provider: 'local',
      options: {
        _render(src, env, md) {
          return env.relativePath === 'skills.md' ? catalogSearchHtml() : md.render(src, env)
        },
      },
    },
  },
})
