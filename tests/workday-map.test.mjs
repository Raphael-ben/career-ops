import { test } from 'node:test';
import assert from 'node:assert/strict';

await import('../extension/ats/workday.js');
const W = globalThis.CareerOpsWorkday;

test('stepOf', () => {
  assert.equal(W.stepOf(['x', 'applyFlowMyExpPage']), 'myExp');
  assert.equal(W.stepOf(['applyFlowMyInfoPage']), 'myInfo');
  assert.equal(W.stepOf(['applyFlowVoluntaryDisclosuresPage']), null);
});

test('blockNumbers keeps DOM order and dedups', () => {
  const ids = ['workExperience-42--jobTitle', 'workExperience-42--location', 'workExperience-9--jobTitle', 'education-3--schoolName'];
  assert.deepEqual(W.blockNumbers(ids, 'workExperience'), [42, 9]);
});

test('fieldId and dateIds', () => {
  assert.equal(W.fieldId('education', 3, 'degree'), 'education-3--degree');
  assert.deepEqual(W.dateIds('workExperience', 9, 'startDate'), {
    month: 'workExperience-9--startDate-dateSectionMonth-input',
    year: 'workExperience-9--startDate-dateSectionYear-input',
  });
});

test('keys', () => {
  assert.equal(W.workKey(' Acme  SA ', 2017), 'acme sa|2017');
  assert.equal(W.eduKey('', undefined), '');
});

test('matchBlocks keys on company and start year', () => {
  const r = W.matchBlocks([{ n: 9, key: W.workKey('Acme SA', 2017) }], [W.workKey('Acme SA ', 2015), W.workKey('acme sa', 2017)]);
  assert.deepEqual(r, { pairs: [{ n: 9, wanted: 1 }], toAdd: [0], extra: [] });
});

test('matchBlocks reuses an empty block before asking for Add', () => {
  const r = W.matchBlocks([{ n: 120, key: '' }], [W.workKey('A', 2020), W.workKey('B', 2018)]);
  assert.deepEqual(r, { pairs: [{ n: 120, wanted: 0 }], toAdd: [1], extra: [] });
});

test('matchBlocks lists foreign blocks as extra', () => {
  assert.deepEqual(W.matchBlocks([{ n: 5, key: W.workKey('Other', 2010) }], []).extra, [5]);
});

test('matchBlocks is stable on a filled page', () => {
  const keys = [W.workKey('A', 2020), W.workKey('B', 2018)];
  const r = W.matchBlocks([{ n: 7, key: keys[1] }, { n: 3, key: keys[0] }], keys);
  assert.deepEqual(r.toAdd, []);
  assert.deepEqual(r.extra, []);
  assert.deepEqual(r.pairs.map(p => p.wanted).sort(), [0, 1]);
});

test('pickOption', () => {
  assert.equal(W.pickOption(['BS', 'MS', 'MBA'], 'mba'), 'MBA');
  assert.equal(W.pickOption(['Business Administration and Management'], 'Business Administration'), null);
  assert.equal(W.pickOption([], 'x'), null);
});

test('shorterQuery', () => {
  assert.equal(W.shorterQuery('Business Administration'), 'Business');
  assert.equal(W.shorterQuery('Python'), 'Pyth');
});

test('companyMatchesHost', () => {
  assert.equal(W.companyMatchesHost('Salesforce', 'salesforce.wd12.myworkdayjobs.com'), true);
  assert.equal(W.companyMatchesHost('Hitachi Energy', 'hitachienergy.wd3.myworkdayjobs.com'), true);
  assert.equal(W.companyMatchesHost('Salesforce', 'hitachienergy.wd3.myworkdayjobs.com'), false);
});

test('formatForClaude', () => {
  const out = W.formatForClaude([
    { field: 'degree', label: 'Degree', wanted: 'MBA', source: 'education[0].degree', options: ['BS', 'MS', 'MBA'] },
    { field: 'skills', label: 'Skills', wanted: 'Python', source: 'skills[0]', options: [] },
  ]);
  assert.equal(out, [
    'Workday unmatched options — pick one option per field, verbatim, or "none":',
    '',
    'Field: Degree (degree)',
    'Wanted: MBA',
    'Source: education[0].degree',
    'Options:',
    '- BS',
    '- MS',
    '- MBA',
    '',
    'Field: Skills (skills)',
    'Wanted: Python',
    'Source: skills[0]',
    'Options: (none found on the page)',
  ].join('\n'));
});
