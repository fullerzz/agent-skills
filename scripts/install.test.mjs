import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, existsSync, writeFileSync, readFileSync, realpathSync, readlinkSync, unlinkSync, symlinkSync, rmSync, copyFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const run = args => spawnSync('uv', ['run', '--script', join(root, 'scripts/install.py'), ...args], { encoding: 'utf8' });
test('empty explicit scopes fail before touching personal configuration', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'zstack empty scope '));
  try {
    const home = join(scratch, 'home');
    const codex = join(scratch, 'codex'), claude = join(scratch, 'claude');
    const env = { ...process.env, HOME: home, CODEX_HOME: codex, CLAUDE_CONFIG_DIR: claude };
    for (const scope of ['--home', '--project']) {
      for (const action of ['install', 'uninstall']) {
        const result = spawnSync('uv', ['run', '--script', join(root, 'scripts/install.py'), action, scope, '', '--apply'], { encoding: 'utf8', env });
        assert.equal(result.status, 1, result.stderr);
        assert.match(result.stderr, /must not be empty/);
        assert.equal(result.stdout, '');
        for (const target of [join(home, '.agents'), codex, claude]) assert.equal(existsSync(target), false);
      }
    }
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
test('native personal roots are honored; explicit home and project remain isolated', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'zstack native roots '));
  try {
    const codex = join(scratch, 'codex config'), claude = join(scratch, 'claude config');
    const env = { ...process.env, CODEX_HOME: codex, CLAUDE_CONFIG_DIR: claude };
    const invoke = args => spawnSync('uv', ['run', '--script', join(root, 'scripts/install.py'), ...args], { encoding: 'utf8', env });
    const preview = invoke(['--host', 'claude']);
    assert.equal(preview.status, 0);
    assert.ok(invoke(['--host', 'codex']).stdout.includes(`create\t${join(codex, 'agents/z-agent.toml')}\t`));
    assert.ok(preview.stdout.includes(`create\t${join(claude, 'skills/how')}\t`));
    assert.equal(invoke(['--host', 'claude', '--apply']).status, 0);
    assert.equal(realpathSync(join(claude, 'skills/how')), join(root, 'skills/how'));
    assert.equal(existsSync(join(claude, 'agents/z-agent.md')), true);
    assert.equal(invoke(['uninstall', '--host', 'claude', '--apply']).status, 0);
    assert.equal(existsSync(join(claude, 'agents/z-agent.md')), false);
    for (const scope of ['--home', '--project']) {
      const target = join(scratch, scope.slice(2)); mkdirSync(target, { recursive: true });
      assert.equal(invoke([scope, target, '--host', 'both', '--apply']).status, 0);
      assert.equal(existsSync(join(target, '.claude/skills/how')), true);
      assert.equal(existsSync(join(target, '.codex/agents/z-agent.toml')), true);
      assert.equal(existsSync(join(claude, 'skills/how')), false);
    }
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
test('install preview, rerun, collision, and owned removal for both hosts', () => {
  const home = mkdtempSync(join(tmpdir(), 'zstack home '));
  try {
    const args = ['--home', home, '--host', 'both'];
    assert.equal(run(args).status, 0);
    assert.equal(existsSync(join(home, '.agents')), false);
    assert.equal(run([...args, '--apply']).status, 0);
    const missingCopy = join(home, '.codex/agents/z-agent.toml');
    unlinkSync(missingCopy);
    assert.equal(run([...args, '--apply']).status, 0);
    assert.equal(readFileSync(missingCopy, 'utf8'), readFileSync(join(root, 'agents/codex/z-agent.toml'), 'utf8'));
    assert.equal(realpathSync(join(home, '.agents/skills/how')), join(root, 'skills/how'));
    assert.equal(realpathSync(join(home, '.claude/skills/how')), join(root, 'skills/how'));
    assert.match(readFileSync(join(home, '.codex/agents/z-agent.toml'), 'utf8'), /developer_instructions/);
    assert.match(readFileSync(join(home, '.claude/agents/comment-sicko.md'), 'utf8'), /model: inherit/);
    assert.equal(run([...args, '--apply']).status, 0);
    const modified = join(home, '.claude/agents/z-agent.md');
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
    assert.equal(existsSync(join(home, '.codex/agents/z-agent.toml')), false);
    assert.equal(existsSync(join(home, '.claude/skills/how')), false);
  } finally { rmSync(home, { recursive: true, force: true }); }
});
test('preflight collisions do not partially install; project scope is explicit', () => {
  const project = mkdtempSync(join(tmpdir(), 'zstack project '));
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
test('force replaces conflicting skills only when applied and preserves symlink destinations', () => {
  const home = mkdtempSync(join(tmpdir(), 'zstack force '));
  try {
    const args = ['--home', home, '--host', 'both', '--force'];
    const foreign = join(home, 'foreign');
    mkdirSync(foreign);
    writeFileSync(join(foreign, 'SKILL.md'), 'foreign skill');
    const targets = [];
    for (const native of ['.agents', '.claude']) {
      const skills = join(home, native, 'skills');
      mkdirSync(join(skills, 'how'), { recursive: true });
      writeFileSync(join(skills, 'how/SKILL.md'), 'old skill');
      writeFileSync(join(skills, 'why'), 'old file');
      symlinkSync(foreign, join(skills, 'teach'));
      symlinkSync(join(home, 'missing'), join(skills, 'recall'));
      targets.push(...['how', 'why', 'teach', 'recall'].map(name => [join(skills, name), name]));
    }
    const preview = run(args);
    assert.equal(preview.status, 0, preview.stderr);
    for (const [target] of targets) assert.ok(preview.stdout.includes(`replace\t${target}\t`));
    assert.equal(readFileSync(join(home, '.agents/skills/how/SKILL.md'), 'utf8'), 'old skill');
    assert.equal(readFileSync(join(home, '.claude/skills/why'), 'utf8'), 'old file');
    assert.equal(readlinkSync(join(home, '.agents/skills/recall')), join(home, 'missing'));
    assert.equal(existsSync(join(home, '.codex')), false);
    const agent = join(home, '.claude/agents/z-agent.md');
    mkdirSync(dirname(agent), { recursive: true });
    writeFileSync(agent, 'custom agent');
    const blocked = run([...args, '--apply']);
    assert.equal(blocked.status, 1);
    assert.match(blocked.stderr, /Existing files conflict/);
    assert.equal(readFileSync(agent, 'utf8'), 'custom agent');
    assert.equal(readFileSync(join(home, '.agents/skills/how/SKILL.md'), 'utf8'), 'old skill');
    unlinkSync(agent);
    const applied = run([...args, '--apply']);
    assert.equal(applied.status, 0, applied.stderr);
    for (const [target, name] of targets) assert.equal(realpathSync(target), join(root, 'skills', name));
    assert.equal(readFileSync(join(foreign, 'SKILL.md'), 'utf8'), 'foreign skill');
    assert.equal(run([...args, '--apply']).status, 0);
    unlinkSync(join(home, '.agents/skills/teach'));
    symlinkSync(foreign, join(home, '.agents/skills/teach'));
    assert.equal(run(['uninstall', ...args, '--apply']).status, 0);
    assert.equal(readlinkSync(join(home, '.agents/skills/teach')), foreign);
  } finally { rmSync(home, { recursive: true, force: true }); }
});
test('rerun updates unchanged owned agent copies and preserves edited copies', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'zstack update '));
  try {
    const source = join(scratch, 'checkout'), home = join(scratch, 'home');
    for (const dir of ['scripts', 'skills/fixture', 'agents/codex', 'agents/claude']) mkdirSync(join(source, dir), { recursive: true });
    copyFileSync(join(root, 'scripts/install.py'), join(source, 'scripts/install.py'));
    writeFileSync(join(source, 'skills/fixture/SKILL.md'), '---\nname: fixture\ndescription: fixture\n---\n');
    const agent = join(source, 'agents/codex/fixture.toml');
    writeFileSync(agent, 'original agent\n');
    const invoke = () => spawnSync('uv', ['run', '--script', join(source, 'scripts/install.py'), '--home', home, '--host', 'codex', '--apply'], { encoding: 'utf8' });
    assert.equal(invoke().status, 0);
    writeFileSync(agent, 'updated agent\n');
    const receipt = join(home, '.codex/zstack-install.json');
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
test('receipts reject symlinks and invalid ownership; agent symlinks remain unowned', () => {
  const home = mkdtempSync(join(tmpdir(), 'zstack receipts '));
  try {
    const args = ['--home', home, '--host', 'codex', '--apply'];
    const native = join(home, '.codex');
    mkdirSync(native);
    const receipt = join(native, 'zstack-install.json');
    const foreign = join(home, 'foreign receipt.json');
    writeFileSync(foreign, 'user receipt\n');
    symlinkSync(foreign, receipt);
    assert.equal(run(args).status, 1);
    assert.equal(readFileSync(foreign, 'utf8'), 'user receipt\n');
    assert.equal(existsSync(join(home, '.agents')), false);
    unlinkSync(receipt);
    for (const contents of ['{invalid json', 'null', JSON.stringify({ source: root, agents: [] }), JSON.stringify({ source: root, agents: { 'z-agent.toml': {} } }), JSON.stringify({ source: '/other-checkout', agents: {} })]) {
      writeFileSync(receipt, contents);
      assert.equal(run(args).status, 1);
      assert.equal(readFileSync(receipt, 'utf8'), contents);
      assert.equal(existsSync(join(home, '.agents')), false);
    }
    unlinkSync(receipt);
    assert.equal(run(args).status, 0);
    const installed = join(native, 'agents/z-agent.toml');
    unlinkSync(installed);
    const source = join(root, 'agents/codex/z-agent.toml');
    symlinkSync(source, installed);
    assert.equal(run(args).status, 1);
    assert.equal(run(['uninstall', ...args]).status, 0);
    assert.equal(readlinkSync(installed), source);
  } finally { rmSync(home, { recursive: true, force: true }); }
});

test('legacy installs migrate owned receipts and names while preserving modified copies', () => {
  const home = mkdtempSync(join(tmpdir(), 'zstack migration '));
  try {
    const args = ['--home', home, '--host', 'codex'];
    assert.equal(run([...args, '--apply']).status, 0);
    const native = join(home, '.codex');
    const receipt = join(native, 'zstack-install.json');
    const oldReceipt = join(native, 'pstack-install.json');
    const saved = JSON.parse(readFileSync(receipt, 'utf8'));
    const oldAgent = join(native, 'agents/poteto-agent.toml');
    writeFileSync(oldAgent, 'old owned agent\n');
    saved.agents['poteto-agent.toml'] = createHash('sha256').update(readFileSync(oldAgent)).digest('hex');
    writeFileSync(oldReceipt, JSON.stringify(saved));
    unlinkSync(receipt);
    const oldSkill = join(home, '.agents/skills/poteto-mode');
    symlinkSync(join(root, 'skills/poteto-mode'), oldSkill);
    const oldSetup = join(home, '.agents/skills/setup-pstack');
    symlinkSync(join(root, 'skills/setup-pstack'), oldSetup);
    const preview = run(args);
    assert.equal(preview.status, 0, preview.stderr);
    assert.ok(preview.stdout.includes(`remove\t${oldAgent}\t`));
    assert.equal(existsSync(oldReceipt), true);
    assert.equal(readlinkSync(oldSkill), join(root, 'skills/poteto-mode'));
    assert.equal(run([...args, '--apply']).status, 0);
    assert.equal(existsSync(oldReceipt), false);
    assert.equal(existsSync(oldAgent), false);
    assert.throws(() => readlinkSync(oldSkill), /ENOENT/);
    assert.throws(() => readlinkSync(oldSetup), /ENOENT/);
    assert.equal(realpathSync(join(home, '.agents/skills/z-mode')), join(root, 'skills/z-mode'));
    assert.equal(existsSync(join(native, 'agents/z-agent.toml')), true);
    const migrated = JSON.parse(readFileSync(receipt, 'utf8'));
    writeFileSync(oldAgent, 'user override\n');
    migrated.agents['poteto-agent.toml'] = saved.agents['poteto-agent.toml'];
    writeFileSync(receipt, JSON.stringify(migrated));
    const result = run([...args, '--apply']);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Preserved unowned or modified files/);
    assert.equal(readFileSync(oldAgent, 'utf8'), 'user override\n');
    assert.equal(JSON.parse(readFileSync(receipt, 'utf8')).agents['poteto-agent.toml'], saved.agents['poteto-agent.toml']);
  } finally { rmSync(home, { recursive: true, force: true }); }
});
