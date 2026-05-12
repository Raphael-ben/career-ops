# Mode: onboarding — First-Launch Setup Guide

Triggered automatically when required files are missing. Walks the user through
the complete setup in one session. All steps write to gitignored files only —
nothing personal is committed.

> **Rule:** Do not run evaluations, scans, or any other mode until ALL required
> files exist. Guide the user step-by-step through this checklist first.

---

## Setup Checklist

Run these checks silently at session start:

```bash
ls config/profile.yml        # personalized?
ls cv.md                     # CV present?
ls portals.yml               # research config present?
ls modes/_profile.md         # archetype customization present?
```

If ALL exist → skip onboarding, proceed normally.
If ANY is missing → enter onboarding mode below.

---

## Step 1 — Profile (required)

**File:** `config/profile.yml`

This is the single source of truth for all commands. Fill it once — every mode reads it.

If missing, copy from example:
```bash
cp config/profile.example.yml config/profile.yml
```

Ask the user for:
- Full name + contact (email, phone, LinkedIn)
- Base location + timezone
- Target roles (what's the North Star role?)
- Compensation target range
- CV output format: `latex` (if using .tex template) or `html` (if using HTML template)
- Photo filename (if they have one, e.g. `CV-2.jpg`)

Fill in `config/profile.yml` with their answers. Key sections to complete:

```yaml
candidate:
  full_name: "..."
  email: "..."
  phone: "..."
  location: "..."

target_roles:
  primary:
    - "..."     # 2–3 North Star roles

narrative:
  headline: "..."          # 1-line professional summary
  superpowers:             # top 3–5 differentiators
    - "..."

compensation:
  target_range: "..."
  currency: "..."

cv:
  output_format: "latex"   # or "html"
  template_cv: "templates/cv-template-rb-lm.tex"   # adjust to actual filename
  template_cl: "templates/cover-letter-template-rb-lm.tex"

jobspy:
  search_terms:
    - "..."    # mirror your portals.yml title_filter positives
  location: "..."
  results_wanted: 30
  hours_old: 72
```

> The `jobspy.search_terms` should mirror your main target roles so JobSpy and the
> portal scanner (Levels 1–3) produce consistent, deduplicated results.

---

## Step 2 — CV (required)

**File:** `cv.md`

The canonical markdown CV that all modes read. If missing:

> "I don't have your CV yet. You can:
> 1. Paste your CV here — I'll convert it to clean markdown
> 2. Paste your LinkedIn URL — I'll extract the key info
> 3. Describe your experience — I'll draft it for you"

Create `cv.md` with standard sections:
- Professional Summary
- Work Experience (most recent first)
- Education
- Skills
- Optional: Projects, Certifications, Languages

---

## Step 3 — Research configuration (required for scan)

**File:** `portals.yml`

Configures what the scanner looks for across 4 levels (Playwright, ATS APIs, WebSearch, JobSpy).

If missing, copy from the example:
```bash
cp templates/portals.example.yml portals.yml
```

Then ask the user:
- What industries are you targeting? (e.g. aviation, luxury, industrial, finance)
- What locations? (e.g. Zürich, Switzerland, DACH, Remote)
- Which specific companies do you want to track?

Key sections to customize in `portals.yml`:
- `location_filter.positive` — list of acceptable cities/countries
- `title_filter.positive` — role keywords to include
- `title_filter.negative` — role keywords to exclude (e.g. "Junior", "Intern")
- `tracked_companies` — companies with `careers_url` for direct Playwright scraping
- `search_queries` — WebSearch queries for broad discovery

> The `jobspy.search_terms` in `profile.yml` should be a condensed version of
> your `title_filter.positive` entries — same intent, different mechanism.

---

## Step 4 — Archetype customization (recommended)

**File:** `modes/_profile.md`

If missing, auto-copy from template:
```bash
cp modes/_profile.template.md modes/_profile.md
```

Edit to match the user's specific archetypes, scoring weights, and proof points.
This file is the user-layer for all evaluation logic — never auto-overwritten by updates.

---

## Step 5 — Template setup (required for pdf/humanize)

**File:** your CV template (LaTeX or HTML)

The template is what gets filled with your profile data to produce the final PDF.

### Option A — LaTeX template (.tex)

Best for: precise formatting, academic/Swiss/European market, offline PDF generation.

Requirements:
```bash
which pdflatex || brew install mactex   # macOS
```

Place your `.tex` files in `templates/`:
- `templates/cv-template-yourname.tex`
- `templates/cover-letter-template-yourname.tex`

Then set in `profile.yml`:
```yaml
cv:
  output_format: "latex"
  template_cv: "templates/cv-template-yourname.tex"
  template_cl: "templates/cover-letter-template-yourname.tex"
```

The writer agent fills placeholders in the template (`\CLName`, `\CLCompanyName`, etc.)
and compiles to PDF via `generate-latex-rb.mjs`.

**Profile photo:** place `yourphoto.jpg` in the career-ops root. Set `cv.photo` in `profile.yml`.
Both are gitignored.

### Option B — HTML template (.html)

Best for: ATS optimization, modern design, Playwright PDF generation.

Place in `templates/`:
- `templates/cv-template.html`

Set in `profile.yml`:
```yaml
cv:
  output_format: "html"
  template_cv: "templates/cv-template.html"
```

PDF is generated via Playwright (`generate-pdf.mjs`). Requires:
```bash
npx playwright install chromium
```

### Template conventions

Regardless of format, the template must NOT hard-code personal data (name, address, etc.) —
those come from `profile.yml` and `cv.md` at generation time. The template defines layout,
fonts, and structure only.

---

## Step 6 — Final verification

```bash
python3 jobspy_scan.py --dry-run --config config/profile.yml   # jobspy reads profile ✓
node scan.mjs --dry-run 2>/dev/null || echo "scan.mjs ready"   # portal scanner ready ✓
ls cv.md portals.yml modes/_profile.md                         # all files present ✓
```

Once all checks pass, confirm:

> "You're all set. Here's what to do next:
>
> 1. `/jobhunter scan` — find new jobs across all sources (zero tokens)
> 2. `/jobhunter evaluate {URL}` — score any job against your profile
> 3. `/jobhunter help` — full command reference and workflow guide"
