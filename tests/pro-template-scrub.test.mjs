import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
// Built by concatenation so this file itself passes leak-check.
const OWNER = ['Pw' + 'C', 'Serpen' + 'tine', 'Rol' + 'ex', 'Chop' + 'ard', 'Benya' + 'mine', 'Raph' + 'ael'];
const PATTERNS = process.env.JOBHUNTER_PII_PATTERNS || join(process.env.HOME, 'Claude-code/job-hunter-data/pii-patterns.txt');

test('pro CV template body carries no owner employers', () => {
  const tex = readFileSync(join(ROOT, 'templates/cv-template-pro.tex'), 'utf8');
  for (const s of OWNER)
    assert.ok(!tex.includes(s), `found ${s}`);
  assert.ok(tex.includes('%%FILL:candidate.name%%'));
  assert.ok(tex.includes('Acme Software AG'));
});
test('_custom.md is owner-neutral', () => {
  const md = readFileSync(join(ROOT, 'modes/_custom.md'), 'utf8');
  assert.ok(!md.includes(OWNER[5])); assert.ok(md.includes('apply.browser'));
});
test('leak-check catches the bare surname and employers', () => {
  const dir = mkdtempSync(join(tmpdir(), 'leak-'));
  spawnSync('git', ['init', '-q', dir]);
  const run = () => spawnSync('bash', [join(ROOT, 'tools/leak-check.sh'), '--worktree', dir, PATTERNS], { encoding: 'utf8' });
  writeFileSync(join(dir, 'x.md'), `Worked with ${OWNER[4]} at ${OWNER[0]} and ${OWNER[2]}.`);
  spawnSync('git', ['-C', dir, 'add', '.']);
  assert.notEqual(run().status, 0, 'leak-check must fail on owner surname/employers');
  writeFileSync(join(dir, 'x.md'), 'Worked with Alex Muster at Acme Software AG.');
  assert.equal(run().status, 0);
});

test('pro fill-specs shipped and owner-neutral', () => {
  for (const f of ['templates/cv-fill-spec.pro.md', 'templates/cl-fill-spec.pro.md']) {
    const md = readFileSync(join(ROOT, f), 'utf8');
    for (const s of [...OWNER, 'Pila' + 'tus']) assert.ok(!md.includes(s), `${f}: ${s}`);
  }
  const prot = readFileSync(join(ROOT, 'tools/protected-paths.txt'), 'utf8');
  for (const p of ['templates/cv-fill-spec.pro.md', 'templates/cl-fill-spec.pro.md', 'modes/pro/onboarding.md', 'templates/portals.zurich.yml', 'templates/blacklist.starter.md', 'tools/make-zurich-pack.mjs'])
    assert.ok(prot.includes(p), p);
});
