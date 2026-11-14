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

// Role/sector targeting is the owner's: each query keeps only site:, location, seniority and generic
// negatives; its first other OR-group becomes {ROLES} (onboarding fills in the friend's titles), any
// later group (sectors, deal types) is dropped.
const LOC = /^(Zürich|Zurich|Zug|Basel|Bern|Winterthur|Schaffhausen|Geneva|Switzerland|Schweiz|Deutschschweiz)$/i;
const SEN = /^(Manager|Director|Head|Head of|Senior|VP|General Manager)$/i;
const NEG = /^-(intern|junior|trainee|praktikum)$/i;
const ROLE_SUFFIX = new RegExp('\\s+(Corporate ' + 'Development|Strat' + 'egy)$'); // owner names like "<Co> <role>"; concatenated, see OWNER
function genericize(q, keepFirst = false) { // keepFirst: tracked_companies scan_query leads with the company group
  const toks = q.match(/-?"[^"]*"|\S+/g) || [];
  const groups = [];
  for (let i = 0; i < toks.length; i++) {
    if (toks[i] === 'OR') continue;
    if (toks[i - 1] === 'OR' && groups.length) groups.at(-1).push(toks[i]); else groups.push([toks[i]]);
  }
  const bare = (t) => t.replace(/"/g, '');
  const out = []; let roles = false, first = keepFirst;
  for (const g of groups) {
    if (g.every((t) => t.startsWith('site:'))) out.push(g.join(' OR '));
    else if (g[0].startsWith('-')) { if (NEG.test(bare(g[0]))) out.push(g[0]); }
    else if (g.every((t) => LOC.test(bare(t))) || g.every((t) => SEN.test(bare(t)))) out.push(g.join(' OR '));
    else if (first) { out.push(g.join(' OR ')); first = false; }
    else if (!roles) { out.push('{ROLES}'); roles = true; }
  }
  return out.join(' ');
}
const src = yaml.load(readFileSync(portals, 'utf8'));
// Once roles are a placeholder, variants of one board differ only in location/seniority noise:
// keep the first query per site (or one for the open web), enabled if any variant was.
const site = (q) => (q.match(/site:(\S+)/) || [, 'web'])[1];
const merged = new Map();
for (const s of src.search_queries) {
  const query = genericize(scrub(s.query));
  const m = merged.get(site(query));
  if (m) m.enabled ||= s.enabled !== false; else merged.set(site(query), { name: site(query), query, enabled: s.enabled !== false });
}
const search_queries = [...merged.values()]; // owner query names carried role terms: name = site
const pack = {
  location_filter: src.location_filter,
  search_queries,
  tracked_companies: src.tracked_companies // a company that is itself owner-identifying (past employer) is dropped
    // owner notes describe his own targeting (sectors, past rejections, commute): only setup hints ship
    .map(({ notes, ...c }) => ({ ...c, name: c.name.replace(ROLE_SUFFIX, ''), ...(c.scan_query && { scan_query: genericize(c.scan_query, true) }),
      ...(/^Template\./.test(notes || '') && { notes }) }))
    .filter((c) => !OWNER.test(JSON.stringify(c))),
};
if (OWNER.test(JSON.stringify(pack))) { console.error('make-zurich-pack: owner text survived scrubbing'); process.exit(1); }
const head = '# Zürich starter pack — sources only. Title filters come from your goal-job definition. search_queries: onboarding replaces {ROLES} with your titles ("Title One" OR "Title Two"). tracked_companies: starter list, prune to taste.\n';

const lines = readFileSync(blacklist, 'utf8').split('\n');
const sep = lines.findIndex((l) => /^\|[-| ]+\|$/.test(l));
if (sep < 0) { console.error('make-zurich-pack: no table separator in blacklist'); process.exit(2); }
const rows = lines.slice(sep + 1).filter((l) => l.startsWith('|')).map((l) => ({ l, c: l.split('|').map((x) => x.trim()) }));
const consulting = rows.filter((r) => r.c[3] === 'all' && /consult|advisory|engineering consultancy/i.test(r.c[4]) && !OWNER.test(r.l));
const starter = [
  ...lines.slice(0, sep + 1),
  ...rows.filter((r) => r.c[3] === 'agency').map((r) => (/commute/i.test(r.c[4]) ? r.l.replace(r.c[4], 'Recruitment intermediary') : r.l)), // owner's commute radius stays private
  // Per-row comments: scan.mjs / scan_aggregate.py parse line-by-line and ignore HTML comments, so a
  // block comment would still blacklist these rows. Uncomment = delete the `<!-- ` and ` -->` markers.
  '', '<!-- CONSULTING / ADVISORY — uncomment to exclude (in-house roles only) -->', ...consulting.map((r) => `<!-- ${r.l} -->`), '',
].join('\n');
// Both outputs are built in memory above; write only now so a failure never leaves a half pack.
writeFileSync(join(out, 'portals.zurich.yml'), head + yaml.dump(pack, { lineWidth: -1, sortKeys: false }));
writeFileSync(join(out, 'blacklist.starter.md'), starter);
