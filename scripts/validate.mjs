#!/usr/bin/env bun
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { dirname, join, resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const failures = [];
const fail = (file, message) => failures.push(`${file}: ${message}`);
const files = [];
function walk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', '.git', '.agent-work'].includes(e.name)) continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p); else if (e.isFile()) files.push(p);
  }
}
walk(root);
const names = new Set();
function frontmatter(file) {
  const text = readFileSync(file, 'utf8');
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) throw new Error('Missing YAML frontmatter');
  const meta = Bun.YAML.parse(match[1]);
  if (!meta || typeof meta.name !== 'string' || typeof meta.description !== 'string' || !meta.description.trim()) throw new Error('Need scalar name and nonempty description');
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(meta.name) || meta.name.length > 64 || meta.description.length > 1024) throw new Error('Invalid identifier or metadata length');
  return meta;
}
for (const file of files) {
  const relative = file.slice(root.length + 1);
  try {
    if (basename(file) === 'SKILL.md') {
      const meta = frontmatter(file);
      if (meta.name !== basename(dirname(file))) fail(relative, 'Name must match directory');
      if (names.has(meta.name)) fail(relative, 'Duplicate skill name');
      names.add(meta.name);
      const allowed = ['name', 'description', 'disable-model-invocation', 'metadata', 'license', 'compatibility', 'allowed-tools'];
      for (const key of Object.keys(meta)) if (!allowed.includes(key)) fail(relative, `Unsupported shared metadata: ${key}`);
      if ('disable-model-invocation' in meta && typeof meta['disable-model-invocation'] !== 'boolean') fail(relative, 'Invocation flag must be boolean');
      const yaml = join(dirname(file), 'agents/openai.yaml');
      if (meta['disable-model-invocation'] === true && (!existsSync(yaml) || Bun.YAML.parse(readFileSync(yaml, 'utf8'))?.policy?.allow_implicit_invocation !== false)) fail(relative, 'Explicit-only Codex policy missing');
    }
    if (relative.startsWith('agents/codex/')) {
      const meta = Bun.TOML.parse(readFileSync(file, 'utf8'));
      for (const key of ['name', 'description', 'developer_instructions']) if (typeof meta[key] !== 'string' || !meta[key].trim()) fail(relative, `Missing ${key}`);
      if (meta.name !== basename(file, '.toml')) fail(relative, 'Agent name mismatch');
    }
    if (relative.startsWith('agents/claude/')) {
      const meta = frontmatter(file);
      if (meta.name !== basename(file, '.md') || meta.model !== 'inherit') fail(relative, 'Agent name/model mismatch');
    }
    if (file.endsWith('.yaml')) Bun.YAML.parse(readFileSync(file, 'utf8'));
    if (!file.endsWith('.md')) continue;
    const text = readFileSync(file, 'utf8');
    if (/[ \t]+$/m.test(text)) fail(relative, 'Trailing whitespace');
    const prose = text.replace(/^```[^\n]*\n[\s\S]*?^```[^\n]*$/gm, '');
    for (const match of prose.matchAll(/\]\(([^)]+)\)/g)) {
      const link = match[1];
      if (/^(?:https?:|mailto:|#)/.test(link) || /[<>]/.test(link)) continue;
      const path = decodeURIComponent(link.split('#')[0]);
      if (!existsSync(resolve(dirname(file), path))) fail(relative, `Broken local link: ${link}`);
    }
    if (relative.startsWith('skills/') || relative.startsWith('docs/guide/') || relative.startsWith('agents/')) {
      if (/\.cursor\/|cursor-team-kit|pstack-models\.mdc|run_in_background|cloud_base_branch|subagent_type|grok-4|claude-opus-5-5|gpt-5\.6-sol|\/loop\b|\/goal\b/.test(text)) fail(relative, 'Active unsupported host instruction');
    }
  } catch (error) { fail(relative, error.message); }
}
for (const path of ['scripts/check-plan.mjs', 'scripts/worktree-audit.sh', 'scripts/worktree-audit.mjs', 'scripts/watch-pr/watch-pr', 'scripts/orch/orch.ts']) if (!existsSync(join(root, 'skills/poteto-mode', path))) fail(path, 'Missing tool entrypoint');
for (const file of ['skills/show-me-your-work/scripts/log.sh', 'skills/poteto-mode/scripts/watch-pr/watch-pr']) if (!(statSync(join(root, file)).mode & 0o111)) fail(file, 'Helper not executable');
for (const path of ['.cursor-plugin', 'automations/benny', 'skills/make-bot-ui']) if (existsSync(join(root, path))) fail(path, 'Retired content remains');
console.log(`${names.size} skills, ${failures.length} structural problems`);
for (const failure of failures) console.error(failure);
process.exitCode = failures.length ? 1 : 0;
