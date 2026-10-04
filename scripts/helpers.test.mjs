import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync, execFileSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
test('installed resources inspect a separate repo with spaces and protect unknown history/files', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'zstack fixture '));
  const repo = join(scratch, 'target repo'); mkdirSync(repo);
  try {
    const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8' });
    git('init', '-b', 'main'); git('config', 'user.name', 'Fixture'); git('config', 'user.email', 'fixture@example.invalid');
    writeFileSync(join(repo, 'note.txt'), 'baseline'); git('add', 'note.txt'); git('commit', '-m', 'fixture');
    const clean = join(scratch, 'clean worktree'), dirty = join(scratch, 'dirty worktree');
    git('worktree', 'add', '-b', 'clean', clean); git('worktree', 'add', '-b', 'dirty', dirty);
    writeFileSync(join(dirty, 'untracked.txt'), 'must preserve');
    const ignored = join(scratch, 'ignored worktree'), locked = join(scratch, 'locked worktree'), missing = join(scratch, 'missing worktree');
    git('worktree', 'add', '--detach', ignored);
    writeFileSync(join(ignored, '.gitignore'), 'cache/\n');
    execFileSync('git', ['-C', ignored, 'add', '.gitignore']);
    execFileSync('git', ['-C', ignored, 'commit', '-m', 'ignore cache']);
    mkdirSync(join(ignored, 'cache')); writeFileSync(join(ignored, 'cache/proof'), 'ignored work');
    git('worktree', 'add', '--detach', locked); git('worktree', 'lock', locked);
    git('worktree', 'add', '--detach', missing); rmSync(missing, { recursive: true });
    assert.equal(spawnSync('uv', ['run', '--script', join(root, 'scripts/install.py'), '--project', repo, '--apply']).status, 0);
    const skill = dirname(realpathSync(join(repo, '.agents/skills/z-mode/SKILL.md')));
    assert.equal(realpathSync(join(skill, '../how/SKILL.md')), join(root, 'skills/how/SKILL.md'));
    const audit = spawnSync('bash', [join(skill, 'scripts/worktree-audit.sh'), repo], { cwd: repo, encoding: 'utf8' });
    assert.equal(audit.status, 0, audit.stderr);
    assert.match(audit.stdout, new RegExp('REPO\\t' + realpathSync(repo)));
    assert.match(audit.stdout, /unknown\treview-history-unknown\t.*clean worktree/);
    assert.match(audit.stdout, /unknown\thold-files\t.*dirty worktree/);
    assert.match(audit.stdout, /unknown\thold-files\t.*ignored worktree/);
    assert.match(audit.stdout, /unknown\thold-unavailable\t.*locked worktree/);
    assert.match(audit.stdout, /unknown\thold-unavailable\t.*missing worktree/);
    assert.doesNotMatch(audit.stdout, /\tsafe\t/);
    assert.equal(readFileSync(join(dirty, 'untracked.txt'), 'utf8'), 'must preserve');
    const log = join(repo, 'proof trail.tsv');
    const logger = dirname(realpathSync(join(repo, '.claude/skills/show-me-your-work/SKILL.md')));
    const result = spawnSync('bash', [join(logger, 'scripts/log.sh'), log, 'verify', '=formula', 'reason\nline', 'file\tpath', 'passed'], { cwd: repo });
    assert.equal(result.status, 0);
    assert.match(readFileSync(log, 'utf8'), /\t'=formula\treason line\tfile path\tpassed/);
    assert.equal(git('status', '--porcelain').includes('note.txt'), false);
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
test('plan validator accepts task-sized proof and rejects missing phase checks', () => {
  const scratch = mkdtempSync(join(tmpdir(), 'zstack plan '));
  try {
    const file = join(scratch, 'plan.md');
    const plan = '# Small migration\n\n## Outcome\nNew path works\n## Scope\nOne module\n## Phases\n### Move\n- Depends on: None\n- Files: parser.ts\n- Acceptance: Same output\n- Verification: Run the fixture command\n## Risks\nNone identified\n## Handoff\nLocal edits only\n';
    writeFileSync(file, plan);
    const run = () => spawnSync('uv', ['run', join(root, 'skills/z-mode/scripts/check_plan.py'), file], { encoding: 'utf8' });
    assert.equal(run().status, 0);
    for (const field of ['Depends on', 'Files', 'Acceptance', 'Verification']) {
      writeFileSync(file, plan.replace(new RegExp('(- ' + field + ':)[^\\n]*'), '$1'));
      assert.equal(run().status, 1, `empty ${field} must not borrow the next line`);
    }
    writeFileSync(file, plan.replace('- Verification: Run the fixture command\n', ''));
    assert.equal(run().status, 1);
    assert.match(run().stderr, /Verification/);
  } finally { rmSync(scratch, { recursive: true, force: true }); }
});
