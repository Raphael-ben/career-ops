#!/usr/bin/env python3
"""
scan_http.py — shared HTTP escalation helper for scan_* scrapers.

get(url) tries a plain `requests.get` with a desktop-Chrome UA first (cheap,
no TLS fingerprinting). If that's blocked (403/429), errors (connection/TLS),
or comes back suspiciously empty (<500 bytes on a 200 — usually a bot-check
stub page), it retries once with curl_cffi's Chrome impersonation, which
matches real Chrome's TLS/JA3 fingerprint and gets past most basic bot gates.

Both requests.Response and curl_cffi's Response expose .status_code/.text,
so callers can treat the return value uniformly. Never raises — returns
None if both tiers fail, so callers degrade to [] rather than crash.
"""
import sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def get(url, timeout=20, **kw):
    import requests
    headers = {"User-Agent": UA, **kw.pop("headers", {})}
    try:
        resp = requests.get(url, timeout=timeout, headers=headers, **kw)
        empty = resp.status_code == 200 and len(resp.content) < 500
        if resp.status_code not in (403, 429) and not empty:
            return resp
    except Exception:
        pass  # connection/TLS error → fall through to escalation tier

    # Tier 2: curl_cffi with Chrome TLS impersonation
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, impersonate="chrome", timeout=timeout, **kw)
        return resp
    except Exception as e:
        print(f"scan_http: both tiers failed for {url}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    # httpbin.org/status/403 always returns 403 to any client (it's not a
    # real bot-gate), so a healthy get() should escalate tier-1 -> tier-2
    # and tier-2 should be the one whose response we get back.
    test_url = "https://httpbin.org/status/403"
    try:
        import requests
        tier1 = requests.get(test_url, timeout=10, headers={"User-Agent": UA})
        print(f"tier-1 (plain requests) got status={tier1.status_code} (expected 403 -> escalate)")
    except Exception as e:
        print(f"tier-1 errored (tolerated, httpbin may be down): {e}")

    resp = get(test_url)
    if resp is None:
        print("self-check: both tiers failed — tolerated (httpbin likely down)")
    else:
        print(f"self-check: escalation path returned status={resp.status_code} "
              f"(via curl_cffi impersonate=chrome, since tier-1 403s are never accepted)")
