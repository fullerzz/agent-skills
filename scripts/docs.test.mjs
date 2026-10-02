import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createMarkdownRenderer } from 'vitepress';

const root = new URL('../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
const markdown = await createMarkdownRenderer(fileURLToPath(root));
const headingIds = (source) => new Set(
  [...markdown.render(source).matchAll(/<h[1-6]\b[^>]*\bid="([^"]+)"/g)].map((match) => match[1]),
);

test('reference anchors must be rendered headings, not prose or fenced examples', () => {
  assert.deepEqual(headingIds('## Real {#real}\n\nProse {#prose}\n\n```md\n## Fake {#fake}\n```'), new Set(['real']));
});

test('every installed skill and routed playbook has a user reference anchor', () => {
  const workflow = headingIds(read('docs/reference/workflow-skills.md'));
  const principles = headingIds(read('docs/reference/principles.md'));
  const playbooks = headingIds(read('docs/reference/playbooks.md'));
  for (const entry of readdirSync(fileURLToPath(new URL('skills/', root)), { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (!existsSync(new URL(`skills/${entry.name}/SKILL.md`, root))) continue;
    const page = entry.name.startsWith('principle-') ? principles : workflow;
    assert.ok(page.has(entry.name), `Missing skill reference: ${entry.name}`);
  }
  for (const file of readdirSync(fileURLToPath(new URL('skills/poteto-mode/playbooks/', root)))) {
    if (!file.endsWith('.md')) continue;
    const id = `playbook-${file.slice(0, -3)}`;
    assert.ok(playbooks.has(id), `Missing playbook reference: ${id}`);
  }
});
