# Job Autopilot

AI-powered job application automation: scrape jobs, tailor a **truthful, scored** resume
to each one, generate a cover letter, render ATS-friendly PDFs, and track it all.

## Quick Start

```bash
# 1. Master resume is the source of truth
#    data/master/resume.json   (preferences in data/master/preferences.json)

# 2. Configure the LLM backend in .env (see "LLM backend" below)

# 3. Run the app
venv/bin/python app.py            # http://localhost:8080

# 4. Run the pipeline / regenerate
venv/bin/python -m scripts.scheduled_scrape          # scrape + tailor (respects settings)
venv/bin/python -m scripts.regen_resumes unscored    # (re)tailor resumes not yet scored
```

## How resume tailoring works

1. Extract the JD's must/nice-have requirements (LLM).
2. Tailor the master resume to the JD (LLM, low temperature, faithful rewrite).
3. **Score the match in code** (deterministic): keyword coverage + flag any skill that
   doesn't trace back to the master resume.
4. Loop with gap feedback until must-have coverage ≥ 0.85, then **deterministically
   strip** any untraceable skill → **0 fabrications, guaranteed**.
5. The match score is stored per application — it doubles as a "should I apply?" signal.

See `src/tailor/engine.py`. Knobs (env-overridable): `TAILOR_MODEL`, plus `target` /
`max_attempts` args.

## LLM backend

The engine talks to any OpenAI-compatible endpoint, configured via `.env`
(loaded automatically by `engine._load_env()`):

```
# Local Ollama (free, default) — requires the box to be up
LLM_BASE_URL=http://10.0.0.18:11434/v1
LLM_API_KEY=ollama
TAILOR_MODEL=qwen3.6:35b-256k
```

To use a cloud model instead (e.g. when local is unavailable): set a cloud
`TAILOR_MODEL` (e.g. `google/gemini-2.5-flash-lite`), remove `LLM_BASE_URL`, and ensure
an OpenRouter key is available (`~/.hermes/.env` or `OPENROUTER_API_KEY`).
**Note:** Claude Pro/Max subscriptions cannot be used for API calls.

Benchmark models on one job: `venv/bin/python -m scripts.model_bench`.

## Structure

```
app.py                 # FastAPI server (API + dashboard)
src/
  scraper/scraper.py   # Multi-source job scrapers + dedup/filtering
  tailor/engine.py     # Scored, fidelity-checked tailoring + cover letters
  generator/pdf_gen.py # WeasyPrint PDFs, friendly Name_Title_Company.pdf names
  pipeline.py          # scrape → JD → salary filter → scored tailor → cover → PDF
  db.py                # SQLite schema + CRUD (jobs, applications, settings)
scripts/
  scheduled_scrape.py  # cron entry (every 3 days; respects auto_scrape_enabled)
  regen_resumes.py     # in-place resume regen ([N] | unscored)
  rename_pdfs.py       # re-render PDFs with friendly names + clean orphans
  rekey_jobs.py        # one-time stable-id migration
  model_bench.py       # compare models on one job
data/
  master/              # resume.json (source of truth) + preferences.json
  applications/        # generated PDFs + match data
  job_autopilot.db     # SQLite
```

## Scraping & dedup

Jobs are keyed by a stable `title+company` hash, so a re-scrape (e.g. the every-3-days
cron) **updates** an existing job without creating a duplicate or a new resume — only
genuinely new jobs are tailored. Toggle scraping with the `auto_scrape_enabled` setting
(currently on). `scheduled_scrape.py` takes an `fcntl` lock and skips if a run is already
running, so the cron can't overlap a manual or slow previous run and create duplicates.

## Paste a job link

Don't want to wait for the scraper? On the dashboard's **Pipeline** tab, paste a job
posting URL into **"Paste a job link"** and hit *Tailor from link*. It reads the JD off
the page, detects the title/company with the LLM, runs the same scored tailor + cover
letter, and the result shows up in Applications. (Sites that block scraping — LinkedIn
especially — may not yield enough text; you'll get a clear error if so.)

## Tech Stack

- **Python / FastAPI / SQLite** — backend + API
- **OpenAI-compatible LLM** — local Ollama (`qwen3.6:35b-256k`) by default, or OpenRouter
- **WeasyPrint** — ATS-friendly A4 PDFs
- **cron** — every-3-days scrape (`scripts/scheduled_scrape.py`)

## Dashboard

`venv/bin/python app.py` serves a single-file dashboard (`static/index.html`) at
http://localhost:8080 (proxied to job.steadiczech.com). Modern, mobile-responsive, and
**match-score-centric**: color-coded fit chips (green ≥70% / amber 50–69% / red <50%),
a score-distribution overview, a Top-Matches list with Apply buttons, and
filter/sort by fit on the Applications page. Auto-scrape can be toggled from Settings.

## Status

Working: scored tailoring, dedup, paste-a-link tailoring, PDF naming, every-3-days cron
(auto-scrape **on**, concurrency-locked), free local-LLM backend, and a redesigned
dashboard. **121 applications** currently — all tailored, scored, and 0-fabrication
(46 strong ≥0.70 / 64 partial / 11 weak). See [PROJECT.md](PROJECT.md),
[CLAUDE.md](CLAUDE.md), and the latest `SESSION_*.md` for details.
