#!/usr/bin/env node
// apply-data.mjs — builds apply.json (Workday form-filler data) from a tailored
// CV .tex plus profile_bank.json. Dates/months come from the bank, text from the CV.
//
// Usage: node apply-data.mjs <output-folder> [profile_bank.json]

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { isMainModule } from './lib/is-main-module.mjs';

const ACCENTS = { "'": '́', '`': '̀', '^': '̂', '"': '̈' };

export function stripLatex(s) {
  return s
    .replace(/\\([`'^"])\s*\{?([A-Za-z])\}?/g, (_, a, l) => l + ACCENTS[a])
    .normalize('NFC')
    .replace(/\\([&#%$_])/g, '$1')
    .replace(/---|--/g, '-')
    .replace(/~/g, ' ')
    .replace(/\\\\/g, ' ')
    .replace(/\\[A-Za-z]+\*?/g, '')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Reads one balanced {...} group at/after i (skipping whitespace); returns [content, nextIndex].
function readGroup(s, i) {
  while (/\s/.test(s[i] ?? '')) i++;
  if (s[i] !== '{') throw new Error(`Expected "{" near: ${s.slice(i, i + 40)}`);
  let depth = 0;
  for (let j = i; j < s.length; j++) {
    if (s[j] === '\\') { j++; continue; }
    if (s[j] === '{') depth++;
    else if (s[j] === '}' && --depth === 0) return [s.slice(i + 1, j), j + 1];
  }
  throw new Error('Unbalanced braces in CV');
}

function readBlocks(tex, env) {
  const out = [];
  const re = new RegExp(`\\\\begin\\{${env}\\}`, 'g');
  let m;
  while ((m = re.exec(tex))) {
    let i = m.index + m[0].length;
    const args = [];
    for (let k = 0; k < 5; k++) { const [g, n] = readGroup(tex, i); args.push(g); i = n; }
    const end = tex.indexOf(`\\end{${env}}`, i);
    const bullets = tex.slice(i, end).split(/\\item\b/).slice(1).map(stripLatex).filter(Boolean);
    const [dates, title, org, location] = args.map(stripLatex);
    out.push({ dates, title, org, location, bullets });
  }
  return out;
}

export function parseCv(tex) {
  const clean = tex.split('\n')
    .filter(l => !/^\s*%/.test(l))
    .map(l => l.replace(/(?<!\\)%.*$/, ''))
    .join('\n');
  const skills = [];
  const re = /\\begin\{sidebarBlock\}\{([^}]*)\}([\s\S]*?)\\end\{sidebarBlock\}/g;
  let m;
  while ((m = re.exec(clean))) {
    if (/LANG|SPRACH|INTEREST|HOBB|LOISIR/i.test(m[1])) continue;
    const item = /\\(sline|pair)(?![A-Za-z])/g;
    let it;
    while ((it = item.exec(m[2]))) {
      let i = it.index + it[0].length;
      for (let k = 0; k < (it[1] === 'pair' ? 2 : 1); k++) {
        const [g, n] = readGroup(m[2], i);
        skills.push(stripLatex(g));
        i = n;
      }
      item.lastIndex = i;
    }
  }
  return { work: readBlocks(clean, 'experience'), education: readBlocks(clean, 'education'), skills };
}

export function cvStartYear(dates) {
  const yy = Number(/'(\d\d)/.exec(dates)?.[1]);
  return yy <= 50 ? 2000 + yy : 1900 + yy;
}

const words = s => new Set(s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-z0-9]{3,}/g) ?? []);

export function findBankEntry(entries, name, startYear, nameKey) {
  const w = words(name);
  const hit = entries.find(e => Number(e.start.slice(0, 4)) === startYear && [...words(e[nameKey])].some(x => w.has(x)));
  if (!hit) throw new Error(`No bank entry for "${name}" starting ${startYear}`);
  return hit;
}

export function isCurrent({ end_status, end }, today) {
  if (!['current_indefinite', 'contract_ending'].includes(end_status)) return false;
  if (!end) return true;
  const [y, mo, d] = end.split('-').map(Number);
  const last = d ?? new Date(Date.UTC(y, mo, 0)).getUTCDate(); // YYYY-MM = end of that month
  return `${y}-${String(mo).padStart(2, '0')}-${String(last).padStart(2, '0')}` >= today;
}

export function degreeCode(text) {
  if (/\bMBA\b|Business Administration/i.test(text)) return 'MBA';
  if (/Ph\.?D|Doctor/i.test(text)) return 'PhD';
  if (/^Master|\bM\.?Sc\b/i.test(text)) return 'MS';
  if (/Bachelor|\bB\.?Sc\b/i.test(text)) return 'BS';
  return null;
}

const ym = s => s.split('-').map(Number);

export function buildApplyData({ tex, bank, classification, pdfNames, today, now }) {
  const cv = parseCv(tex);
  const { candidate: c } = bank;
  const contact = c.contact ?? {};
  const work = cv.work.map(b => {
    const e = findBankEntry(bank.experiences ?? bank.experience, b.org, cvStartYear(b.dates), 'company');
    const current = isCurrent(e, today);
    const [sy, sm] = ym(e.start);
    const [ey, em] = current ? [null, null] : ym(e.end);
    return { title: b.title, company: b.org, location: b.location, startMonth: sm, startYear: sy,
      endMonth: em, endYear: ey, current, description: b.bullets.join('\n') };
  });
  const education = cv.education.map(b => {
    const e = findBankEntry(bank.education, b.org, cvStartYear(b.dates), 'institution');
    return { school: b.org, degreeCode: degreeCode(e.degree), degreeText: e.degree, fieldOfStudy: e.field_of_study ?? '',
      startYear: ym(e.start)[0], endYear: ym(e.end)[0] };
  });
  const [firstName, ...rest] = c.name.split(/\s+/);
  const pdf = f => (pdfNames.includes(f) ? f : null);
  return {
    schema: 1, generated: now,
    job: { company: classification.company, role: classification.role_title, url: classification.source_url },
    candidate: {
      firstName, lastName: rest.join(' '), email: contact.email,
      phone: (contact.phone ?? '').replace(/^\+41/, '').replace(/\D/g, ''),
      phoneType: 'Mobile', countryPhoneCode: 'Switzerland (+41)',
      addressLine1: (contact.address ?? '').split(',')[0].trim(), postalCode: contact.zip,
      city: contact.city, country: contact.country, linkedin: contact.linkedin ?? null, previouslyWorked: false,
    },
    work, education, skills: cv.skills.slice(0, 10),
    files: { cv: pdf(`${c.file_slug}_CV.pdf`), coverLetter: pdf(`${c.file_slug}_cover-letter.pdf`) },
  };
}

if (isMainModule(import.meta.url)) {
  try {
    const folder = process.argv[2];
    if (!folder) throw new Error('Usage: node apply-data.mjs <output-folder> [profile_bank.json]');
    const bankPath = process.argv[3] ?? `${process.env.HOME}/Claude-code/job-hunter-data/config/profile_bank.json`;
    const bank = JSON.parse(readFileSync(resolve(bankPath), 'utf8'));
    const dir = resolve(folder);
    const data = buildApplyData({
      tex: readFileSync(join(dir, `${bank.candidate.file_slug}_CV.tex`), 'utf8'),
      bank,
      classification: JSON.parse(readFileSync(join(dir, 'classification.json'), 'utf8')),
      pdfNames: readdirSync(dir),
      today: new Date().toISOString().slice(0, 10),
      now: new Date().toISOString(),
    });
    const out = join(dir, 'apply.json');
    writeFileSync(out, JSON.stringify(data, null, 2) + '\n');
    console.log(`apply.json: ${data.work.length} work, ${data.education.length} education, ${data.skills.length} skills, cv ${data.files.cv ? 'yes' : 'no'}, cover letter ${data.files.coverLetter ? 'yes' : 'no'} -> ${out}`);
  } catch (err) {
    process.stderr.write(`${err.message}\n`);
    process.exit(1);
  }
}
