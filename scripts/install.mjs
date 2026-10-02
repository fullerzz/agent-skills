#!/usr/bin/env node
import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync, mkdirSync, symlinkSync, readlinkSync, unlinkSync, writeFileSync, renameSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { createHash, randomUUID } from 'node:crypto';
import { parseArgs } from 'node:util';

const root = realpathSync(resolve(dirname(fileURLToPath(import.meta.url)), '..'));
const hash = path => createHash('sha256').update(readFileSync(path)).digest('hex');
const present = path => { try { lstatSync(path); return true; } catch (e) { if (e.code === 'ENOENT') return false; throw e; } };
const ownsLink = (path, source) => present(path) && lstatSync(path).isSymbolicLink() && resolve(dirname(path), readlinkSync(path)) === source;

function main() {
  const { values, positionals } = parseArgs({ allowPositionals: true, options: {
    host: { type: 'string', default: 'both' }, home: { type: 'string' }, project: { type: 'string' },
    apply: { type: 'boolean', default: false }, help: { type: 'boolean', default: false },
  } });
  if (values.help) {
    console.log('node scripts/install.mjs [install|uninstall] --host codex|claude|both [--project PATH | --home PATH] [--apply]\nPreview by default. Skills are links; agents are owned copies. No model or permission settings are changed.');
    return;
  }
  const action = positionals[0] ?? 'install';
  if (positionals.length > 1 || !['install', 'uninstall'].includes(action) || !['both', 'codex', 'claude'].includes(values.host)) throw new Error('Invalid action or host. See --help.');
  if (values.project && values.home) throw new Error('Choose --project or --home.');
  const home = resolve(values.home ?? homedir());
  const project = values.project && realpathSync(resolve(values.project));
  const hosts = values.host === 'both' ? ['codex', 'claude'] : [values.host];
  const plans = hosts.map(host => {
    const base = project ?? home;
    const configured = process.env[host === 'codex' ? 'CODEX_HOME' : 'CLAUDE_CONFIG_DIR'];
    const native = !project && !values.home && configured ? resolve(configured) : join(base, host === 'codex' ? '.codex' : '.claude');
    const skills = host === 'codex' ? join(base, '.agents/skills') : join(native, 'skills');
    const receipt = join(native, 'pstack-install.json');
    if (present(receipt) && (!lstatSync(receipt).isFile() || lstatSync(receipt).isSymbolicLink())) throw new Error(`Receipt is not a regular file: ${receipt}`);
    const saved = existsSync(receipt) ? JSON.parse(readFileSync(receipt, 'utf8')) : { source: root, agents: {} };
    if (saved.source !== root || !saved.agents || typeof saved.agents !== 'object') throw new Error(`Receipt belongs to another checkout or is invalid: ${receipt}`);
    const entries = readdirSync(join(root, 'skills'), { withFileTypes: true }).filter(e => e.isDirectory() && existsSync(join(root, 'skills', e.name, 'SKILL.md'))).map(e => ({ source: join(root, 'skills', e.name), target: join(skills, e.name), kind: 'link' }));
    for (const name of readdirSync(join(root, 'agents', host))) entries.push({ source: join(root, 'agents', host, name), target: join(native, 'agents', name), kind: 'copy', name });
    for (const entry of entries) {
      const exists = present(entry.target);
      const owned = entry.kind === 'link' ? ownsLink(entry.target, entry.source) : exists && lstatSync(entry.target).isFile() && !lstatSync(entry.target).isSymbolicLink() && [saved.agents[entry.name]].flat().includes(hash(entry.target));
      entry.op = action === 'install' ? (exists ? (owned ? (entry.kind === 'copy' && hash(entry.source) !== hash(entry.target) ? 'update' : 'keep') : 'collision') : 'create') : (exists ? (owned ? 'remove' : 'preserve') : 'absent');
    }
    return { receipt, saved, entries };
  });
  for (const plan of plans) for (const e of plan.entries) console.log(`${e.op}\t${e.target}\t${e.source}`);
  if (plans.some(p => p.entries.some(e => e.op === 'collision'))) throw new Error('Existing files conflict. Nothing installed; choose another scope or resolve the named collisions.');
  if (!values.apply) { console.log('Preview only. Add --apply to perform these operations.'); return; }
  for (const plan of plans) {
    for (const e of plan.entries) {
      if (['create', 'update'].includes(e.op)) {
        mkdirSync(dirname(e.target), { recursive: true });
        if (e.kind === 'link') symlinkSync(e.source, e.target, 'dir');
        else {
          // An interrupted update may leave either the old or the new owned copy.
          const nextHash = hash(e.source);
          plan.saved.agents[e.name] = [...new Set([plan.saved.agents[e.name], nextHash].flat().filter(Boolean))];
          save(plan);
          if (e.op === 'create') writeFileSync(e.target, readFileSync(e.source), { flag: 'wx' });
          else atomicWrite(e.target, readFileSync(e.source));
          plan.saved.agents[e.name] = nextHash;
        }
      } else if (e.op === 'remove') {
        unlinkSync(e.target);
        if (e.kind === 'copy') delete plan.saved.agents[e.name];
      } else if (e.kind === 'copy' && e.op === 'absent') delete plan.saved.agents[e.name];
    }
    if (Object.keys(plan.saved.agents).length) save(plan);
    else if (present(plan.receipt)) unlinkSync(plan.receipt);
  }
  if (action === 'uninstall' && plans.some(p => p.entries.some(e => e.op === 'preserve'))) console.log('Preserved unowned or modified files. Their receipts remain for inspection.');
}

function save(plan) {
  mkdirSync(dirname(plan.receipt), { recursive: true });
  atomicWrite(plan.receipt, JSON.stringify(plan.saved, null, 2) + '\n');
}

function atomicWrite(target, contents) {
  const temporary = `${target}.${randomUUID()}.tmp`;
  try { writeFileSync(temporary, contents, { flag: 'wx' }); renameSync(temporary, target); }
  finally { if (present(temporary)) unlinkSync(temporary); }
}

try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
