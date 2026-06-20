# Job Autopilot

AI-powered job application automation — tailored resumes, auto-apply, tracking, follow-ups.

## Goals

- Apply to 50+ jobs/week on autopilot
- Tailor resume per job (keywords, skills, summary, bullets)
- Generate custom cover letter per application
- Auto-submit via LinkedIn Easy Apply + company portals
- Track all applications in Google Sheet
- Automated follow-up email sequences
- Daily job digest via Telegram

## In Progress

- [ ] Apply to the 46 strong-fit jobs (match ≥ 0.70)
- [ ] Improve master resume coverage of granular tool keywords (lifts match scores)

## To Do

### Phase 1: Data Layer
- [x] Parse user resume into structured JSON master data
- [x] Create job board scraper (LinkedIn, Indeed, BuiltIn, Wellfound)
- [ ] Set up Google Sheet tracker (Company, Role, Date, Status, Follow-up)
- [ ] Create n8n connection and API key storage

### Phase 2: AI Engine
- [x] Job analyzer — extract requirements, keywords, seniority from JD
- [x] Resume tailor — rewrite summary, bullets, skills order per JD
- [x] Summary voice auto-matched to each JD (engineering/ai_ml/management/executive/default)
- [x] Cover letter generator — 3-paragraph tailored version
- [x] ATS keyword optimizer — scored coverage loop + deterministic fidelity strip
- [x] PDF generator — clean ATS-friendly output, friendly Name_Title_Company.pdf names
- [x] Awards & Recognition block on resumes (conditional render)
- [x] Match scoring per application (stored + API) — doubles as a fit-triage signal

### Phase 3: Automation
- [x] Cron scraper every 3 days (scripts/scheduled_scrape.py)
- [x] Cross-run dedup via stable job ids — no duplicate jobs/resumes on re-scrape
- [x] Concurrency guard (fcntl lock) so cron/manual runs can't overlap & duplicate
- [x] Paste-a-link → tailored resume (dedicated Add Job tab + Run-via-pipeline)
- [x] Multi-location scraping — search each location separately (LA, Remote, California)
- [ ] Auto-apply via LinkedIn Easy Apply (Playwright)
- [ ] Follow-up email sequences (day 3, day 7)
- [ ] Application tracker sync to Google Sheet

### Phase 4: Polish
- [x] Dashboard — web UI (FastAPI + vanilla JS) showing application stats
- [x] Redesigned dashboard — modern, mobile-responsive, SVG icons, match-score triage
- [ ] Cloud fallback when local Ollama box is unavailable
- [ ] Response monitoring — detect email replies, interview invites
- [ ] Salary negotiation AI — help with offer responses

## Done

- [x] Create GitHub repo (2026-05-29)
- [x] Full-stack app: scraper + tailor + PDF + dashboard, 94 applications (2026-06-17)
- [x] Scored, fidelity-checked tailoring — 0 fabrications by construction (2026-06-18)
- [x] Match scoring stored per application + exposed via API (2026-06-18)
- [x] Fix cross-run dedup (stable job ids); re-key existing jobs (2026-06-18)
- [x] Friendly PDF filenames Name_Title_Company.pdf + folder cleanup (2026-06-18)
- [x] Every-3-days cron scraper installed (2026-06-18)
- [x] Switch LLM backend to free local Ollama (qwen3.6:35b-256k) via .env (2026-06-18)
- [x] JSON-output robustness for cheap/reasoning models (2026-06-18)
- [x] Redo all 94 resumes clean & scored on local Qwen — 0 fabrications (2026-06-18)
- [x] Redesign dashboard: modern, mobile-friendly, SVG icons, match-score triage (2026-06-18)
- [x] Paste-a-link feature: URL → JD scrape → detect title/company → scored tailor (2026-06-19)
- [x] Enable auto-scrape (`auto_scrape_enabled=true`); first live cron run pulled 27 new jobs (2026-06-19)
- [x] Fix cron concurrency: fcntl lock in scheduled_scrape.py (a cron run had overlapped a manual run and created 86 duplicate applications, since cleaned) (2026-06-19)
- [x] Dedicated Add Job tab: add manual jobs by link, Run-via-pipeline on demand (2026-06-19)
- [x] Stop tracking SQLite DB; init_db() recreates it on first run (2026-06-19)
- [x] systemd unit + installer (deploy/) — install pending sudo (2026-06-19)
- [x] Summary voice auto-matched to the JD (deterministic select_summary_angle) (2026-06-20)
- [x] Fix resume data gaps vs. real PDF: add Studio Mirage job, Awards section, missing cert (2026-06-20)
- [x] Multi-location scraping + search California + add AMD to target companies (2026-06-20)

## Blocked

- [ ] OpenRouter credits exhausted ($45.26 used) — mitigated by moving to free local
      Ollama; cloud paths need a top-up to use again.

## Releases

- v0.4.0 — released 2026-06-20 — Add Job tab, JD-matched summary voice, Awards/Studio-Mirage resume fixes, multi-location (California) scraping + AMD, DB untracked, systemd unit
- v0.3.0 — released 2026-06-19 — Paste-a-link tailoring, auto-scrape enabled (first live cron, +27 jobs → 121 applications), cron concurrency lock
- v0.2.0 — released 2026-06-18 — Scored truthful tailoring, dedup fix, local-LLM backend, cron, all 94 resumes redone clean, redesigned match-score dashboard
- v0.1.0 — released 2026-06-17 — Initial full-stack app: scrape → tailor → PDF → dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    JOB AUTOPILOT                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ LinkedIn  │    │  Indeed  │    │ Wellfound│          │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘          │
│       └───────────────┼───────────────┘                  │
│                       ▼                                  │
│              ┌─────────────────┐                         │
│              │  n8n Job Scraper│  (daily cron)           │
│              └────────┬────────┘                         │
│                       ▼                                  │
│              ┌─────────────────┐                         │
│              │  AI Job Scorer  │  (match vs profile)     │
│              └────────┬────────┘                         │
│                       ▼                                  │
│              ┌─────────────────┐                         │
│              │  Filter 70%+    │                         │
│              └────────┬────────┘                         │
│                       ▼                                  │
│  ┌─────────────────────────────────────┐                │
│  │        RESUME TAILOR ENGINE         │                │
│  │  ┌───────────┐  ┌────────────────┐  │                │
│  │  │ Master    │  │ JD Analyzer    │  │                │
│  │  │ Resume    │→ │ (keywords,     │  │                │
│  │  │ (JSON)    │  │  skills, tone) │  │                │
│  │  └───────────┘  └───────┬────────┘  │                │
│  │                         ▼           │                │
│  │  ┌────────────────────────────────┐ │                │
│  │  │ AI Tailor (per-job rewrite)    │ │                │
│  │  │ • Summary mirrors JD           │ │                │
│  │  │ • Skills reordered             │ │                │
│  │  │ • Bullets reframed             │ │                │
│  │  │ • Keywords injected            │ │                │
│  │  └───────────────┬────────────────┘ │                │
│  │                  ▼                  │                │
│  │  ┌──────────┐  ┌──────────────────┐ │                │
│  │  │ PDF Gen  │  │ Cover Letter Gen │ │                │
│  │  └──────────┘  └──────────────────┘ │                │
│  └─────────────────────────────────────┘                │
│                       ▼                                  │
│              ┌─────────────────┐                         │
│              │  Auto-Submit    │  (Playwright)           │
│              │  Easy Apply +   │                         │
│              │  Portal Fill    │                         │
│              └────────┬────────┘                         │
│                       ▼                                  │
│  ┌──────────────────────────────────────┐               │
│  │         APPLICATION TRACKER          │               │
│  │  Google Sheet: Company, Role, Date,  │               │
│  │  Status, Resume Version, Follow-up   │               │
│  └──────────────────┬───────────────────┘               │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐               │
│  │       FOLLOW-UP SEQUENCES            │               │
│  │  Day 3: "Following up..."            │               │
│  │  Day 7: "Still interested..."        │               │
│  │  Day 14: "Final check..."            │               │
│  └──────────────────────────────────────┘               │
│                     ▼                                    │
│              ┌─────────────────┐                         │
│              │  Telegram       │  (daily digest)         │
│              │  Dashboard      │  (web UI)               │
│              └─────────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

- **n8n** — workflow orchestration (already running on server)
- **OpenRouter** — AI models for scoring, tailoring, cover letters
- **Playwright** — browser automation for LinkedIn Easy Apply
- **Google Sheets API** — application tracking
- **Himalaya** — email sending (SMTP) + monitoring (IMAP)
- **Telegram Bot** — daily digest, notifications
- **Python** — resume parsing, PDF generation
- **React** — dashboard UI (optional, phase 4)

## Resume Data Schema (Draft)

```json
{
  "personal": {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "website": ""
  },
  "summary_templates": {
    "default": "Senior engineer with X years...",
    "ai_ml": "AI/ML engineer with expertise in...",
    "management": "Engineering leader with..."
  },
  "experience": [
    {
      "company": "",
      "title": "",
      "start": "",
      "end": "",
      "bullets": {
        "default": ["bullet 1", "bullet 2"],
        "ai_ml": ["AI-focused bullet 1", "AI-focused bullet 2"],
        "management": ["Leadership bullet 1"]
      },
      "technologies": []
    }
  ],
  "skills": {
    "all": ["Python", "React", "AWS", "..."],
    "categories": {
      "languages": [],
      "frameworks": [],
      "cloud": [],
      "ai_ml": [],
      "tools": []
    }
  },
  "education": [],
  "certifications": [],
  "target_roles": {
    "titles": [],
    "locations": [],
    "salary_min": 0,
    "remote_ok": true,
    "dealbreakers": []
  }
}
```

## Notes

- **LLM backend**: configured in project `.env` (loaded by `engine._load_env()`).
  Default = local Ollama `qwen3.6:35b-256k` at `http://10.0.0.18:11434/v1` (free, slow
  ~3-8 min/resume). Switch to cloud by editing `.env` (`TAILOR_MODEL`, drop `LLM_BASE_URL`).
- **Claude Pro/Max subscriptions cannot power API calls** — claude.ai + Claude Code only.
- **Tailoring**: `tailor_resume_scored()` loops extract→tailor→score until must-coverage
  ≥ 0.85, then `_strip_fabricated()` removes untraceable skills → 0 fabrications.
  `match_score` is stored per application; use ≥ ~0.7 as an "apply" threshold.
- **Summary voice**: `engine.select_summary_angle(jd, requirements)` deterministically
  picks one of the 5 master voices per JD (signal-phrase scoring; fallback `default`).
  The chosen voice is seeded into the rendered slot so the model tailors the right angle;
  stored as `report.summary_angle` and the app's `template`, shown as a chip in detail.
- **Resume content**: `data/master/resume.json` is the source of truth (gitignored, backup
  `.bak`). Mirrors the real `LiborCevelik2026.pdf` — 5 jobs incl. Studio Mirage, an
  `awards` section (rendered conditionally), education, certs. **Tailored resumes are
  snapshots**: existing apps don't reflect master edits until re-tailored.
- **Search**: `search_keywords` + `search_location` (now `Los Angeles, Remote, California`
  — each location searched separately) + `scrape_sources` + `target_companies` (incl. AMD).
- **Dedup**: job id = `title+company` hash; re-scrape never duplicates. Toggle scraping
  via the `auto_scrape_enabled` setting (currently **`true`**).
- **Add a job by link**: dedicated **Add Job** dashboard tab → `POST /api/jobs/add-url`
  (`add_job_from_url(tailor=False)`) scrapes the JD, `engine.extract_job_meta()` detects
  title/company, adds it flagged `source="manual"` WITHOUT tailoring; user hits
  **Run via pipeline** per job to tailor. Scrape-blocked sites may return an error.
- **Server**: manual `setsid venv/bin/python app.py` on :8080. systemd unit at
  `deploy/job-autopilot.service` — install with `sudo bash deploy/install-service.sh`
  (pending) for boot/crash auto-restart.
- **Regen resumes** (no LLM cost for re-render of PDFs; LLM for re-tailor):
  `venv/bin/python -m scripts.regen_resumes [N|unscored]`. Idempotent — `unscored` skips done.
- **Cron**: `0 6 */3 * *` → `scripts/scheduled_scrape.py`, logs `data/scrape.log`. The
  script takes an `fcntl` lock (`data/.scrape.lock`) and skips if a run is already in
  progress — a run can take ~13h on the local LLM, so overlapping runs would duplicate
  applications (happened 2026-06-19, now guarded).
- LinkedIn RSS is dead (404). Use scraping or LinkedIn API.
- n8n API key in ~/.hermes/.env (N8N_API_KEY); OpenRouter key also in ~/.hermes/.env
- Himalaya email config at ~/.config/himalaya/config.toml
- Gmail app password at ~/.hermes/.secrets/gmail-app-password
