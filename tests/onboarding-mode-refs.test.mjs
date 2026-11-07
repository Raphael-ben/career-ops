import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

test('onboarding.md references only scripts that exist and all nine phases', () => {
  const md = readFileSync(join(ROOT, 'modes/pro/onboarding.md'), 'utf8');
  const refs = [...md.matchAll(/`(?:node|\{PYTHON\}|python3) ([\w.-]+\.(?:mjs|py))/g)].map(m => m[1]);
  assert.ok(refs.length >= 5, `expected script references, got ${refs.length}`);
  for (const r of refs) assert.ok(existsSync(join(ROOT, r)), r);
  for (let p = 0; p <= 9; p++) assert.match(md, new RegExp(`^## Phase ${p}\\b`, 'm'));
  assert.ok(md.includes('scan.scrapers')); assert.ok(md.includes('language.warned'));
  assert.ok(md.includes('onboard-write.mjs --answers')); assert.ok(md.includes('npm run ui'));
  assert.match(md, /tracker\.type.*notion.*markdown.*dashboard/);
  const owner = new RegExp(['Pw' + 'C', 'Ro' + 'lex', 'Rap' + 'hael', 'Serp' + 'entine', 'Cho' + 'pard'].join('|'));
  assert.ok(!owner.test(md));
});

test('modes/onboarding.md is a pointer to the pro mode', () => {
  const md = readFileSync(join(ROOT, 'modes/onboarding.md'), 'utf8');
  assert.ok(md.includes('modes/pro/onboarding.md'));
  assert.ok(md.trim().split('\n').length <= 3);
});
