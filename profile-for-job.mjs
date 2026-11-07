#!/usr/bin/env node
// profile-for-job.mjs — pre-filters profile_bank.json to job-relevant achievements.
//
// Reads classification.json (produced by pipeline Step 3) and profile_bank.json,
// emits a slimmer JSON to stdout that the write-cv and write-cl modes consume.
// Strips surface_in and keywords arrays from each achievement (routing metadata
// the writers don't need) and omits achievements whose surface_in has no overlap
// with the job's classifications.
//
// Usage:
//   node profile-for-job.mjs <classification.json> [profile_bank.json]
//   node profile-for-job.mjs <classification.json> > output/folder/profile-filtered.json

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const classPath = process.argv[2];
const bankPath = process.argv[3] ??
  `${process.env.HOME}/Claude-code/job-hunter-data/config/profile_bank.json`;

if (!classPath) {
  process.stderr.write(
    'Usage: node profile-for-job.mjs <classification.json> [profile_bank.json]\n'
  );
  process.exit(1);
}

const classification = JSON.parse(readFileSync(resolve(classPath), 'utf8'));
const bank = JSON.parse(readFileSync(resolve(bankPath), 'utf8'));

// Build match set: all classification tags + "general" (always included)
const tags = new Set([...(classification.classifications ?? []), 'general']);

function filterAchievements(achievements = []) {
  return achievements
    .filter(a => Array.isArray(a.surface_in) && a.surface_in.some(t => tags.has(t)))
    .map(({ surface_in: _s, keywords: _k, ...rest }) => rest);
}

// An experience entry may carry include_only_if (a list of classification tags).
// It is then included only when the job matches one of those tags. The pipeline's
// conditional_flags (keyed by experience id or company) override the tag test when
// present, so a classification that forgets the flag still resolves correctly.
function conditionalEligible(exp) {
  if (!Array.isArray(exp.include_only_if)) return true;
  const flags = classification.conditional_flags ?? {};
  return flags[exp.id] ?? flags[exp.company] ?? exp.include_only_if.some(t => tags.has(t));
}

const experiences = (bank.experiences ?? bank.experience ?? []).map(exp => {
  const filtered = {
    ...exp,
    achievements: filterAchievements(exp.achievements),
  };
  // Signal ineligibility so the writer can skip without re-running logic
  if (!conditionalEligible(exp)) {
    filtered._conditional_eligible = false;
  }
  return filtered;
});

const output = {
  _meta: {
    ...bank._meta,
    filtered_for: classification.classifications,
    excluded_conditional: experiences.filter(e => e._conditional_eligible === false).map(e => e.id),
  },
  candidate: bank.candidate,
  education: bank.education,
  experiences,
  skills_master: bank.skills_master,
  rules: bank.rules,
};

process.stdout.write(JSON.stringify(output, null, 2) + '\n');
