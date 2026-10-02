#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
try {
  const args = process.argv.slice(2);
  const withPrs = args.includes('--with-prs');
  const paths = args.filter(a => a !== '--with-prs');
  if (paths.length > 1 || paths.some(p => p.startsWith('-'))) throw new Error('Usage: worktree-audit.sh [repo-path] [--with-prs]');
  const git = (cwd, ...args) => execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' } });
  const repo = git(resolve(paths[0] ?? '.'), 'rev-parse', '--show-toplevel').trim();
  let prs = [], prEvidence = 'unknown';
  if (withPrs) {
    try { prs = JSON.parse(execFileSync('gh', ['pr', 'list', '--state', 'all', '--limit', '1000', '--json', 'number,state,headRefName'], { cwd: repo, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })); prEvidence = 'not-found'; }
    catch { console.error('PR lookup unavailable; PR state is unknown.'); }
  }
  const records = git(repo, 'worktree', 'list', '--porcelain', '-z').split('\0\0').filter(Boolean).map(block => Object.fromEntries(block.split('\0').filter(Boolean).map(field => { const i = field.indexOf(' '); return i < 0 ? [field, true] : [field.slice(0, i), field.slice(i + 1)]; })));
  console.log('REPO\t' + repo);
  console.log('HEAD\tMERGED\tDIRTY\tPR\tHISTORY\tBUCKET\tWORKTREE');
  for (const record of records) {
    const wt = record.worktree;
    if (wt === repo) continue;
    let dirty = 'unknown', merged = 'unknown', bucket = 'review-unknown';
    try {
      const status = git(wt, 'status', '--porcelain', '--untracked-files=all', '--ignored=matching');
      dirty = status ? 'has-files' : 'clean';
      try { git(wt, 'merge-base', '--is-ancestor', record.HEAD, 'refs/remotes/origin/main'); merged = 'yes-local-ref'; } catch { merged = 'no-or-unknown'; }
      bucket = status ? 'hold-files' : 'review-history-unknown';
    } catch {}
    if (record.locked || record.prunable) bucket = 'hold-unavailable';
    const branch = typeof record.branch === 'string' ? record.branch.replace(/^refs\/heads\//, '') : '';
    const matches = prs.filter(p => p.headRefName === branch);
    const pr = matches.length ? matches.map(p => '#' + p.number + '/' + p.state).join(',') : prEvidence;
    if (matches.some(p => p.state === 'OPEN')) bucket = 'hold-open-pr';
    console.log([record.HEAD, merged, dirty, pr, 'unknown', bucket, wt].map(c => String(c ?? 'unknown').replace(/[\t\r\n]/g, ' ')).join('\t'));
  }
} catch (error) { console.error(error.message); process.exitCode = 1; }
