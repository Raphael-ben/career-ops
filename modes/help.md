# Mode: help — Guided Workflow + Function Hierarchy

## Function Hierarchy

Three tiers. Everything flows from `scan` through evaluation to downstream actions.

### Top-level orchestrators
- **`pipeline`** — processes your entire pending inbox; calls auto-pipeline per URL
- **`batch`** — same as pipeline but spawns N parallel workers
- **`auto-pipeline`** (internal) — core sequence for one job: `evaluate` → `pdf` → tracker write

### Mid-level (callable directly or by orchestrators)
- **`evaluate`** — A-G scoring of one job; called by auto-pipeline or standalone
- **`pdf`** — CV generation; called by auto-pipeline or standalone
- **`compare`** — scores multiple offers side-by-side; may call evaluate internally

### Leaf functions (depend on evaluate having run first)
- **`humanize`** — removes AI writing patterns from LaTeX CV/cover letter output
- **`apply`** — reads evaluation report, pre-fills application form
- **`contact`** — reads evaluation report, drafts LinkedIn outreach
- **`interview`** — reads evaluation report, generates STAR stories + prep
- **`follow`** — follow-up cadence for active applications

### Truly independent
- **`scan`** — zero tokens; populates `pipeline.md` from all sources
- **`deep`** — standalone company research
- **`tracker`** — read-only view of your pipeline
- **`patterns`** — read-only win/loss analysis

### Mental model

```
scan → pipeline.md → [pipeline / batch / evaluate] → reports/ → [humanize → apply / contact / interview / follow]
```

---

## Linear Workflow

Follow these steps in order for each job application.

### Step 1 — Populate your pipeline (zero tokens)

```
/jobhunter scan
```

Scrapes company portals (Playwright), ATS APIs (Greenhouse/Ashby/Lever), WebSearch queries,
and job boards (LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter, Bayt, Naukri via JobSpy).
Results land in `data/pipeline.md`. Review and delete noise before proceeding.

### Step 2 — Evaluate a job

```
/jobhunter evaluate {URL or paste JD}
```

Produces an A-G score across 10 dimensions + gap analysis + legitimacy check.
**Skip anything below 3.5/5** — your time and the recruiter's time are both valuable.

### Step 3 — Generate your CV

```
/jobhunter pdf
```

ATS-optimized, keyword-injected from the JD. Single-page, clean for parsers.

### Step 4 — Humanize

```
/jobhunter humanize
```

Removes AI writing patterns from the LaTeX CV and cover letter. Applies 29 rules.
Does not change facts, metrics, or structure — only phrasing.

### Step 5 — Apply

```
/jobhunter apply
```

Reads your evaluation report and pre-fills the application form.
**Always review before submitting** — the system never auto-submits.

### Step 6 — Track and follow up

```
/jobhunter tracker    ← view pipeline status
/jobhunter follow     ← generate follow-up messages for active applications
```

---

## All Commands

```
DISCOVERY (zero tokens)
  scan          Scrape all job boards + company portals → pipeline.md

EVALUATION
  evaluate      Full A-G score for one job (URL or paste JD)
  compare       Side-by-side matrix for multiple offers
  deep          Deep company research before applying
  patterns      Analyse your win/loss history

APPLICATION
  pdf           Generate ATS-optimized CV PDF
  humanize      Remove AI writing patterns from LaTeX CV/cover letter
  apply         Pre-fill application form (stops before submit)
  contact       LinkedIn outreach message

TRACKING
  tracker       View and filter your pipeline
  pipeline      Process all pending URLs in batch
  batch         Evaluate 10+ jobs in parallel

PREPARATION
  interview     STAR stories + interview prep
  follow        Follow-up cadence for active applications

SYSTEM
  update        Check and apply updates for all components
  help          This guide
```
