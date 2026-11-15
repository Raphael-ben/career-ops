#!/usr/bin/env node
// appflowy-export.mjs — regenerate an AppFlowy-importable CSV (JOB OP columns) from data/applications.md.
// Usage: node tools/appflowy-export.mjs [--selftest]   (no deps; run from anywhere)
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { resolveColumns, parseTrackerRow, isSeparatorRow } from '../tracker-parse.mjs';

export const HEADER = ['Name', 'Position', 'Status', 'Application date', 'first answer date', 'First ITW', 'Rejection date',
  'Available From', 'URL', 'Location', 'Zipcode', 'ATS Platform', 'Match Score', 'Expected Salary', 'Salary Currency',
  'Current Salary', 'CV', 'Cover Letter', 'Job description', 'Rejection reason', 'RAV Disclosed'];

// Hired -> Interview: JOB OP has no Hired/Offer option. null = row omitted.
const STATUS = { evaluated: 'To apply', applied: 'Applied', responded: 'In progress', interview: 'Interview',
  offer: 'In progress', hired: 'Interview', rejected: 'Rejected', discarded: null, skip: null };

const csv = (v) => (/[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);

function newest(dir, re) {
  let best = null;
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (re.test(e.name) && (!best || statSync(p).mtimeMs > best.t)) best = { p, t: statSync(p).mtimeMs };
    }
  };
  if (existsSync(dir)) walk(dir);
  return best?.p;
}

export function build(root) {
  const lines = readFileSync(join(root, 'data/applications.md'), 'utf8').split('\n');
  const colmap = resolveColumns(lines);
  const out = [HEADER.join(',')];
  for (const line of lines) {
    if (isSeparatorRow(line)) continue;
    const r = parseTrackerRow(line, colmap);
    if (!r) continue;
    const status = STATUS[r.status.replace(/\*\*/g, '').trim().toLowerCase()];
    if (status === null) continue;
    const m = r.score.replace(/\*\*/g, '').match(/^(\d+(?:\.\d+)?)\/5$/);
    const dir = join(root, 'output', r.company);
    const rel = (p) => (p ? relative(root, p) : '');
    const row = Object.fromEntries(HEADER.map((h) => [h, '']));
    Object.assign(row, { Name: r.company, Position: r.role, Status: status ?? 'To apply', 'Application date': r.date,
      URL: r.url, 'Match Score': m ? m[1] : '', CV: rel(newest(dir, /_CV\.pdf$/i)),
      'Cover Letter': rel(newest(dir, /cover-letter.*\.pdf$/i)) });
    out.push(HEADER.map((h) => csv(row[h])).join(','));
  }
  return out;
}

function selftest() {
  const root = mkdtempSync(join(tmpdir(), 'afexp-'));
  try {
    mkdirSync(join(root, 'data'));
    mkdirSync(join(root, 'output/Acme/x'), { recursive: true });
    writeFileSync(join(root, 'output/Acme/x/A_CV.pdf'), '');
    writeFileSync(join(root, 'output/Acme/x/A_cover-letter.pdf'), '');
    writeFileSync(join(root, 'data/applications.md'), [
      '| # | Date | Company | Role | Score | Status | PDF | Report | Notes |', '|---|---|---|---|---|---|---|---|---|',
      '| 1 | 2026-01-02 | Acme | PMM, EMEA | 4.0/5 | Applied | ✅ | - | |',
      '| 2 | 2026-01-03 | Beta | Dev | N/A | Evaluated | ❌ | - | |',
      '| 3 | 2026-01-04 | Gone | Ops | 3.0/5 | Discarded | ❌ | - | |',
      '| 4 | 2026-01-05 | Hi | Lead | 4.5/5 | Hired | ❌ | - | |', ''].join('\n'));
    const o = build(root);
    assert.equal(o.length, 4);
    assert.equal(o[1], 'Acme,"PMM, EMEA",Applied,2026-01-02,,,,,,,,,4.0,,,,output/Acme/x/A_CV.pdf,output/Acme/x/A_cover-letter.pdf,,,');
    assert.match(o[2], /^Beta,Dev,To apply,2026-01-03,.*,,,,,,,,,,,,,$/);
    assert.ok(!o.some((l) => l.startsWith('Gone')));
    assert.match(o[3], /^Hi,Lead,Interview,2026-01-05,.*4\.5/);
    console.log('appflowy-export selftest: ok');
  } finally { rmSync(root, { recursive: true, force: true }); }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--selftest')) selftest();
  else {
    const root = join(dirname(fileURLToPath(import.meta.url)), '..');
    const rows = build(root);
    mkdirSync(join(root, 'data/appflowy'), { recursive: true });
    writeFileSync(join(root, 'data/appflowy/job-op.csv'), rows.join('\n') + '\n');
    console.log(`appflowy-export: ${rows.length - 1} rows → data/appflowy/job-op.csv`);
  }
}
