import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');

test('every installed skill and routed playbook has a user reference anchor', () => {
  const workflow = read('docs/reference/workflow-skills.md');
  const principles = read('docs/reference/principles.md');
  const playbooks = read('docs/reference/playbooks.md');
  for (const entry of readdirSync(fileURLToPath(new URL('skills/', root)), { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (!existsSync(new URL(`skills/${entry.name}/SKILL.md`, root))) continue;
    const page = entry.name.startsWith('principle-') ? principles : workflow;
    assert.ok(page.includes(`{#${entry.name}}`), `Missing skill reference: ${entry.name}`);
  }
  for (const file of readdirSync(fileURLToPath(new URL('skills/poteto-mode/playbooks/', root)))) {
    if (!file.endsWith('.md')) continue;
    const id = `playbook-${file.slice(0, -3)}`;
    assert.ok(playbooks.includes(`{#${id}}`), `Missing playbook reference: ${id}`);
  }
});
