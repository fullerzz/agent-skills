import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const repo = 'https://github.com/fullerzz/agent-skills'
export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

export interface Entry {
  id: string
  name: string
  description: string
  source: string
  guide: string
  modelInvocable: boolean
}

export interface Catalog {
  skills: Entry[]
  principles: Entry[]
  playbooks: Entry[]
}

const plain = (line: string) =>
  line.replace(/^\d+\.\s+/, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/`/g, '')

export function loadCatalog(): Catalog {
  const skillsDir = path.join(repoRoot, 'skills')
  const entries = fs
    .readdirSync(skillsDir)
    .filter((name) => fs.existsSync(path.join(skillsDir, name, 'SKILL.md')))
    .sort()
    .map((id): Entry => {
      const text = fs.readFileSync(path.join(skillsDir, id, 'SKILL.md'), 'utf8')
      const meta = parse(text.split(/^---$/m)[1])
      return {
        id,
        name: id.replace(/^principle-/, ''),
        description: meta.description,
        source: `${repo}/blob/main/skills/${id}/SKILL.md`,
        guide: `/reference/${id.startsWith('principle-') ? 'principles' : 'workflow-skills'}#${id}`,
        modelInvocable: meta['disable-model-invocation'] !== true,
      }
    })

  const playbookDir = path.join(skillsDir, 'z-mode/playbooks')
  const playbooks = fs
    .readdirSync(playbookDir)
    .filter((file) => file.endsWith('.md'))
    .sort()
    .map((file): Entry => {
      const lines = fs.readFileSync(path.join(playbookDir, file), 'utf8').split('\n')
      const slug = file.replace(/\.md$/, '')
      return {
        id: `playbook-${slug}`,
        name: lines[0].replace(/^#\s+/, ''),
        description: plain(lines.find((line, i) => i > 0 && line.trim() && !line.startsWith('#')) ?? ''),
        source: `${repo}/blob/main/skills/z-mode/playbooks/${file}`,
        guide: `/reference/playbooks#playbook-${slug}`,
        modelInvocable: false,
      }
    })

  return {
    skills: entries.filter((entry) => !entry.id.startsWith('principle-')),
    principles: entries.filter((entry) => entry.id.startsWith('principle-')),
    playbooks,
  }
}
