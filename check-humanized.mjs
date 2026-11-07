#!/usr/bin/env node
// pro/ pipeline mechanical lint: cv-voice wording/dash check per .tex (profile_bank text is the
// candidate's own wording) + humanizer_report.json must be newer than every .tex it covers.
// cv-voice.mjs itself has no CLI (library only: `node cv-voice.mjs x.tex` silently exits 0).
// Usage: node check-humanized.mjs <profile_bank.json> <file.tex>...   exit 0 clean, 1 any hit.
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { BANNED_PHRASES, voiceIssues } from './cv-voice.mjs';

const [bankPath, ...texs] = process.argv.slice(2);
if (!bankPath || !texs.length) { console.error('Usage: node check-humanized.mjs <profile_bank.json> <file.tex>...'); process.exit(1); }
const bank = JSON.parse(readFileSync(bankPath, 'utf8'));
const strings = (v) => (typeof v === 'string' ? [v] : v && typeof v === 'object' ? Object.values(v).flatMap(strings) : []);
const h = bank.humanize ?? {};
// ponytail: extends cv-voice's exported list in place. Qualified entries ("key (adjective)") need
// judgement, so only bare words/phrases are enforced mechanically; humanize.md handles the rest.
for (const w of [h.banned_words, h.banned_words_de, h.banned_words_fr, h.banned_bullet_openers].flat()) {
  if (typeof w === 'string' && !/[()/]/.test(w) && !BANNED_PHRASES.includes(w.toLowerCase())) BANNED_PHRASES.push(w.toLowerCase());
}
// the ban lists themselves must not count as "candidate's own wording"
const source = strings({ ...bank, humanize: null, verify: null }).join('\n');
let bad = 0;
for (const tex of texs) {
  // numbers are verify-cv-facts.mjs's job (it takes the computed-facts --source); not double-gated here
  const issues = voiceIssues(readFileSync(tex, 'utf8'), source).filter((i) => i.kind !== 'invented-number');
  for (const i of issues) { bad++; console.log(`${tex}: ${i.kind}: ${i.value}`); }
  const report = join(dirname(tex), 'humanizer_report.json');
  if (!existsSync(report)) { bad++; console.log(`${tex}: humanizer_report.json missing`); }
  else if (statSync(report).mtimeMs < statSync(tex).mtimeMs) { bad++; console.log(`${tex}: edited after humanizer_report.json (stale report, re-run humanize)`); }
}
console.log(bad ? `FAIL: ${bad} issue(s)` : 'PASS');
process.exit(bad ? 1 : 0);
