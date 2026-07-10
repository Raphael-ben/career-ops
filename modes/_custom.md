# _custom.md — Raphael's procedural house rules (user layer, survives updates)

## No Playwright outside the apply flow

Playwright (or any browser automation) is used in EXACTLY ONE place: the
interactive `/jobhunter apply` flow driving Raphael's Brave + Dashlane browser.
Everywhere else — scan, pipeline, liveness, JD fetching, Notion entries — is
browserless. This overrides the system-layer "Offer Verification — MANDATORY
Playwright" rule in CLAUDE.md/AGENTS.md.

**Liveness checks (pipeline / pre-apply):**
- Use `node check-liveness.mjs {url}` — its ATS JSON API rung — or a plain
  curl HTTP status check. NEVER browser-verify.
- Anti-bot 403/challenge pages are NOT "dead" — treat non-404 as
  alive-inconclusive and defer the real confirmation to apply time, when the
  posting opens in Brave anyway.

**JD fetching (pipeline/notion-entry):**
- Primary: JD text already in session context.
- Fallback: Scrapling `Fetcher` with chrome impersonation (curl_cffi) via the
  local venv, or the `scrapling` MCP `get`/`fetch` tools. No PlaywrightFetcher,
  no StealthyFetcher (both launch browsers).
- If blocked: note "(JD fetch failed — paste manually from {url})" and move on.
