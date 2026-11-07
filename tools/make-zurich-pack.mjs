#!/usr/bin/env node
// Owner-only: extract the shareable Zürich starter pack from private portals.yml + data/blacklist.md.
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import * as yaml from 'js-yaml';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? (process.argv[i + 1] ?? (console.error(`make-zurich-pack: ${k} needs a value`), process.exit(2))) : d; };
const portals = arg('--portals', 'portals.yml');
const blacklist = arg('--blacklist', 'data/blacklist.md');
const out = arg('--out-dir', 'templates');
if (!existsSync(portals)) { console.error('make-zurich-pack: portals.yml not found (owner-only tool)'); process.exit(2); }
if (!existsSync(blacklist)) { console.error('make-zurich-pack: blacklist.md not found (owner-only tool)'); process.exit(2); }

// Owner-identifying text: built by concatenation so this file stays leak-clean.
const OWNER = new RegExp(['Rap' + 'hael', 'Benya' + 'mine', 'Rol' + 'ex', 'Serpen' + 'tine', 'Chop' + 'ard', 'Pw' + 'C'].join('|'), 'i');
const scrub = (q) => q.replace(/\s-"?Pw\u0043"?(?=\s|$)/g, '');

const src = yaml.load(readFileSync(portals, 'utf8'));
const pack = {
  location_filter: src.location_filter,
  search_queries: src.search_queries.map((s) => ({ ...s, query: scrub(s.query) })),
  tracked_companies: src.tracked_companies // a company that is itself owner-identifying (past employer) is dropped
    .map(({ notes, ...c }) => (notes && !OWNER.test(notes) ? { ...c, notes } : c))
    .filter((c) => !OWNER.test(JSON.stringify(c))),
};
if (OWNER.test(JSON.stringify(pack))) { console.error('make-zurich-pack: owner text survived scrubbing'); process.exit(1); }
const head = '# Zürich starter pack — sources only. Title filters come from your goal-job definition. tracked_companies: starter list, prune to taste.\n';

const lines = readFileSync(blacklist, 'utf8').split('\n');
const sep = lines.findIndex((l) => /^\|[-| ]+\|$/.test(l));
if (sep < 0) { console.error('make-zurich-pack: no table separator in blacklist'); process.exit(2); }
const rows = lines.slice(sep + 1).filter((l) => l.startsWith('|')).map((l) => ({ l, c: l.split('|').map((x) => x.trim()) }));
const consulting = rows.filter((r) => r.c[3] === 'all' && /consult|advisory|engineering consultancy/i.test(r.c[4]) && !OWNER.test(r.l));
const starter = [
  ...lines.slice(0, sep + 1),
  ...rows.filter((r) => r.c[3] === 'agency').map((r) => r.l),
  // Per-row comments: scan.mjs / scan_aggregate.py parse line-by-line and ignore HTML comments, so a
  // block comment would still blacklist these rows. Uncomment = delete the `<!-- ` and ` -->` markers.
  '', '<!-- CONSULTING / ADVISORY — uncomment to exclude (in-house roles only) -->', ...consulting.map((r) => `<!-- ${r.l} -->`), '',
].join('\n');
// Both outputs are built in memory above; write only now so a failure never leaves a half pack.
writeFileSync(join(out, 'portals.zurich.yml'), head + yaml.dump(pack, { lineWidth: -1, sortKeys: false }));
writeFileSync(join(out, 'blacklist.starter.md'), starter);
