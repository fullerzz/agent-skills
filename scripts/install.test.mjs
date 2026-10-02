import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, existsSync, writeFileSync, readFileSync, realpathSync, readlinkSync, unlinkSync, symlinkSync, rmSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const run = args => spawnSync(process.execPath, [join(root, 'scripts/install.mjs'), ...args], { encoding: 'utf8' });
test('native personal roots are honored; explicit home and project remain isolated', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'pstack native roots '));
  try {
    const codex = join(scratch, 'codex config'), claude = join(scratch, 'claude config');
    const env = { ...process.env, CODEX_HOME: codex, CLAUDE_CONFIG_DIR: claude };
    const invoke = args => spawnSync(process.execPath, [join(root, 'scripts/install.mjs'), ...args], { encoding: 'utf8', env });
    const preview = invoke(['--host', 'claude']);
    assert.equal(preview.status, 0);
    assert.ok(invoke(['--host', 'codex']).stdout.includes(`create\t${join(codex, 'agents/poteto-agent.toml')}\t`));
    assert.ok(preview.stdout.includes(`create\t${join(claude, 'skills/how')}\t`));
    assert.equal(invoke(['--host', 'claude', '--apply']).status, 0);
    assert.equal(realpathSync(join(claude, 'skills/how')), join(root, 'skills/how'));
    assert.equal(existsSync(join(claude, 'agents/poteto-agent.md')), true);
    assert.equal(invoke(['uninstall', '--host', 'claude', '--apply']).status, 0);
    assert.equal(existsSync(join(claude, 'agents/poteto-agent.md')), false);
    for (const scope of ['--home', '--project']) {
      const target = join(scratch, scope.slice(2)); mkdirSync(target, { recursive: true });
      assert.equal(invoke([scope, target, '--host', 'both', '--apply']).status, 0);
      assert.equal(existsSync(join(target, '.claude/skills/how')), true);
      assert.equal(existsSync(join(target, '.codex/agents/poteto-agent.toml')), true);
      assert.equal(existsSync(join(claude, 'skills/how')), false);
    }
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
test('install preview, rerun, collision, and owned removal for both hosts', () => {
  const home = mkdtempSync(join(tmpdir(), 'pstack home '));
  try {
    const args = ['--home', home, '--host', 'both'];
    assert.equal(run(args).status, 0);
    assert.equal(existsSync(join(home, '.agents')), false);
    assert.equal(run([...args, '--apply']).status, 0);
    const missingCopy = join(home, '.codex/agents/poteto-agent.toml');
    unlinkSync(missingCopy);
    assert.equal(run([...args, '--apply']).status, 0);
    assert.equal(readFileSync(missingCopy, 'utf8'), readFileSync(join(root, 'agents/codex/poteto-agent.toml'), 'utf8'));
    assert.equal(realpathSync(join(home, '.agents/skills/how')), join(root, 'skills/how'));
    assert.equal(realpathSync(join(home, '.claude/skills/how')), join(root, 'skills/how'));
    assert.match(readFileSync(join(home, '.codex/agents/poteto-agent.toml'), 'utf8'), /developer_instructions/);
    assert.match(readFileSync(join(home, '.claude/agents/comment-sicko.md'), 'utf8'), /model: inherit/);
    assert.equal(run([...args, '--apply']).status, 0);
    const modified = join(home, '.claude/agents/poteto-agent.md');
    writeFileSync(modified, 'user override\n');
    assert.equal(run([...args, '--apply']).status, 1);
    const unrelated = join(home, '.agents/skills/user-owned');
    mkdirSync(unrelated);
    const foreign = join(home, '.agents/skills/how');
    unlinkSync(foreign); symlinkSync(unrelated, foreign);
    const dangling = join(home, '.claude/skills/why'), destination = join(home, 'missing foreign skill');
    unlinkSync(dangling); symlinkSync(destination, dangling);
    assert.equal(run(['uninstall', ...args, '--apply']).status, 0);
    assert.equal(readFileSync(modified, 'utf8'), 'user override\n');
    assert.equal(existsSync(unrelated), true);
    assert.equal(realpathSync(foreign), realpathSync(unrelated));
    assert.equal(readlinkSync(dangling), destination);
    assert.equal(existsSync(join(home, '.codex/agents/poteto-agent.toml')), false);
    assert.equal(existsSync(join(home, '.claude/skills/how')), false);
  } finally { rmSync(home, { recursive: true, force: true }); }
});
test('preflight collisions do not partially install; project scope is explicit', () => {
  const project = mkdtempSync(join(tmpdir(), 'pstack project '));
  try {
    mkdirSync(join(project, '.claude/skills/how'), { recursive: true });
    writeFileSync(join(project, '.claude/skills/how/SKILL.md'), 'user skill');
    const args = ['--project', project, '--host', 'both', '--apply'];
    assert.equal(run(args).status, 1);
    assert.equal(existsSync(join(project, '.agents')), false);
    assert.equal(readFileSync(join(project, '.claude/skills/how/SKILL.md'), 'utf8'), 'user skill');
    rmSync(join(project, '.claude/skills/how'), { recursive: true });
    assert.equal(run(args).status, 0);
    assert.equal(existsSync(join(project, '.codex/agents/comment-sicko.toml')), true);
    assert.equal(run(['uninstall', ...args]).status, 0);
    assert.equal(existsSync(join(project, '.codex/agents/comment-sicko.toml')), false);
  } finally { rmSync(project, { recursive: true, force: true }); }
});
test('rerun updates unchanged owned agent copies and preserves edited copies', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'pstack update '));
  try {
    const source = join(scratch, 'checkout'), home = join(scratch, 'home');
    for (const dir of ['scripts', 'skills/fixture', 'agents/codex', 'agents/claude']) mkdirSync(join(source, dir), { recursive: true });
    copyFileSync(join(root, 'scripts/install.mjs'), join(source, 'scripts/install.mjs'));
    writeFileSync(join(source, 'skills/fixture/SKILL.md'), '---\nname: fixture\ndescription: fixture\n---\n');
    const agent = join(source, 'agents/codex/fixture.toml');
    writeFileSync(agent, 'original agent\n');
    const invoke = () => spawnSync(process.execPath, [join(source, 'scripts/install.mjs'), '--home', home, '--host', 'codex', '--apply'], { encoding: 'utf8' });
    assert.equal(invoke().status, 0);
    writeFileSync(agent, 'updated agent\n');
    const receipt = join(home, '.codex/pstack-install.json');
    const interrupted = JSON.parse(readFileSync(receipt, 'utf8'));
    interrupted.agents['fixture.toml'] = [interrupted.agents['fixture.toml'], createHash('sha256').update(readFileSync(agent)).digest('hex')];
    writeFileSync(receipt, JSON.stringify(interrupted));
    assert.equal(invoke().status, 0);
    const installed = join(home, '.codex/agents/fixture.toml');
    assert.equal(readFileSync(installed, 'utf8'), 'updated agent\n');
    writeFileSync(installed, 'user override\n');
    writeFileSync(agent, 'third version\n');
    assert.equal(invoke().status, 1);
    assert.equal(readFileSync(installed, 'utf8'), 'user override\n');
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
