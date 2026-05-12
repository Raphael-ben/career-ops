import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

function summarizeNotes(notes = '') {
  const trimmed = String(notes).trim();

  if (!trimmed) {
    return '';
  }

  const sentenceMatch = trimmed.match(/^(.+?\.(?:\s|$))/);
  const firstSentence = sentenceMatch?.[1]?.trim();

  if (firstSentence && firstSentence.length <= 60) {
    return firstSentence;
  }

  return trimmed.slice(0, 60).trimEnd();
}

function formatDateRange(start, end, endStatus) {
  const finish = endStatus === 'contract_ending' ? 'Present' : end;
  return [start, finish].filter(Boolean).join(' - ');
}

function formatExperienceEntry(entry) {
  const titleLine = `### ${entry.role || ''} | ${entry.company || ''}`.trim();
  const meta = [formatDateRange(entry.start, entry.end, entry.end_status), entry.location]
    .filter(Boolean)
    .join(' | ');
  const achievements = (entry.achievements || [])
    .map((achievement) => `- ${achievement.text}`)
    .join('\n');

  return [titleLine, meta, achievements].filter(Boolean).join('\n');
}

function formatEducationEntry(entry) {
  const titleLine = `### ${entry.degree || ''} | ${entry.institution || ''}`.trim();
  const meta = [formatDateRange(entry.start, entry.end, entry.end_status), entry.location]
    .filter(Boolean)
    .join(' | ');
  const notes = summarizeNotes(entry.notes);

  return [titleLine, meta, notes].filter(Boolean).join('\n');
}

function formatSkillLine(label, values) {
  if (!Array.isArray(values) || values.length === 0) {
    return '';
  }

  return `- ${label}: ${values.join(', ')}`;
}

export function generateCvMd(profileBank) {
  const candidate = profileBank?.candidate ?? {};
  const contact = candidate.contact ?? {};
  const experience = profileBank?.experience ?? [];
  const education = profileBank?.education ?? [];
  const skills = profileBank?.skills_master ?? {};
  const languageValues = (candidate.languages ?? []).map((item) => {
    const level = item.level ? ` (${item.level})` : '';
    return `${item.language}${level}`;
  });

  const headerLines = [
    `# ${candidate.name || 'Candidate'}`,
    [candidate.base, contact.email, contact.phone, contact.linkedin].filter(Boolean).join(' | '),
    contact.address || ''
  ].filter(Boolean);

  const workSection = experience.map(formatExperienceEntry).join('\n\n');
  const educationSection = education.map(formatEducationEntry).join('\n\n');
  const skillLines = [
    formatSkillLine('Technical', skills.technical),
    formatSkillLine('Domain', skills.domain),
    formatSkillLine('Soft', skills.soft),
    formatSkillLine('Tools', skills.tools),
    formatSkillLine('Languages', languageValues)
  ].filter(Boolean);

  return [
    ...headerLines,
    '',
    '## Work Experience',
    workSection,
    '',
    '## Education',
    educationSection,
    '',
    '## Skills',
    ...skillLines,
    ''
  ].join('\n');
}

export function isStale(profileBankPath, cvMdPath) {
  if (!existsSync(cvMdPath)) {
    return true;
  }

  const profileStat = statSync(profileBankPath);
  const cvStat = statSync(cvMdPath);

  return profileStat.mtimeMs > cvStat.mtimeMs;
}

function resolveProfileBankPath() {
  const overridePath = process.env.DATA_REPO_PATH;

  if (!overridePath) {
    return join(homedir(), 'Claude-code', 'job-hunter-data', 'config', 'profile_bank.json');
  }

  return basename(overridePath) === 'profile_bank.json'
    ? overridePath
    : join(overridePath, 'config', 'profile_bank.json');
}

function runCli() {
  const profileBankPath = resolveProfileBankPath();
  const outputPath = join(dirname(fileURLToPath(import.meta.url)), 'cv.md');

  if (!isStale(profileBankPath, outputPath)) {
    console.log(`cv.md is already up to date at ${outputPath}`);
    return;
  }

  const profileBank = JSON.parse(readFileSync(profileBankPath, 'utf8'));
  const markdown = generateCvMd(profileBank);

  writeFileSync(outputPath, `${markdown.endsWith('\n') ? markdown : `${markdown}\n`}`, 'utf8');
  console.log(`Generated cv.md from ${profileBankPath}`);
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
const currentFilePath = fileURLToPath(import.meta.url);

if (invokedPath === currentFilePath) {
  runCli();
}
