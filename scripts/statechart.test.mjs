import { createRequire } from 'node:module';
import { test } from 'node:test';

const tests = '../skills/statechart/scripts/test/';
for (const name of ['chart', 'cli', 'config-fuzz', 'corpus', 'messages', 'pipeline', 'plain-tlc', 'tlc-out']) {
  await import(`${tests}${name}.test.ts`);
}

// These suites need packages that the skill does not ship, so they run only on request.
let fastCheck = true;
try {
  createRequire(new URL(`${tests}../package.json`, import.meta.url)).resolve('fast-check');
} catch {
  fastCheck = false;
}
if (fastCheck) await import(`${tests}differential.test.ts`);
else test('statechart differential suite', { skip: 'run npm install in skills/statechart/scripts to add fast-check' }, () => {});
if (process.env.STATECHART_RENDER_TESTS === '1') await import(`${tests}render.test.ts`);
else test('statechart Pele and Mermaid render suite', { skip: 'set STATECHART_RENDER_TESTS=1; it installs Pele and Mermaid under ~/.cache/statechart' }, () => {});
