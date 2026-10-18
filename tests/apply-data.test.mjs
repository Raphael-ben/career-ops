import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripLatex, parseCv, isCurrent, degreeCode, buildApplyData } from '../apply-data.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

const TEX = String.raw`%%   \begin{experience}{date}{title}{org}{location}{url}
\begin{sidebarBlock}{FOREIGN LANGUAGES}
  \sline{German: Native}
\end{sidebarBlock}
\begin{sidebarBlock}{PERSONAL SKILLS}
  \sline{Stakeholder management}
  \pair{Process design}{Proactivity}
\end{sidebarBlock}
\begin{sidebarBlock}{COMPUTER SKILLS}
  \pair{Python}{SQL}
  \sline{Excel (advanced)}
\end{sidebarBlock}
\begin{sidebarBlock}{INTERESTS}
  \pair{Skiing}{Cycling}
\end{sidebarBlock}
\begin{experience}{Nov.~'22 -- May~'26}%
                  {Senior Associate -- Deals}%
                  {Muster Advisory}%
                  {Zürich, Switzerland}%
                  {https://example.com}
  \item Ran 10+ workstreams across \textbf{three} teams
  \item Cut cost by CHF 1--5M (20\%)
\end{experience}
\begin{experience}{Aug.~'17 -- June~'20}%
                  {Project Manager -- Tests}%
                  {Acme SA}%
                  {Biel/Bienne, Switzerland}%
                  {https://example.com}
  \item Built a tool \& rolled it out
\end{experience}
\begin{experience}{Mar.~'15 -- July~'17}%
                  {Engineer -- Methods}%
                  {Acme SA}%
                  {Biel/Bienne, Switzerland}%
                  {https://example.com}
  \item Saved 1000s of hours
\end{experience}
\begin{education}{Aug.~'20 -- Aug.~'21}%
                 {Master of Business Administration (MBA)}%
                 {HSG -- University of St.~Gallen}%
                 {St.~Gallen, Switzerland}%
                 {https://example.com}
  \item Ranked \#6
\end{education}
\begin{education}{Sept.~'11 -- Sept.~'15}%
                 {Master of Mechanical Engineering}%
                 {Example Institute}%
                 {Lyon, France}%
                 {https://example.com}
  \item \'Ecole group
\end{education}
`;

const BANK = {
  candidate: { name: 'Alex Muster', file_slug: 'Alex-Muster', contact: { email: 'alex@example.com', phone: '+41 79 000 00 00', linkedin: 'https://www.linkedin.com/in/alex-muster-example', address: 'Musterstrasse 1, 8000 Zürich, Switzerland', city: 'Zürich', zip: '8000', country: 'Switzerland' } },
  experience: [
    { company: 'Muster Advisory AG', start: '2022-11', end: '2026-05-31', end_status: 'contract_ending' },
    { company: 'Acme SA', start: '2017-08', end: '2020-06', end_status: 'completed' },
    { company: 'Acme SA', start: '2015-03', end: '2017-07', end_status: 'completed' },
  ],
  education: [
    { institution: 'University of St. Gallen (HSG)', degree: 'Master of Business Administration (MBA)', start: '2020-08', end: '2021-08', field_of_study: 'Business Administration' },
    { institution: 'Example Institute of Mechanics', degree: 'Master of Mechanical Engineering', start: '2011-09', end: '2015-09', field_of_study: 'Mechanical Engineering' },
  ],
};
const CLS = { company: 'Example Co', role_title: 'Analyst', source_url: 'https://example.wd1.myworkdayjobs.com/job/1' };
const build = (o = {}) => buildApplyData({ tex: TEX, bank: BANK, classification: CLS, pdfNames: ['Alex-Muster_CV.pdf', 'Alex-Muster_cover-letter.pdf'], today: '2026-10-18', now: '2026-10-18T10:00:00Z', ...o });

test('stripLatex cases', () => {
  for (const [i, o] of [
    ['A -- B', 'A - B'], ['St.~Gallen', 'St. Gallen'], ['R\\&D', 'R&D'], ['\\#6', '#6'],
    ['20\\%', '20%'], ["\\'Ecole", 'École'], ["\\'{e}t\\'e", 'été'],
    ['\\textbf{bold} x', 'bold x'], ['{grouped}', 'grouped'], ['  a   b ', 'a b'],
  ]) assert.equal(stripLatex(i), o);
});

test('parseCv ignores template comment lines and reads blocks in CV order', () => {
  const cv = parseCv(TEX);
  assert.equal(cv.work.length, 3);
  assert.equal(cv.education.length, 2);
  assert.deepEqual(cv.work.map(w => w.org), ['Muster Advisory', 'Acme SA', 'Acme SA']);
});

test('parseCv reads sidebar skills in order, skipping languages and interests', () => {
  assert.deepEqual(parseCv(TEX).skills, ['Stakeholder management', 'Process design', 'Proactivity', 'Python', 'SQL', 'Excel (advanced)']);
});

test('buildApplyData work block', () => {
  assert.deepEqual(build().work[0], { title: 'Senior Associate - Deals', company: 'Muster Advisory', location: 'Zürich, Switzerland', startMonth: 11, startYear: 2022, endMonth: 5, endYear: 2026, current: false, description: 'Ran 10+ workstreams across three teams\nCut cost by CHF 1-5M (20%)' });
});

test('two blocks of one company resolve by start year', () => {
  const { work } = build();
  assert.deepEqual([work[1].startMonth, work[1].startYear, work[1].endMonth, work[1].endYear], [8, 2017, 6, 2020]);
  assert.deepEqual([work[2].startMonth, work[2].startYear, work[2].endMonth, work[2].endYear], [3, 2015, 7, 2017]);
});

test('current role gets no end date', () => {
  const w = build({ today: '2026-04-01' }).work[0];
  assert.equal(w.current, true);
  assert.equal(w.endMonth, null);
  assert.equal(w.endYear, null);
});

test('isCurrent treats YYYY-MM end as end of month and null end as open', () => {
  assert.equal(isCurrent({ end_status: 'contract_ending', end: '2026-10' }, '2026-10-18'), true);
  assert.equal(isCurrent({ end_status: 'current_indefinite', end: null }, '2026-10-18'), true);
  assert.equal(isCurrent({ end_status: 'completed', end: '2027-01' }, '2026-10-18'), false);
  assert.equal(isCurrent({ end_status: 'completed', end: null }, '2026-10-18'), false);
  assert.equal(isCurrent({ end_status: 'weird', end: '2027-01' }, '2026-10-18'), false);
  assert.equal(isCurrent({ end_status: 'contract_ending', end: '2026-05-31' }, '2026-10-18'), false);
});

test('education from CV school and bank years', () => {
  const { education } = build();
  assert.deepEqual(education[0], { school: 'HSG - University of St. Gallen', degreeCode: 'MBA', degreeText: 'Master of Business Administration (MBA)', fieldOfStudy: 'Business Administration', startYear: 2020, endYear: 2021 });
  assert.equal(education[1].degreeCode, 'MS');
  assert.equal(education[1].school, 'Example Institute');
});

test('degreeCode table', () => {
  assert.equal(degreeCode('Bachelor of Science'), 'BS');
  assert.equal(degreeCode('BSc Computer Science'), 'BS');
  assert.equal(degreeCode('MSc Computer Science'), 'MS');
  assert.equal(degreeCode('PhD in Physics'), 'PhD');
  assert.equal(degreeCode('Intensive 2-year preparatory course'), null);
});

test('candidate from bank contact', () => {
  assert.deepEqual(build().candidate, { firstName: 'Alex', lastName: 'Muster', email: 'alex@example.com', phone: '790000000', phoneType: 'Mobile', countryPhoneCode: 'Switzerland (+41)', addressLine1: 'Musterstrasse 1', postalCode: '8000', city: 'Zürich', country: 'Switzerland', linkedin: 'https://www.linkedin.com/in/alex-muster-example', previouslyWorked: false });
});

test('skills capped at 10', () => {
  const items = Array.from({ length: 12 }, (_, i) => `  \\sline{Skill ${i}}`).join('\n');
  const tex = TEX.replace(/(COMPUTER SKILLS\}\n)[\s\S]*?(\\end\{sidebarBlock\})/, `$1${items}\n$2`);
  const { skills } = build({ tex });
  assert.equal(skills.length, 10);
  assert.equal(skills[0], 'Stakeholder management');
});

test('files and job', () => {
  const d = build({ pdfNames: ['Alex-Muster_CV.pdf'] });
  assert.deepEqual(d.files, { cv: 'Alex-Muster_CV.pdf', coverLetter: null });
  assert.deepEqual(d.job, { company: 'Example Co', role: 'Analyst', url: CLS.source_url });
  assert.equal(d.schema, 1);
});

test('unknown employer throws', () => {
  const tex = TEX.replace("Aug.~'17 -- June~'20", "Jan.~'19").replace(/\{Acme SA\}(?=%\n\s*\{Biel\/Bienne, Switzerland\}%\n\s*\{https:\/\/example.com\}\n  \\item Built)/, '{Ghost Corp}');
  assert.throws(() => build({ tex }), /No bank entry for "Ghost Corp" starting 2019/);
});

function setup(withTex) {
  const dir = mkdtempSync(join(tmpdir(), 'apply-data-'));
  if (withTex) writeFileSync(join(dir, 'Alex-Muster_CV.tex'), TEX);
  writeFileSync(join(dir, 'classification.json'), JSON.stringify(CLS));
  writeFileSync(join(dir, 'Alex-Muster_CV.pdf'), '');
  writeFileSync(join(dir, 'bank.json'), JSON.stringify(BANK));
  return dir;
}
const run = dir => spawnSync(process.execPath, ['apply-data.mjs', dir, join(dir, 'bank.json')], { cwd: ROOT, encoding: 'utf8' });

test('CLI writes apply.json', () => {
  const dir = setup(true);
  const r = run(dir);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(JSON.parse(readFileSync(join(dir, 'apply.json'), 'utf8')).work.length, 3);
});

test('CLI fails loudly without the CV', () => {
  const dir = setup(false);
  const r = run(dir);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Alex-Muster_CV\.tex/);
  assert.equal(existsSync(join(dir, 'apply.json')), false);
});
