/**
 * liveness-api.mjs — zero-token ATS API rung for job-posting liveness.
 *
 * The cheap first rung of check-liveness.mjs (and scan --verify): map a posting
 * URL to the vendor's public JSON API and read liveness straight from it — no
 * browser, no LLM tokens. A definitive 404/410 (or Ashby "unlisted") is
 * authoritative; anything ambiguous (network error, non-200, malformed body,
 * non-ATS host) returns null so the caller falls back to the Playwright rung.
 *
 * A false "expired" is worse than a slow check (it makes the user miss a real
 * job), so every uncertain path degrades to null rather than guessing expired.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LOCALE_RE = /^[a-z]{2}-[A-Z]{2}$/;      // Workday URL locale segment, e.g. en-US
const FETCH_TIMEOUT_MS = 8_000;
// Some ATS APIs (Ashby, SmartRecruiters) reject an empty/robotic UA.
const API_HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  Accept: 'application/json',
};

/**
 * Per-job liveness from an Ashby org job-board payload.
 * Ashby's posting API returns the whole org board, so we confirm the specific
 * job id ourselves. Live iff the job is present AND listed; otherwise expired.
 * Returns null for a malformed payload (no `jobs` array) → Playwright fallback.
 */
export function classifyAshbyBoard(board, jobId) {
  const jobs = board?.jobs;
  if (!Array.isArray(jobs)) return null;
  const job = jobs.find((j) => j?.id === jobId);
  if (job && job.isListed) {
    return { result: 'active', code: 'ashby_api_ok', reason: `Ashby board lists job ${jobId}` };
  }
  // Absent or present-but-unlisted both mean the posting is no longer public.
  return { result: 'expired', code: 'ashby_api_unlisted', reason: `Ashby board no longer lists job ${jobId}` };
}

/**
 * Map a posting URL to its public ATS JSON API endpoint.
 * Returns null for non-ATS hosts, non-https URLs, board roots (no specific job),
 * or any shape we can't confidently resolve.
 *
 * Shape: { ats, apiUrl, parts, [interpret] }. Per-job endpoints (Greenhouse,
 * Lever, SmartRecruiters, Workday) are authoritative by HTTP status alone.
 * Ashby resolves to an org-level board, so it carries an `interpret` closure
 * that classifyAshbyBoard-filters the payload down to the one job id.
 */
export function resolveAtsApi(url) {
  let u;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  // https-only SSRF guard. The API targets are fixed public hosts, and a
  // private/internal input host simply won't match any vendor below → null.
  if (u.protocol !== 'https:') return null;
  const host = u.hostname.toLowerCase();
  const seg = u.pathname.split('/').filter(Boolean);

  // Greenhouse: boards.greenhouse.io/{org}/jobs/{numericId}
  if (host === 'boards.greenhouse.io' || host === 'job-boards.greenhouse.io') {
    const i = seg.indexOf('jobs');
    const org = seg[i - 1];
    const jobId = seg[i + 1];
    if (i >= 1 && org && jobId && /^\d+$/.test(jobId)) {
      return {
        ats: 'greenhouse',
        apiUrl: `https://boards-api.greenhouse.io/v1/boards/${org}/jobs/${jobId}`,
        parts: { org, jobId },
      };
    }
    return null;
  }

  // Lever: jobs[.eu].lever.co/{org}/{postingId} → api[.eu].lever.co/v0/postings/{org}/{id}
  if (host === 'jobs.lever.co' || host.endsWith('.lever.co')) {
    const org = seg[0];
    const jobId = seg[1];
    if (org && jobId) {
      const apiHost = host.replace(/^jobs\./, 'api.');
      return {
        ats: 'lever',
        apiUrl: `https://${apiHost}/v0/postings/${org}/${jobId}`,
        parts: { org, jobId },
      };
    }
    return null;
  }

  // Ashby: jobs.ashbyhq.com/{org}/{jobId}[/application] → org job-board API.
  if (host === 'jobs.ashbyhq.com') {
    const org = seg[0];
    const jobId = seg[1];
    if (org && jobId && UUID_RE.test(jobId)) {
      return {
        ats: 'ashby',
        apiUrl: `https://api.ashbyhq.com/posting-api/job-board/${org}`,
        parts: { org, jobId },
        interpret: (board) => classifyAshbyBoard(board, jobId),
      };
    }
    return null;
  }

  // SmartRecruiters: jobs.smartrecruiters.com/{Company}/{postingId}[-slug]
  //   → api.smartrecruiters.com/v1/companies/{Company}/postings/{postingId}
  if (host === 'jobs.smartrecruiters.com' || host === 'careers.smartrecruiters.com') {
    const company = seg[0];
    // Posting id is the leading digit run of the last segment (id-slug or bare id).
    const idMatch = seg[1] && seg[1].match(/^(\d{6,})/);
    if (company && idMatch) {
      return {
        ats: 'smartrecruiters',
        apiUrl: `https://api.smartrecruiters.com/v1/companies/${company}/postings/${idMatch[1]}`,
        parts: { org: company, jobId: idMatch[1] },
      };
    }
    return null;
  }

  // Workday: {tenant}.{instance}.myworkdayjobs.com/[locale/]{site}/job/{...path}
  //   → {origin}/wday/cxs/{tenant}/{site}/job/{...path}  (per-job GET, 200/404)
  // ponytail: covers the standard hosted-page URL shape; exotic locale/site
  // layouts fall through to null → Playwright, never a false expired.
  if (host.endsWith('.myworkdayjobs.com')) {
    const hp = host.split('.');
    const tenant = hp[0];
    const instance = hp[1];
    let rest = seg;
    if (rest[0] && LOCALE_RE.test(rest[0])) rest = rest.slice(1); // drop locale
    const site = rest[0];
    const j = rest.indexOf('job');
    if (tenant && instance && site && j >= 1) {
      const jobPath = rest.slice(j).join('/'); // "job/{Location}/{Title}_{ReqId}"
      return {
        ats: 'workday',
        apiUrl: `https://${host}/wday/cxs/${tenant}/${site}/${jobPath}`,
        parts: { org: tenant, site, jobId: rest.slice(j + 1).join('/') },
      };
    }
    return null;
  }

  return null;
}

/**
 * Zero-token liveness check via the ATS API rung.
 * @returns {Promise<{result,code,reason}|null>} active/expired verdict, or null
 *   (non-ATS host, network/timeout error, or inconclusive) → Playwright fallback.
 */
export async function checkLivenessViaApi(url) {
  const resolved = resolveAtsApi(url);
  if (!resolved) return null;

  let res;
  try {
    res = await fetch(resolved.apiUrl, {
      headers: API_HEADERS,
      redirect: 'follow',
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    });
  } catch {
    // Network error or aborted timeout — inconclusive, not expired.
    return null;
  }

  const status = res?.status ?? 0;
  if (status === 404 || status === 410) {
    return { result: 'expired', code: `${resolved.ats}_api_gone`, reason: `${resolved.ats} API HTTP ${status}` };
  }
  if (status !== 200) return null; // 403/429/5xx etc. — inconclusive → Playwright

  if (resolved.interpret) {
    // Org-level board (Ashby): parse and confirm the specific job id.
    let body;
    try {
      body = await res.json();
    } catch {
      return null;
    }
    return resolved.interpret(body); // may be null (malformed) → Playwright
  }

  // Per-job endpoint: a 200 is the live posting itself.
  return { result: 'active', code: `${resolved.ats}_api_ok`, reason: `${resolved.ats} API HTTP 200` };
}
