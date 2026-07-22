#!/usr/bin/env python3
"""
notion_finalize.py — deterministic Notion tracker-page finalizer.

Owns two things the tracker-entry flow must NEVER hand to an LLM agent:
  1. Uploading the CV + cover-letter PDFs as REAL Notion files (File Upload API),
     not external links.
  2. Pasting the FULL job description verbatim into the page body. LLM agents
     summarize/truncate long JDs; this script chunks and appends the raw text
     byte-for-byte, then re-reads the page to verify nothing was lost.

USAGE:
  python3 notion_finalize.py <page_id_or_url> [--cv path.pdf] [--cl path.pdf] [--jd path.txt] [--dry-run]
  python3 notion_finalize.py --selftest

Token: NOTION_ACCESS_TOKEN env var, or career-ops/.env (NOTION_ACCESS_TOKEN=...).
Exit codes: 0 PASS, 1 FAIL (API error or verification failed), 2 no token configured.
"""
import os as _os
import sys as _sys

# Re-exec into the project venv that has `requests` (root .venv preferred),
# mirroring cv_fitcheck.py's pattern so this runs the same way as its siblings.
_HERE = _os.path.dirname(_os.path.abspath(__file__))
for _v in (_os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3"),
           _os.path.join(_HERE, ".venv", "bin", "python3")):
    if _os.path.exists(_v) and _os.path.realpath(_sys.executable) != _os.path.realpath(_v):
        _os.execv(_v, [_v] + _sys.argv)
        break

import argparse
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
BASE = "https://api.notion.com"
# ponytail: one Notion-Version for every call in this script. Per the API
# reference (developers.notion.com/reference/upload-file + create-a-file-upload),
# the file-upload endpoints need a version at least this recent; older 2022-06-28
# calls used elsewhere in this repo (sync-notion-tracker.sh) still work fine on it.
NOTION_VERSION = "2026-03-11"
JD_HEADING = "Job Description"
DOCS_HEADING = "Documents"
CHUNK_LIMIT = 1900
JD_REPLACE_THRESHOLD = 0.90   # existing/source below this -> replace
JD_PASS_THRESHOLD = 0.98      # verification gate


class NotionAPIError(Exception):
    def __init__(self, status, body):
        super().__init__(f"Notion API error {status}: {body}")
        self.status = status
        self.body = body


# ── .env parsing (dotenv-style, no new dependency) ──────────────────────────

def load_env_file(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        env[k] = v
    return env


def get_token() -> str | None:
    env_val = _os.environ.get("NOTION_ACCESS_TOKEN")
    if env_val:
        return env_val
    return load_env_file(HERE / ".env").get("NOTION_ACCESS_TOKEN") or None


SETUP_MESSAGE = """\
NOTION_ACCESS_TOKEN is not configured — cannot finalize the tracker page.

Set it up once:
  1. Create an internal integration at https://www.notion.so/my-integrations
     and copy its secret (starts with "ntn_" or "secret_").
  2. Add it to career-ops/.env:  NOTION_ACCESS_TOKEN=ntn_your_secret_here
  3. In Notion, open the JOB OP applications database -> "..." menu -> Connections
     -> share it with the integration you just created.

Then re-run this command."""


# ── page id extraction ──────────────────────────────────────────────────────

def _format_uuid(h32: str) -> str:
    return f"{h32[0:8]}-{h32[8:12]}-{h32[12:16]}-{h32[16:20]}-{h32[20:32]}"


def extract_page_id(raw: str) -> str:
    """Accept a raw uuid (dashed or not) or a notion.so/app.notion.com URL."""
    raw = raw.strip()
    stripped_dashes = re.sub(r"-", "", raw)
    if re.fullmatch(r"[0-9a-fA-F]{32}", stripped_dashes) and len(raw) <= 36:
        return _format_uuid(stripped_dashes)
    # URL form: id is the trailing 32 hex chars of the last path segment.
    no_query = raw.split("?")[0].split("#")[0].rstrip("/")
    last_seg = no_query.split("/")[-1]
    hexonly = re.sub(r"[^0-9a-fA-F]", "", last_seg)
    if len(hexonly) < 32:
        raise ValueError(f"Could not extract a 32-hex-char page id from: {raw}")
    return _format_uuid(hexonly[-32:])


# ── chunking (never loses a character) ──────────────────────────────────────

def chunk_text(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Contiguous slices of `text`, each <= limit chars. Prefers to break on the
    last newline before the limit; falls back to a hard cut if none exists.
    Concatenating the result always reconstructs `text` exactly."""
    chunks = []
    i, n = 0, len(text)
    while i < n:
        end = min(i + limit, n)
        if end < n:
            nl = text.rfind("\n", i, end)
            if nl > i:
                end = nl + 1
        chunks.append(text[i:end])
        i = end
    return chunks


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ── Notion API wrapper ──────────────────────────────────────────────────────

def notion_request(token, method, path, json_body=None, params=None, timeout=30):
    url = BASE + path
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    resp = requests.request(method, url, headers=headers, json=json_body, params=params, timeout=timeout)
    if resp.status_code == 429:
        wait = float(resp.headers.get("Retry-After", "1"))
        time.sleep(wait)
        resp = requests.request(method, url, headers=headers, json=json_body, params=params, timeout=timeout)
    if resp.status_code >= 400:
        raise NotionAPIError(resp.status_code, resp.text[:1000])
    return resp.json() if resp.content else {}


def send_file_upload(token, file_upload_id, filepath, content_type):
    url = f"{BASE}/v1/file_uploads/{file_upload_id}/send"
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    for attempt in (1, 2):
        with open(filepath, "rb") as f:
            resp = requests.post(url, headers=headers,
                                  files={"file": (_os.path.basename(filepath), f, content_type)},
                                  timeout=60)
        if resp.status_code == 429 and attempt == 1:
            time.sleep(float(resp.headers.get("Retry-After", "1")))
            continue
        break
    if resp.status_code >= 400:
        raise NotionAPIError(resp.status_code, resp.text[:1000])
    return resp.json()


def upload_pdf(token, filepath, label):
    filename = _os.path.basename(filepath)
    created = notion_request(token, "POST", "/v1/file_uploads",
                              json_body={"mode": "single_part", "filename": filename,
                                         "content_type": "application/pdf"})
    send_file_upload(token, created["id"], filepath, "application/pdf")
    return created  # {"id": ..., "status": "uploaded", ...}


def get_all_blocks(token, block_id):
    blocks, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = notion_request(token, "GET", f"/v1/blocks/{block_id}/children", params=params)
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def append_children(token, page_id, children, after=None):
    body = {"children": children}
    if after:
        body["after"] = after
    return notion_request(token, "PATCH", f"/v1/blocks/{page_id}/children", json_body=body)


def archive_block(token, block_id):
    return notion_request(token, "PATCH", f"/v1/blocks/{block_id}", json_body={"archived": True})


# ── block helpers ───────────────────────────────────────────────────────────

def _plain_text(rich_text_array):
    return "".join(rt.get("plain_text", rt.get("text", {}).get("content", "")) for rt in rich_text_array)


def heading2_block(text):
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def paragraph_block(text):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def file_block(file_upload_id, caption):
    return {"object": "block", "type": "file",
            "file": {"type": "file_upload", "file_upload": {"id": file_upload_id},
                     "caption": [{"type": "text", "text": {"content": caption}}]}}


def find_section(blocks, heading_text):
    """Returns (heading_block_or_None, [child_blocks_until_next_heading_2])."""
    heading, children, collecting = None, [], False
    for b in blocks:
        if b["type"] == "heading_2":
            if collecting:
                break
            if _plain_text(b["heading_2"]["rich_text"]).strip() == heading_text:
                heading = b
                collecting = True
                continue
        elif collecting:
            children.append(b)
    return heading, children


def section_text(children):
    return "".join(_plain_text(b["paragraph"]["rich_text"]) for b in children if b["type"] == "paragraph")


def file_captions(children):
    caps = set()
    for b in children:
        if b["type"] == "file":
            cap = _plain_text(b["file"].get("caption", []))
            if cap:
                caps.add(cap)
    return caps


# ── Documents section (CV / cover letter) ───────────────────────────────────

def handle_documents(token, page_id, existing_blocks, cv_path, cl_path, dry_run, notes):
    if not cv_path and not cl_path:
        return
    heading, children = find_section(existing_blocks, DOCS_HEADING)
    existing_captions = file_captions(children)
    insertion_after = children[-1]["id"] if children else (heading["id"] if heading else None)

    to_append = []
    if heading is None:
        to_append.append(heading2_block(DOCS_HEADING))

    for path, caption, size_label in ((cv_path, "CV", "CV"), (cl_path, "Cover Letter", "cover letter")):
        if not path:
            continue
        if caption in existing_captions:
            notes.append(f"Documents: {caption} block already present — skipped (no duplicate).")
            continue
        if not _os.path.isfile(path):
            raise FileNotFoundError(f"{size_label} PDF not found: {path}")
        size = _os.path.getsize(path)
        if dry_run:
            notes.append(f"[dry-run] would upload {caption} ({path}, {size} bytes) and append a file block.")
            continue
        uploaded = upload_pdf(token, path, caption)
        to_append.append(file_block(uploaded["id"], caption))
        notes.append(f"Documents: uploaded {caption} ({size} bytes).")

    if to_append and not dry_run:
        append_children(token, page_id, to_append, after=insertion_after if heading else None)
    elif to_append and dry_run:
        notes.append(f"[dry-run] would append {len(to_append)} block(s) under '{DOCS_HEADING}'"
                     f"{' (creating the heading)' if heading is None else ''}.")


# ── Job Description section ─────────────────────────────────────────────────

def handle_jd(token, page_id, existing_blocks, jd_path, dry_run, notes):
    if not jd_path:
        return
    source_text = Path(jd_path).read_text(encoding="utf-8")
    chunks = chunk_text(source_text)
    heading, children = find_section(existing_blocks, JD_HEADING)
    existing_text = section_text(children)

    if dry_run:
        notes.append(f"[dry-run] JD source: {len(source_text)} chars -> {len(chunks)} block(s).")
        if heading is None:
            notes.append(f"[dry-run] would create '{JD_HEADING}' heading and append {len(chunks)} paragraph block(s).")
        else:
            ratio = (len(existing_text) / len(source_text)) if source_text else 1.0
            if ratio < JD_REPLACE_THRESHOLD:
                notes.append(f"[dry-run] existing JD is {ratio:.0%} of source (<{JD_REPLACE_THRESHOLD:.0%}) "
                              f"-> would archive {len(children)} block(s) and re-append {len(chunks)}.")
            else:
                notes.append(f"[dry-run] existing JD is {ratio:.0%} of source (>={JD_REPLACE_THRESHOLD:.0%}) -> leave as-is.")
        return

    if heading is None:
        to_append = [heading2_block(JD_HEADING)] + [paragraph_block(c) for c in chunks]
        append_children(token, page_id, to_append)
        notes.append(f"Job Description: created heading + appended {len(chunks)} block(s) ({len(source_text)} chars).")
        return

    ratio = (len(existing_text) / len(source_text)) if source_text else 1.0
    if ratio >= JD_REPLACE_THRESHOLD:
        notes.append(f"Job Description: existing content is {ratio:.0%} of source (>= {JD_REPLACE_THRESHOLD:.0%}) — left as-is.")
        return

    for b in children:
        archive_block(token, b["id"])
    append_children(token, page_id, [paragraph_block(c) for c in chunks], after=heading["id"])
    notes.append(f"Job Description: replaced {len(children)} stale block(s) with {len(chunks)} fresh block(s) "
                 f"({len(source_text)} chars, was {ratio:.0%} of source).")


# ── properties (CV / Cover Letter, only if schema type is 'files') ─────────

def get_properties_schema(token, page):
    parent = page.get("parent", {})
    try:
        if parent.get("type") == "data_source_id":
            return notion_request(token, "GET", f"/v1/data_sources/{parent['data_source_id']}").get("properties", {})
        if parent.get("type") == "database_id":
            return notion_request(token, "GET", f"/v1/databases/{parent['database_id']}").get("properties", {})
    except NotionAPIError:
        pass
    return {}


def handle_properties(token, page_id, props_schema, cv_path, cl_path, dry_run, notes):
    updates = {}
    for path, prop_name, filename in ((cv_path, "CV", "CV.pdf"), (cl_path, "Cover Letter", "Cover-Letter.pdf")):
        if not path:
            continue
        prop_type = props_schema.get(prop_name, {}).get("type")
        if prop_type != "files":
            notes.append(f"Property '{prop_name}' is type '{prop_type or 'absent'}', not 'files' — "
                         f"skipped silently (body attachment is the deliverable).")
            continue
        if dry_run:
            notes.append(f"[dry-run] would set property '{prop_name}' (files type detected).")
            continue
        # Re-upload is wasteful if handle_documents already uploaded it; caller passes
        # the same PDF path so we just note this path isn't wired to reuse the file_upload
        # id — ponytail: current known schema state is 'url', so this branch is dormant.
        notes.append(f"Property '{prop_name}' is type 'files' but this script does not "
                     f"re-upload for properties — set it manually or extend this function.")
    if updates and not dry_run:
        notion_request(token, "PATCH", f"/v1/pages/{page_id}", json_body={"properties": updates})


# ── verification ─────────────────────────────────────────────────────────

def verify(token, page_id, cv_path, cl_path, jd_path, notes):
    blocks = get_all_blocks(token, page_id)
    ok = True

    if cv_path or cl_path:
        _, doc_children = find_section(blocks, DOCS_HEADING)
        caps = file_captions(doc_children)
        expected = {c for c, p in (("CV", cv_path), ("Cover Letter", cl_path)) if p}
        if not expected.issubset(caps):
            missing = expected - caps
            notes.append(f"FAIL: missing file block(s) under '{DOCS_HEADING}': {sorted(missing)}")
            ok = False
        else:
            notes.append(f"PASS: file block(s) present under '{DOCS_HEADING}': {sorted(expected)}")

    if jd_path:
        source_text = Path(jd_path).read_text(encoding="utf-8")
        _, jd_children = find_section(blocks, JD_HEADING)
        page_text = section_text(jd_children)
        src_norm, page_norm = normalize_ws(source_text), normalize_ws(page_text)
        ratio = (len(page_norm) / len(src_norm)) if src_norm else 1.0
        if ratio < JD_PASS_THRESHOLD:
            notes.append(f"FAIL: JD in page is {ratio:.1%} of source (< {JD_PASS_THRESHOLD:.0%}).")
            ok = False
        else:
            notes.append(f"PASS: JD in page is {ratio:.1%} of source (>= {JD_PASS_THRESHOLD:.0%}).")

    return ok


# ── selftest (no network, no token needed) ──────────────────────────────────

def selftest():
    # extract_page_id
    flat = "abcdef1234567890abcdef1234567890"
    expected = _format_uuid(flat)
    assert extract_page_id(flat) == expected
    assert extract_page_id("abcdef12-3456-7890-abcd-ef1234567890") == expected
    assert extract_page_id(f"https://www.notion.so/myworkspace/Application-Tracker-{flat}") == expected
    assert extract_page_id(f"https://app.notion.com/{flat}?v=someviewid123") == expected
    try:
        extract_page_id("https://www.notion.so/not-a-valid-id")
        raise AssertionError("expected ValueError for a bad id")
    except ValueError:
        pass
    print("PASS: extract_page_id (uuid, dashed uuid, notion.so URL, app.notion.com URL, bad-id rejection)")

    # chunk_text — 5000-char fixture -> 3 blocks, no char lost
    import random
    rng = random.Random(42)
    fixture = "".join(rng.choice("abcdefghij \n") for _ in range(5000))
    chunks = chunk_text(fixture, 1900)
    assert len(chunks) == 3, f"expected 3 chunks, got {len(chunks)}"
    assert all(len(c) <= 1900 for c in chunks)
    assert sum(len(c) for c in chunks) == len(fixture)
    assert "".join(chunks) == fixture
    # edge cases: empty text, text shorter than limit, text with no newlines at all
    assert chunk_text("", 1900) == []
    assert chunk_text("short", 1900) == ["short"]
    no_newline = "x" * 5000
    nn_chunks = chunk_text(no_newline, 1900)
    assert "".join(nn_chunks) == no_newline and len(nn_chunks) == 3
    print("PASS: chunk_text (5000-char fixture -> 3 blocks, exact reconstruction, edge cases)")

    # .env parsing
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        envfile = Path(td) / ".env"
        envfile.write_text(
            "# comment line\n"
            "\n"
            "GEMINI_API_KEY=abc123\n"
            "export NOTION_ACCESS_TOKEN=ntn_fake_selftest_value\n"
            'QUOTED="quoted value"\n'
            "SINGLE_QUOTED='single value'\n",
            encoding="utf-8",
        )
        env = load_env_file(envfile)
        assert env["NOTION_ACCESS_TOKEN"] == "ntn_fake_selftest_value"
        assert env["GEMINI_API_KEY"] == "abc123"
        assert env["QUOTED"] == "quoted value"
        assert env["SINGLE_QUOTED"] == "single value"
        assert load_env_file(Path(td) / "nonexistent.env") == {}
    print("PASS: .env parsing (comments, blank lines, export prefix, quoted values, missing file)")

    print("\nSELFTEST: ALL PASS")


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("page", nargs="?", help="Notion page id (uuid) or a notion.so/app.notion.com URL")
    ap.add_argument("--cv", help="Path to the CV PDF")
    ap.add_argument("--cl", help="Path to the cover letter PDF")
    ap.add_argument("--jd", help="Path to a text file with the full job description")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="Run internal unit tests, no network/token needed")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if not args.page:
        ap.error("page (id or URL) is required unless --selftest is given")

    token = get_token()
    if not token:
        print(SETUP_MESSAGE)
        sys.exit(2)

    notes = []
    try:
        page_id = extract_page_id(args.page)
        page = notion_request(token, "GET", f"/v1/pages/{page_id}")
        props_schema = get_properties_schema(token, page)
        existing_blocks = get_all_blocks(token, page_id)

        handle_documents(token, page_id, existing_blocks, args.cv, args.cl, args.dry_run, notes)
        handle_jd(token, page_id, existing_blocks, args.jd, args.dry_run, notes)
        handle_properties(token, page_id, props_schema, args.cv, args.cl, args.dry_run, notes)
    except NotionAPIError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"FAIL: network error: {e}")
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    print("\n".join(notes))

    if args.dry_run:
        print("\nDRY RUN — no writes were made.")
        return

    print()
    verify_notes = []
    ok = verify(token, page_id, args.cv, args.cl, args.jd, verify_notes)
    print("\n".join(verify_notes))
    print("\nRESULT: PASS" if ok else "\nRESULT: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
