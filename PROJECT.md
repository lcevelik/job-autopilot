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

- [x] Project setup and architecture design
- [x] Master resume data schema (JSON)
- [x] Resume tailoring engine (AI prompt chain)

## To Do

### Phase 1: Data Layer
- [ ] Parse user resume into structured JSON master data
- [ ] Create job board scraper (LinkedIn, Indeed, BuiltIn, Wellfound)
- [ ] Set up Google Sheet tracker (Company, Role, Date, Status, Follow-up)
- [ ] Create n8n connection and API key storage

### Phase 2: AI Engine
- [ ] Job analyzer — extract requirements, keywords, seniority from JD
- [ ] Resume tailor — rewrite summary, bullets, skills order per JD
- [ ] Cover letter generator — 3-paragraph tailored version
- [ ] ATS keyword optimizer — inject exact JD phrases
- [ ] PDF generator — clean, ATS-friendly output per application

### Phase 3: Automation (n8n Workflows)
- [ ] Workflow 1: Daily job scraper + AI scoring + Telegram digest
- [ ] Workflow 2: Resume tailor + cover letter + PDF generation
- [ ] Workflow 3: Auto-apply via LinkedIn Easy Apply (Playwright)
- [ ] Workflow 4: Follow-up email sequences (day 3, day 7)
- [ ] Workflow 5: Application tracker sync to Google Sheet

### Phase 4: Polish
- [ ] Dashboard — web UI showing application stats
- [ ] A/B testing — track which resume versions get callbacks
- [ ] Response monitoring — detect email replies, interview invites
- [ ] Salary negotiation AI — help with offer responses

## Done

- [x] Create GitHub repo (2026-05-29)

## Blocked

(none yet)

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

- LinkedIn RSS is dead (404). Use scraping or LinkedIn API.
- n8n API key in ~/.hermes/.env (N8N_API_KEY)
- Himalaya email config at ~/.config/himalaya/config.toml
- Gmail app password at ~/.hermes/.secrets/gmail-app-password
