#!/usr/bin/env node
import { readFileSync } from 'node:fs';
const file = process.argv[2];
if (!file) { console.error('Usage: node check-plan.mjs <plan.md>'); process.exit(2); }
try {
  const text = readFileSync(file, 'utf8').replace(/^~~~[^\n]*\n[\s\S]*?^~~~[^\n]*$/gm, '').replace(/^```[^\n]*\n[\s\S]*?^```[^\n]*$/gm, '');
  const problems = [];
  if (!/^# .+$/m.test(text)) problems.push('Missing H1 title');
  const sections = text.split(/^## /m).slice(1).map(s => { const i = s.indexOf('\n'); return { name: s.slice(0, i).trim(), body: s.slice(i + 1).trim() }; });
  for (const name of ['Outcome', 'Scope', 'Phases', 'Risks', 'Handoff']) {
    const found = sections.filter(s => s.name === name);
    if (found.length !== 1 || !found[0].body) problems.push('Need one nonempty ## ' + name);
  }
  const phases = sections.find(s => s.name === 'Phases')?.body.split(/^### /m).slice(1) ?? [];
  if (!phases.length) problems.push('Phases needs at least one H3 unit');
  for (const phase of phases) {
    const title = phase.split('\n')[0].trim();
    for (const field of ['Depends on', 'Files', 'Acceptance', 'Verification']) {
      if (!new RegExp('^- ' + field + ':\\s*\\S', 'm').test(phase)) problems.push(title + ': missing nonempty ' + field + ' bullet');
    }
  }
  console.log(phases.length + ' phases, ' + problems.length + ' problems');
  for (const problem of problems) console.error(file + ': ' + problem);
  process.exitCode = problems.length ? 1 : 0;
} catch (error) { console.error(error.message); process.exitCode = 1; }
