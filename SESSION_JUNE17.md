# Job Autopilot — Session Summary (June 17, 2026)

## What Was Built
Full-stack AI job application automation platform.

### **Stack**
- **Backend:** FastAPI + SQLite + Python
- **Frontend:** Vanilla JS single-page app
- **PDF:** WeasyPrint (A4, corporate blue/amber template)
- **AI:** OpenRouter (Claude Sonnet) for resume tailoring + cover letters
- **Scraper:** Multi-source (LinkedIn, Indeed, RemoteOK, Built In + 6 more)
- **Proxy:** Apache reverse proxy at `https://job.steadiczech.com`

### **URLs**
- **Dashboard:** https://job.steadiczech.com
- **Local:** http://localhost:8080
- **Port:** 8080

---

## Current State (End of Session)

| Metric | Count |
|--------|-------|
| Jobs in DB | 95 |
| Applications | 94 |
| Resumes + Cover Letters | 94 each |
| PDFs Generated | 188 |
| Pipeline Runs | 5 |
| Errors | 0 |

### **All 94 applications use updated master resume:**
- Tagline: "Creative Technologist · Hybrid Technical-Creative Lead · AI Prototyping Specialist"
- Enhanced experience bullets (showing not telling)
- Skills matrix: AI & Agentic Coding, Creative & Prototyping, Content & Storytelling, Strategic Leadership
- Vimeo link added
- Professional PDF template (blue header, amber accents, page numbers)

---

## Settings (in DB: `data/job_autopilot.db`)

| Setting | Value |
|---------|-------|
| **Keywords** | virtual production, unreal engine, LED volume, creative technologist, AI workflow, real-time VFX, ICVFX, generative AI |
| **Location** | Los Angeles, Remote |
| **Salary Min** | $150,000 |
| **Target Companies** | Google, Disney, Anthropic, Sony, NVIDIA, Epic Games, Netflix, Adobe, Runway, Luma AI, Apple, Meta |
| **Sources** | linkedin, indeed, google, glassdoor, ziprecruiter, builtin, weworkremotely, remoteok, hired, targets |
| **Template** | default |

---

## Cron Jobs

| Job | Schedule | ID |
|-----|----------|----|
| **job-autopilot-daily-scrape** | `0 7 * * *` (daily 7am) | `5674bd5e254c` |

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server (API + frontend) |
| `src/db.py` | SQLite schema + CRUD |
| `src/pipeline.py` | Auto-pipeline (scrape → JD → salary filter → tailor → cover → PDF) |
| `src/scraper/scraper.py` | Multi-source job scraper with dedup + filtering |
| `src/tailor/engine.py` | LLM resume tailoring + cover letter generation |
| `src/generator/pdf_gen.py` | WeasyPrint PDF generation (corporate template) |
| `static/index.html` | Dashboard UI |
| `data/master/resume.json` | Master resume (source of truth) |
| `data/job_autopilot.db` | SQLite database |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stats` | GET | Dashboard stats |
| `/api/resume` | GET/PUT | Master resume |
| `/api/jobs` | GET | List jobs |
| `/api/applications` | GET | List applications |
| `/api/applications/{id}` | GET | Get application detail |
| `/api/applications/{id}/resume.pdf` | GET | Download resume PDF |
| `/api/applications/{id}/cover.pdf` | GET | Download cover letter PDF |
| `/api/pipeline/run` | POST | Run full pipeline |
| `/api/pipeline/regenerate` | POST | Re-tailor all resumes |
| `/api/pipeline/status` | GET | Pipeline status |
| `/api/pipeline/runs` | GET | Run history |
| `/api/settings` | GET/PUT | Pipeline settings |

---

## Features

### **Scraping**
- 10 sources (LinkedIn, Indeed, Google Jobs, Glassdoor, ZipRecruiter, Built In, We Work Remotely, RemoteOK, Hired, Target Companies)
- Dedup by title+company hash (MD5)
- Filters: salary ($150k min), job level (no intern/junior), relevance (no admin/medical)
- Location scoring: LA (100) → California (90) → USA/Remote (80) → International (50)

### **Pipeline**
1. Scrape jobs from all sources
2. Fetch job descriptions
3. Salary filter (only blocks jobs WITH salary listed below $150k)
4. Tailor resume with LLM
5. Generate cover letter with LLM
6. Generate PDFs (resume + cover letter)
7. Store in DB

### **PDF Template**
- A4, Helvetica Neue
- Deep Blue (#2b6cb0) + Amber (#d69e2e)
- Header: 24pt UPPERCASE name, tagline, contact row
- Skills matrix table (25% category / 75% items)
- Experience blocks with company/dates/role
- "Page X of Y" footer
- Justified text

---

## What to Do Next

### **Immediate**
- [ ] Process remaining 1 new job (95 total, 94 apps — 1 might have been filtered)
- [ ] Check PDF quality in browser

### **Short-term**
- [ ] Add SerpAPI key for Google Jobs (currently skipped)
- [ ] Set up auto-scrape interval (currently manual trigger)
- [ ] Add more target companies if needed

### **Medium-term**
- [ ] Add authentication to dashboard (currently open)
- [ ] Add email notifications when pipeline completes
- [ ] Add job application tracking (applied/interview/offer stages)

---

## How to Restart

```bash
# Kill existing
kill $(lsof -ti:8080)

# Start app
cd /home/server/job-autopilot
source venv/bin/activate
python app.py

# Or background
cd /home/server/job-autopilot && source venv/bin/activate && python app.py &
```

## How to Run Pipeline

```bash
# Full pipeline
curl -X POST http://localhost:8080/api/pipeline/run -H 'Content-Type: application/json' -d '{}'

# Regenerate all resumes
curl -X POST http://localhost:8080/api/pipeline/regenerate -H 'Content-Type: application/json'

# Check status
curl http://localhost:8080/api/stats
```

---

## Known Issues
- Some scraped jobs from Apple/Luma AI career pages had garbage titles (now filtered)
- Indeed often returns 403 (blocks scrapers)
- Google Jobs needs SerpAPI key (currently skipped)
- LinkedIn sometimes returns limited results due to anti-bot measures
- Salary filter only works when salary IS listed (by design — keeps jobs without salary info)
