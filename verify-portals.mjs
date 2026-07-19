// verify-portals.mjs — fetch-error classifier for the portal scanner.
//
// Restored after the v1.17.0 auto-update shipped scan.mjs (which imports
// classifyFetchError from here) without shipping this file. Only the piece the
// scan path needs is reconstructed; its contract is pinned by test-all.mjs:
//   classifyFetchError({ status: 404 })       === 'slug_gone'
//   classifyFetchError({ name: 'AbortError' }) === 'network'
//   classifyFetchError({ status: 503 })       === 'server'
//
// ponytail: scan.mjs only consumes classifyFetchError (buckets errors into
// slug_gone / network / other). The full upstream portal verifier
// (verifyPortalsFile, deriveSlugCandidates, verifyCompanies) was not restored —
// no upstream source and the scan path never calls it. `node doctor.mjs`'s
// portal-liveness check will fail its dynamic import until upstream is restored.

/**
 * Classify a fetch/HTTP error into a coarse bucket the scanner acts on.
 * @param {{status?: number, name?: string, code?: string}} err
 * @returns {'slug_gone'|'network'|'server'|'client'|'unknown'}
 */
export function classifyFetchError(err = {}) {
  const status = typeof err.status === 'number' ? err.status : undefined;

  // A 404/410 means the ATS slug/board no longer resolves — the company's
  // careers_url likely changed. Surfaced to the user as "run verify-portals".
  if (status === 404 || status === 410) return 'slug_gone';

  // Aborted or transport-level failures (DNS, reset, timeout) → transient network.
  const netNames = new Set(['AbortError', 'FetchError', 'TypeError']);
  const netCodes = new Set([
    'ENOTFOUND', 'ECONNREFUSED', 'ECONNRESET', 'ETIMEDOUT',
    'EAI_AGAIN', 'ECONNABORTED', 'UND_ERR_CONNECT_TIMEOUT',
  ]);
  if ((err.name && netNames.has(err.name)) || (err.code && netCodes.has(err.code))) {
    return 'network';
  }

  if (status !== undefined) {
    if (status >= 500) return 'server';
    if (status >= 400) return 'client';
  }
  return 'unknown';
}
