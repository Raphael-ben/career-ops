# Career-Ops

[English](README.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [한국어](README.ko-KR.md) | [日本語](README.ja.md) | [Русский](README.ru.md) | [简体中文](README.cn.md) | [繁體中文](README.zh-TW.md)

<p align="center">
  <a href="https://x.com/santifer"><img src="docs/hero-banner.jpg" alt="Career-Ops — Multi-Agent Job Search System" width="800"></a>
</p>

<p align="center">
  <em>I spent months applying to jobs the hard way. So I engineered the system I wish I had.</em><br>
  Companies use AI to filter candidates. <strong>I just gave candidates AI to <em>choose</em> companies.</strong><br>
  <em>Now it's open source.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-000?style=flat&logo=anthropic&logoColor=white" alt="Claude Code">
  <img src="https://img.shields.io/badge/OpenCode-111827?style=flat&logo=terminal&logoColor=white" alt="OpenCode">
  <img src="https://img.shields.io/badge/Gemini_CLI-4285F4?style=flat&logo=google&logoColor=white" alt="Gemini CLI">
  <img src="https://img.shields.io/badge/Codex_(soon)-6B7280?style=flat&logo=openai&logoColor=white" alt="Codex">
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/Go-00ADD8?style=flat&logo=go&logoColor=white" alt="Go">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT">
  <a href="https://discord.gg/8pRpHETxa4"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  <br>
  <img src="https://img.shields.io/badge/EN-blue?style=flat" alt="EN">
  <img src="https://img.shields.io/badge/ES-red?style=flat" alt="ES">
  <img src="https://img.shields.io/badge/DE-grey?style=flat" alt="DE">
  <img src="https://img.shields.io/badge/FR-blue?style=flat" alt="FR">
  <img src="https://img.shields.io/badge/PT--BR-green?style=flat" alt="PT-BR">
  <img src="https://img.shields.io/badge/KO-white?style=flat" alt="KO">
  <img src="https://img.shields.io/badge/JA-red?style=flat" alt="JA">
  <img src="https://img.shields.io/badge/ZH--CN-red?style=flat" alt="ZH-CN">
  <img src="https://img.shields.io/badge/ZH--TW-blue?style=flat" alt="ZH-TW">
</p>

---

<p align="center">
  <img src="docs/demo.gif" alt="Career-Ops Demo" width="800">
</p>

<p align="center"><strong>740+ job listings evaluated · 100+ personalized CVs · 1 dream role landed</strong></p>

<p align="center"><a href="https://discord.gg/8pRpHETxa4"><img src="https://img.shields.io/badge/Join_the_community-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a></p>

## What Is This

Career-Ops turns any AI coding CLI into a full job search command center. Instead of manually tracking applications in a spreadsheet, you get an AI-powered pipeline that:

- **Evaluates offers** with a structured A-F scoring system (10 weighted dimensions)
- **Generates tailored PDFs** -- ATS-optimized CVs customized per job description
- **Scans portals** automatically (Greenhouse, Ashby, Lever, company pages)
- **Processes in batch** -- evaluate 10+ offers in parallel with sub-agents
- **Tracks everything** in a single source of truth with integrity checks

> **Important: This is NOT a spray-and-pray tool.** Career-ops is a filter -- it helps you find the few offers worth your time out of hundreds. The system strongly recommends against applying to anything scoring below 4.0/5. Your time is valuable, and so is the recruiter's. Always review before submitting.

Career-ops is agentic: Claude Code navigates career pages with Playwright, evaluates fit by reasoning about your CV vs the job description (not keyword matching), and adapts your resume per listing.

> **Heads up: the first evaluations won't be great.** The system doesn't know you yet. Feed it context -- your CV, your career story, your proof points, your preferences, what you're good at, what you want to avoid. The more you nurture it, the better it gets. Think of it as onboarding a new recruiter: the first week they need to learn about you, then they become invaluable.

Built by someone who used it to evaluate 740+ job offers, generate 100+ tailored CVs, and land a Head of Applied AI role. [Read the full case study](https://santifer.io/career-ops-system).

## Features

| Feature | Description |
|---------|-------------|
| **Auto-Pipeline** | Paste a URL, get a full evaluation + PDF + tracker entry |
| **6-Block Evaluation** | Role summary, CV match, level strategy, comp research, personalization, interview prep (STAR+R) |
| **Interview Story Bank** | Accumulates STAR+Reflection stories across evaluations -- 5-10 master stories that answer any behavioral question |
| **Negotiation Scripts** | Salary negotiation frameworks, geographic discount pushback, competing offer leverage |
| **ATS PDF Generation** | Keyword-injected CVs with Space Grotesk + DM Sans design |
| **Portal Scanner** | 45+ companies pre-configured (Anthropic, OpenAI, ElevenLabs, Retool, n8n...) + custom queries across Ashby, Greenhouse, Lever, Wellfound |
| **Batch Processing** | Parallel evaluation with `claude -p` workers |
| **Dashboard TUI** | Terminal UI to browse, filter, and sort your pipeline |
| **Human-in-the-Loop** | AI evaluates and recommends, you decide and act. The system never submits an application -- you always have the final call |
| **Pipeline Integrity** | Automated merge, dedup, status normalization, health checks |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/santifer/career-ops.git
cd career-ops && npm install
npx playwright install chromium   # Required for HTML→PDF generation

# 2. Install Python dependencies (for JobSpy scanner)
pip install -r requirements.txt

# 3. Open Claude Code and let it guide you
claude   # Opens onboarding if config/profile.yml or cv.md is missing

# 4. Start using
# Paste a job URL or run /jobhunter
```

> **The system is designed to be customized by Claude itself.** Modes, archetypes, scoring weights, negotiation scripts -- just ask Claude to change them. It reads the same files it uses, so it knows exactly what to edit.

---

## Setup Guide

> **First launch automatically starts onboarding.** When Claude Code opens in this directory, it checks for required files and walks you through setup if any are missing. This section documents what happens and what each file does.

### Prerequisites

| Requirement | Purpose | Install |
|-------------|---------|---------|
| [Claude Code](https://claude.ai/code) | AI agent runtime | Download from claude.ai |
| Node.js 18+ | Scripts (PDF, scanner, tracker) | `brew install node` or nodejs.org |
| Python 3.10+ | JobSpy board scraper | `brew install python` or python.org |
| `pdflatex` | LaTeX→PDF compilation | `brew install --cask mactex` (macOS) |
| Playwright Chromium | HTML→PDF generation | `npx playwright install chromium` |

> You only need **one** of pdflatex or Playwright depending on your template format (see Template Setup below). Both is fine too.

---

### Step 1 — Profile (single source of truth)

**File: `config/profile.yml`**

This is the single source of truth for **all** `/jobhunter` commands. Fill it once — every mode (evaluate, scan, pdf, humanize, batch) reads it. It is gitignored and never committed.

```bash
cp config/profile.example.yml config/profile.yml
# Then edit with your details (or let Claude fill it from your CV)
```

Key sections:

```yaml
candidate:
  full_name: "Your Name"
  email: "you@email.com"
  phone: "+1 555 000 0000"
  location: "City, Country"

target_roles:
  primary:
    - "Head of Strategy"
    - "Business Development Director"
  market: "Switzerland (Zürich, Remote/DACH)"

narrative:
  headline: "One-line professional summary"
  superpowers:
    - "Your top differentiator"
    - "Second differentiator"

compensation:
  target_range: "CHF 120K–160K base"
  currency: "CHF"

cv:
  output_format: "latex"          # "latex" (default) or "html"
  photo: "photo.jpg"              # relative to career-ops root, gitignored
  template_cv: "templates/cv-template.tex"
  template_cl: "templates/cover-letter-template.tex"

jobspy:
  search_terms:
    - "Business Development Manager Switzerland"
    - "Head of Strategy Switzerland"
  location: "Switzerland"
  results_wanted: 30
  hours_old: 72
```

> The `jobspy.search_terms` should mirror your `portals.yml` `title_filter.positive` entries — same intent, different scraping mechanism. This ensures the Level 4 JobSpy scan and Levels 1–3 portal scan produce consistent, deduplicated results.

---

### Step 2 — CV

**File: `cv.md`** (project root, gitignored)

The canonical markdown CV that all modes read. If missing, Claude will ask you to:
1. Paste your CV — it converts to clean markdown
2. Paste your LinkedIn URL — it extracts key info
3. Describe your experience — it drafts for you

Standard sections: Professional Summary, Work Experience (most recent first), Education, Skills, and optionally Projects, Certifications, Languages.

---

### Step 3 — Research configuration

**File: `portals.yml`** (project root, gitignored)

Configures what the scanner looks for across all 4 levels (Playwright, ATS APIs, WebSearch, JobSpy).

```bash
cp templates/portals.example.yml portals.yml
# Then customize location_filter, title_filter, and tracked_companies
```

Key sections to customize:

```yaml
location_filter:
  positive: ["Zürich", "Switzerland", "DACH", "Remote"]
  negative: ["London", "Paris"]   # exclude if not relevant

title_filter:
  positive: ["Head of Strategy", "Business Development", "Corporate Development"]
  negative: ["Junior", "Intern", "Graduate"]   # filter out seniority mismatches

tracked_companies:
  - name: "Rolex"
    careers_url: "https://jobs.rolex.com/"
    ats: "workday"
  - name: "ABB"
    careers_url: "https://careers.abb/global/en"
    ats: "taleo"
```

> Keep `jobspy.search_terms` in `profile.yml` aligned with `title_filter.positive` here for consistent results across all scan levels.

---

### Step 4 — Template Setup

The template is what gets filled with your profile data at generation time. It defines layout, fonts, and structure — **never hard-code personal data** in the template.

#### Option A — LaTeX template (`.tex`) — Recommended for European/Swiss market

Best for: precise formatting, academic-style CVs, offline PDF generation.

```bash
# 1. Verify pdflatex is installed
which pdflatex || brew install --cask mactex

# 2. Place your .tex files in templates/
#    templates/cv-template-yourname.tex
#    templates/cover-letter-template-yourname.tex

# 3. Set in config/profile.yml:
cv:
  output_format: "latex"
  template_cv: "templates/cv-template-yourname.tex"
  template_cl: "templates/cover-letter-template-yourname.tex"
```

The writer agent fills LaTeX placeholders (`\CLName`, `\CLCompanyName`, `\CLPosition`, etc.) and compiles to PDF via `generate-latex-rb.mjs`.

**LaTeX template placeholders** — your template must define these commands:

| Placeholder | Value |
|-------------|-------|
| `\CLName` | Candidate full name |
| `\CLEmail` | Email |
| `\CLPhone` | Phone |
| `\CLAddress` | Address |
| `\CLCompanyName` | Target company name |
| `\CLPosition` | Target role title |
| `\CLDate` | Letter date |
| `\CLBodyA` | Cover letter paragraph 1 |
| `\CLBodyB` | Cover letter paragraph 2 |
| `\CLBodyC` | Cover letter paragraph 3 |

#### Option B — HTML template (`.html`) — Best for ATS optimization

Best for: modern design, ATS keyword injection, Playwright PDF generation.

```bash
# 1. Install Playwright
npx playwright install chromium

# 2. Place your template in templates/
#    templates/cv-template.html

# 3. Set in config/profile.yml:
cv:
  output_format: "html"
  template_cv: "templates/cv-template.html"
```

PDF generated via `generate-pdf.mjs`. The HTML template uses `{{PLACEHOLDER}}` syntax for dynamic data injection.

#### Profile photo

Place your photo in the career-ops root (e.g., `photo.jpg` or `CV-photo.jpg`). Set `cv.photo` in `profile.yml`. Both the photo and all generated PDFs are gitignored.

---

### Step 5 — First scan

Once setup is complete:

```bash
# Dry-run to verify JobSpy config reads correctly
python3 jobspy_scan.py --dry-run --config config/profile.yml

# Run a full scan across all 4 levels
/jobhunter scan
```

The scan populates `data/pipeline.md` with new job URLs. Then:

```bash
/jobhunter pipeline   # Evaluate all pending URLs
/jobhunter tracker    # View your application status
```

---

### What's gitignored (never committed)

| File/folder | Contains |
|-------------|----------|
| `cv.md` | Your personal CV |
| `config/profile.yml` | Your profile, targets, comp |
| `portals.yml` | Your research config |
| `config/profile_bank.json` | Extended profile bank |
| `data/` | Pipeline, applications, scan history |
| `output/` | Generated CVs and cover letters |
| `reports/` | Evaluation reports |
| `interview-prep/` | Interview prep notes |
| `*.pdf` | All compiled PDFs |
| `photo.jpg`, `CV-*.jpg` | Profile photos |

Everything else (modes, scripts, templates, batch config) is system layer — safe to commit and share.

## Gemini CLI Integration

Career-ops supports [Gemini CLI](https://github.com/google-gemini/gemini-cli) natively — the same way it supports Claude Code and OpenCode. All 15 slash commands are available, using the same `modes/*.md` evaluation logic.

### Option A — Native Gemini CLI (Recommended)

```bash
# 1. Install Gemini CLI
npm install -g @google/gemini-cli
# or: npx @google/gemini-cli --version

# 2. Authenticate (free — uses your Google account)
gemini auth

# 3. Run in the career-ops directory
cd career-ops
gemini

# 4. Use slash commands just like Claude Code
/jobhunter "Senior AI Engineer at Anthropic..."
/jobhunter-evaluate --file ./jds/openai.txt
/jobhunter-scan
/jobhunter-pdf
/jobhunter-tracker
```

The `GEMINI.md` file is auto-loaded as context. All 15 commands are defined in `.gemini/commands/*.toml`.

### Option B — Standalone API Script (No CLI install needed)

```bash
# 1. Get a free API key at https://aistudio.google.com/apikey
cp .env.example .env
# Edit .env → set GEMINI_API_KEY=your_key_here

# 2. Install dependencies
npm install

# 3. Evaluate a job description
node gemini-eval.mjs "We are looking for a Senior AI Engineer..."
node gemini-eval.mjs --file ./jds/my-job.txt
npm run gemini:eval -- "JD text here"
```

> **Free tier:** Both options work without billing. Native CLI uses Google OAuth; the API script uses `gemini-2.0-flash` (15 RPM, 1M tokens/day free).

## Usage

Career-ops is a single slash command with multiple modes:

```
/jobhunter                → Show all available commands
/jobhunter {paste a JD}   → Full auto-pipeline (evaluate + PDF + tracker)
/jobhunter scan           → Scan portals + job boards for new offers (zero tokens)
/jobhunter evaluate       → Score a single offer A–G
/jobhunter compare        → Side-by-side matrix for multiple offers
/jobhunter pdf            → Generate ATS-optimized CV
/jobhunter humanize       → Remove AI writing patterns from LaTeX CV/cover letter
/jobhunter batch          → Batch evaluate multiple offers in parallel
/jobhunter tracker        → View application status
/jobhunter apply          → Fill application forms with AI
/jobhunter pipeline       → Process pending URLs
/jobhunter contact        → LinkedIn outreach message
/jobhunter deep           → Deep company research
/jobhunter interview      → STAR story prep for a specific company
/jobhunter follow         → Follow-up cadence tracker
/jobhunter help           → Full command reference + function hierarchy
```

Or just paste a job URL or description directly -- career-ops auto-detects it and runs the full pipeline.

## How It Works

```
You paste a job URL or description
        │
        ▼
┌──────────────────┐
│  Archetype       │  Classifies: LLMOps / Agentic / PM / SA / FDE / Transformation
│  Detection       │
└────────┬─────────┘
         │
┌────────▼─────────┐
│  A-F Evaluation  │  Match, gaps, comp research, STAR stories
│  (reads cv.md)   │
└────────┬─────────┘
         │
    ┌────┼────┐
    ▼    ▼    ▼
 Report  PDF  Tracker
  .md   .pdf   .tsv
```

## Pre-configured Portals

The scanner comes with **45+ companies** ready to scan and **19 search queries** across major job boards. Copy `templates/portals.example.yml` to `portals.yml` and add your own:

**AI Labs:** Anthropic, OpenAI, Mistral, Cohere, LangChain, Pinecone
**Voice AI:** ElevenLabs, PolyAI, Parloa, Hume AI, Deepgram, Vapi, Bland AI
**AI Platforms:** Retool, Airtable, Vercel, Temporal, Glean, Arize AI
**Contact Center:** Ada, LivePerson, Sierra, Decagon, Talkdesk, Genesys
**Enterprise:** Salesforce, Twilio, Gong, Dialpad
**LLMOps:** Langfuse, Weights & Biases, Lindy, Cognigy, Speechmatics
**Automation:** n8n, Zapier, Make.com
**European:** Factorial, Attio, Tinybird, Clarity AI, Travelperk

**Job boards searched:** Ashby, Greenhouse, Lever, Wellfound, Workable, RemoteFront

## Dashboard TUI

The built-in terminal dashboard lets you browse your pipeline visually:

```bash
cd dashboard
go build -o career-dashboard .
./career-dashboard --path ..
```

Features: 6 filter tabs, 4 sort modes, grouped/flat view, lazy-loaded previews, inline status changes.

## Project Structure

```
career-ops/
├── CLAUDE.md                    # Agent instructions (auto-loaded)
├── cv.md                        # Your CV — gitignored, create this
├── portals.yml                  # Research config — gitignored, create this
├── jobspy_scan.py               # JobSpy scraper (Python) — Level 4 scan
├── requirements.txt             # Python deps (python-jobspy, pyyaml)
├── config/
│   ├── profile.example.yml      # Profile template — copy to profile.yml
│   └── profile.yml              # Your profile (gitignored, single source of truth)
├── modes/                       # Skill modes
│   ├── _shared.md               # Shared evaluation context
│   ├── _profile.md              # Your archetype customization (gitignored)
│   ├── evaluate.md              # Single offer A-G scoring
│   ├── compare.md               # Multi-offer comparison matrix
│   ├── contact.md               # LinkedIn outreach
│   ├── scan.md                  # 4-level portal + board scanner
│   ├── pdf.md                   # PDF generation
│   ├── help.md                  # Command reference + function hierarchy
│   ├── onboarding.md            # First-launch setup guide
│   ├── rb/
│   │   └── humanize.md          # LaTeX humanizer (29 rules)
│   ├── de/                      # German (DACH) modes
│   ├── fr/                      # French modes
│   └── ja/                      # Japanese modes
├── templates/
│   ├── cv-template.html         # HTML CV template (for Playwright PDF)
│   ├── cv-template.tex          # LaTeX CV template
│   ├── portals.example.yml      # Scanner config template
│   └── states.yml               # Canonical application statuses
├── batch/
│   ├── batch-prompt.md          # Self-contained worker prompt
│   └── batch-runner.sh          # Orchestrator script
├── dashboard/                   # Go TUI pipeline viewer
├── data/                        # Tracking data — gitignored
├── reports/                     # Evaluation reports — gitignored
├── output/                      # Generated CVs + cover letters — gitignored
├── fonts/                       # Space Grotesk + DM Sans
├── docs/                        # Architecture docs and plans
└── examples/                    # Sample CV, report, proof points
```

## Tech Stack

![Claude Code](https://img.shields.io/badge/Claude_Code-000?style=flat&logo=anthropic&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white)
![Go](https://img.shields.io/badge/Go-00ADD8?style=flat&logo=go&logoColor=white)
![Bubble Tea](https://img.shields.io/badge/Bubble_Tea-FF75B5?style=flat&logo=go&logoColor=white)

- **Agent**: Claude Code with custom skills and modes
- **PDF**: Playwright/Puppeteer + HTML template
- **Scanner**: Playwright + Greenhouse API + WebSearch
- **Dashboard**: Go + Bubble Tea + Lipgloss (Catppuccin Mocha theme)
- **Data**: Markdown tables + YAML config + TSV batch files

## Also Open Source

- **[cv-santiago](https://github.com/santifer/cv-santiago)** -- The portfolio website (santifer.io) with AI chatbot, LLMOps dashboard, and case studies. If you need a portfolio to showcase alongside your job search, fork it and make it yours.

## About the Author

I'm Santiago -- Head of Applied AI, former founder (built and sold a business that still runs with my name on it). I built career-ops to manage my own job search. It worked: I used it to land my current role.

My portfolio and other open source projects → [santifer.io](https://santifer.io)

## Star History

<a href="https://www.star-history.com/?repos=santifer%2Fcareer-ops&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=santifer/career-ops&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=santifer/career-ops&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=santifer/career-ops&type=timeline&legend=top-left" />
 </picture>
</a>

## Disclaimer

**career-ops is a local, open-source tool — NOT a hosted service.** By using this software, you acknowledge:

1. **You control your data.** Your CV, contact info, and personal data stay on your machine and are sent directly to the AI provider you choose (Anthropic, OpenAI, etc.). We do not collect, store, or have access to any of your data.
2. **You control the AI.** The default prompts instruct the AI not to auto-submit applications, but AI models can behave unpredictably. If you modify the prompts or use different models, you do so at your own risk. **Always review AI-generated content for accuracy before submitting.**
3. **You comply with third-party ToS.** You must use this tool in accordance with the Terms of Service of the career portals you interact with (Greenhouse, Lever, Workday, LinkedIn, etc.). Do not use this tool to spam employers or overwhelm ATS systems.
4. **No guarantees.** Evaluations are recommendations, not truth. AI models may hallucinate skills or experience. The authors are not liable for employment outcomes, rejected applications, account restrictions, or any other consequences.

See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) for full details. This software is provided under the [MIT License](LICENSE) "as is", without warranty of any kind.

## Contributors

<a href="https://github.com/santifer/career-ops/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=santifer/career-ops" />
</a>

Got hired using career-ops? [Share your story!](https://github.com/santifer/career-ops/issues/new?template=i-got-hired.yml)

## License

MIT

## Let's Connect

[![Website](https://img.shields.io/badge/santifer.io-000?style=for-the-badge&logo=safari&logoColor=white)](https://santifer.io)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/santifer)
[![X](https://img.shields.io/badge/X-000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/santifer)
[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/8pRpHETxa4)
[![Email](https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:hi@santifer.io)
