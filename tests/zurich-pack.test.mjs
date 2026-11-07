import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseBlacklist } from '../scan.mjs';
import { mkdtempSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import * as yaml from 'js-yaml';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OWNER = ['Rap' + 'hael', 'Rol' + 'ex', 'Serpen' + 'tine', 'Chop' + 'ard', 'Pw' + 'C'];

test('pack has sources only, no title filter', () => {
  const y = yaml.load(readFileSync(join(ROOT, 'templates/portals.zurich.yml'), 'utf8'));
  assert.deepEqual(Object.keys(y).sort(), ['location_filter', 'search_queries', 'tracked_companies']);
  assert.ok(y.location_filter.allow.includes('Zürich')); assert.ok(y.location_filter.block.length > 0);
});
test('pack carries no owner-identifying text', () => {
  const txt = readFileSync(join(ROOT, 'templates/portals.zurich.yml'), 'utf8');
  for (const s of OWNER) assert.ok(!txt.includes(s), s);
});
test('starter blacklist: agencies active, consulting commented', () => {
  const md = readFileSync(join(ROOT, 'templates/blacklist.starter.md'), 'utf8');
  assert.match(md, /^\| Hays \|/m);
  assert.ok(!/^\| McKinsey \|/m.test(md)); assert.ok(/<!--[\s\S]*McKinsey[\s\S]*-->/.test(md));
  assert.ok(!md.includes('TW' + '1')); // personal 'all' row (applied + rejected)
  for (const s of OWNER) assert.ok(!md.includes(s), s);
});
test('refuses without portals.yml', () => {
  const r = spawnSync('node', [join(ROOT, 'tools/make-zurich-pack.mjs'), '--portals', '/nonexistent'], { encoding: 'utf8' });
  assert.equal(r.status, 2);
});
test('real parser: agencies blacklisted, commented consulting rows skipped', () => {
  const names = [...parseBlacklist(readFileSync(join(ROOT, 'templates/blacklist.starter.md'), 'utf8')).values()].map((e) => e.company);
  assert.ok(names.includes('Hays')); assert.ok(!names.includes('McKinsey'));
});
test('bad --blacklist exits 2 and writes no pack', () => {
  const dir = mkdtempSync(join(tmpdir(), 'zpack-'));
  const r = spawnSync('node', [join(ROOT, 'tools/make-zurich-pack.mjs'), '--portals', join(ROOT, 'templates/portals.zurich.yml'), '--blacklist', '/nonexistent', '--out-dir', dir], { encoding: 'utf8' });
  assert.equal(r.status, 2); assert.ok(!existsSync(join(dir, 'portals.zurich.yml')));
});
