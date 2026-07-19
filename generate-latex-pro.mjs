#!/usr/bin/env node
// Compiles the "pro" (generic, parameterized) LaTeX templates to PDF.
// Replaces career-ops' generate-latex.mjs (which validates Santiago's template structure).

import { readFileSync, writeFileSync, rmSync, readdirSync, existsSync, copyFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { resolve, basename, join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { mkdtempSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const PROJECT_ROOT = dirname(fileURLToPath(import.meta.url));
const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.pdf', '.eps', '.svg']);

const PLACEHOLDER_PATTERN = /%%FILL:|%%TODO:|%%PLACEHOLDER/;

export function normalizeLatex(text, { swissGerman = false } = {}) {
  let result = text;

  // Em dash (U+2014) → comma
  result = result
    .replace(/ — /g, ', ')
    .replace(/— /g, ', ')
    .replace(/ —/g, ',')
    .replace(/—/g, ',');

  // En dash (U+2013) → comma
  result = result
    .replace(/ – /g, ', ')
    .replace(/– /g, ', ')
    .replace(/ –/g, ',')
    .replace(/–/g, ',');

  // Smart quotes → ASCII (U+2018/2019 single, U+201C/201D double)
  result = result
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"');

  // Swiss German: ß → ss (only when explicitly requested)
  if (swissGerman) {
    result = result.replace(/ß/g, 'ss');
  }

  return result;
}

export function validateTex(texContent) {
  const errors = [];

  if (PLACEHOLDER_PATTERN.test(texContent)) {
    errors.push('unreplaced placeholder found (%%FILL: or %%TODO: present)');
  }
  if (!texContent.includes('\\begin{document}')) {
    errors.push('missing \\begin{document}');
  }
  if (!texContent.includes('\\end{document}')) {
    errors.push('missing \\end{document}');
  }

  return { valid: errors.length === 0, errors };
}

// Slug identifies whose templates/data these are — drives the tmp-dir prefix
// and (optionally) an extra search dir for image assets living outside the
// repo (e.g. a per-user data directory). Generic default: 'pro'.
// ponytail: env/flag instead of a config file — one value, no need for more.
function resolveSlug(argv) {
  const flagIdx = argv.indexOf('--slug');
  if (flagIdx !== -1 && argv[flagIdx + 1]) return argv[flagIdx + 1];
  return process.env.JOBHUNTER_SLUG || 'pro';
}

export async function compileTex(inputTexPath, outputPdfPath, { swissGerman = false, slug = 'pro' } = {}) {
  const texContent = readFileSync(inputTexPath, 'utf8');

  const validation = validateTex(texContent);
  if (!validation.valid) {
    return { success: false, errors: validation.errors, pdfPath: null };
  }

  const normalized = normalizeLatex(texContent, { swissGerman });

  const tmpDir = mkdtempSync(join(tmpdir(), `latex-${slug}-`));
  const tmpTexPath = join(tmpDir, basename(inputTexPath));
  writeFileSync(tmpTexPath, normalized, 'utf8');

  // Copy image assets so \includegraphics can resolve them.
  // Search order: same folder as the .tex file, project root, project
  // templates/, then an optional external dir (JOBHUNTER_TEMPLATES_DIR) for
  // setups that keep per-user templates/photos outside the repo.
  const sourceDir = dirname(resolve(inputTexPath));
  const searchDirs = [sourceDir, PROJECT_ROOT, join(PROJECT_ROOT, 'templates')];
  if (process.env.JOBHUNTER_TEMPLATES_DIR) searchDirs.push(process.env.JOBHUNTER_TEMPLATES_DIR);
  for (const searchDir of searchDirs) {
    if (!existsSync(searchDir)) continue;
    for (const f of readdirSync(searchDir)) {
      const ext = f.slice(f.lastIndexOf('.')).toLowerCase();
      if (IMAGE_EXTS.has(ext)) {
        const dest = join(tmpDir, f);
        if (!existsSync(dest)) copyFileSync(join(searchDir, f), dest);
      }
    }
  }

  // Warn if tex references a photo file that wasn't resolved into the tmp dir.
  const photoWarnings = [];
  const simpleDef = texContent.match(/\\newcommand\s*\{\\CVPhoto\}\s*\{([^}]+)\}/);
  const photoFile = simpleDef ? simpleDef[1].trim() : null;
  if (photoFile && !existsSync(join(tmpDir, photoFile))) {
    photoWarnings.push(`Photo file "${photoFile}" not found — CV will render without a photo. Place it at the project root or next to the .tex file.`);
  }

  try {
    const opts = { cwd: tmpDir, timeout: 120_000 };
    execSync(`pdflatex -no-shell-escape -interaction=nonstopmode "${tmpTexPath}"`, opts);
    execSync(`pdflatex -no-shell-escape -interaction=nonstopmode "${tmpTexPath}"`, opts);

    const tmpPdfPath = tmpTexPath.replace(/\.tex$/, '.pdf');
    execSync(`cp "${tmpPdfPath}" "${resolve(outputPdfPath)}"`);

    const pdfContent = readFileSync(resolve(outputPdfPath), 'latin1');
    const pageMatches = pdfContent.match(/\/Type\s*\/Page[^s]/g) || [];
    const pageCount = pageMatches.length || 1;

    return { success: true, errors: [], warnings: photoWarnings, pdfPath: resolve(outputPdfPath), pageCount };
  } catch (err) {
    return { success: false, errors: [err.message.split('\n')[0]], warnings: photoWarnings, pdfPath: null };
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }
}

// CLI: node generate-latex-pro.mjs input.tex output.pdf [--swiss-german] [--slug <name>]
const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
const currentFilePath = fileURLToPath(import.meta.url);

if (invokedPath === currentFilePath) {
  const args = process.argv.slice(2);
  const swissGerman = args.includes('--swiss-german');
  const slug = resolveSlug(args);
  const positional = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--slug');

  if (positional.length < 2) {
    console.error('Usage: node generate-latex-pro.mjs <input.tex> <output.pdf> [--swiss-german] [--slug <name>]');
    process.exit(1);
  }

  const [inputTexPath, outputPdfPath] = positional;
  const result = await compileTex(inputTexPath, outputPdfPath, { swissGerman, slug });

  if (result.success) {
    console.log(JSON.stringify({ status: 'ok', pdfPath: result.pdfPath, pageCount: result.pageCount, warnings: result.warnings ?? [] }, null, 2));
  } else {
    console.error(JSON.stringify({ status: 'error', errors: result.errors, warnings: result.warnings ?? [] }, null, 2));
    process.exit(1);
  }
}
