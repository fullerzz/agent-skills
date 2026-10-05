import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMarkdownRenderer } from 'vitepress';
import { docsNotices } from './docs-notices.mjs';

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
  for (const file of readdirSync(fileURLToPath(new URL('skills/z-mode/playbooks/', root)))) {
    if (!file.endsWith('.md')) continue;
    const id = `playbook-${file.slice(0, -3)}`;
    assert.ok(playbooks.has(id), `Missing playbook reference: ${id}`);
  }
});

test('published docs ship license texts and the personal-use policy without an edit invitation', () => {
  execFileSync(process.execPath, [fileURLToPath(new URL('node_modules/vitepress/bin/vitepress.js', root)), 'build', 'docs'], {
    cwd: fileURLToPath(root),
    encoding: 'utf8',
  });
  const notices = read('docs/.vitepress/dist/third-party-notices.txt');
  for (const source of [
    'LICENSE',
    'node_modules/@fontsource/ibm-plex-mono/LICENSE',
    'node_modules/@fontsource-variable/schibsted-grotesk/LICENSE',
    'node_modules/vitepress/LICENSE',
  ]) {
    assert.ok(notices.includes(read(source).trim()), `Missing full notice: ${source}`);
  }
  assert.ok(notices.includes('@vue/runtime-core@'), 'Missing Vue runtime notice');
  const home = read('docs/.vitepress/dist/index.html');
  assert.ok(home.includes('third-party-notices.txt'), 'Missing notice download link');
  for (const content of [read('README.md'), home]) {
    assert.ok(content.includes('do not accept external issues or pull requests'));
    assert.ok(content.includes('do not provide user support'));
  }
  assert.ok(!read('docs/.vitepress/dist/guide/index.html').includes('Edit this page on GitHub'));
});

test('notice generation refuses missing and empty license texts, including loaded CSS', () => {
  const fixture = mkdtempSync(path.join(os.tmpdir(), 'docs notices '));
  try {
    const directory = path.join(fixture, 'node_modules', 'fixture-font');
    mkdirSync(directory, { recursive: true });
    writeFileSync(path.join(directory, 'package.json'), JSON.stringify({ name: 'fixture-font', version: '1.0.0' }));
    const context = {
      getModuleIds: () => [path.join(directory, 'font.css')],
      getModuleInfo: () => ({ isIncluded: false }),
    };
    const generate = () => docsNotices().generateBundle.call(context);
    assert.throws(generate, /Missing license text for fixture-font@1.0.0/);
    writeFileSync(path.join(directory, 'LICENSE'), '');
    assert.throws(generate, /Empty license text for fixture-font@1.0.0/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
