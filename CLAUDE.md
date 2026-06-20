# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AI job-application automation: scrape jobs → tailor a **truthful, scored** resume to each → generate a cover letter → render ATS PDFs → track in SQLite. FastAPI backend + vanilla-JS dashboard, single process. There is **no build system, no test suite, and no linter** — it runs straight from the `venv`.

## Commands

```bash
# Run the app (FastAPI + dashboard) on port 8080
venv/bin/python app.py

# Tailor pipeline (scrape → tailor → PDF); respects DB settings incl. auto_scrape_enabled
venv/bin/python -m scripts.scheduled_scrape

# (Re)generate resumes in place from current master + stored JDs
venv/bin/python -m scripts.regen_resumes            # all
venv/bin/python -m scripts.regen_resumes 10         # first 10
venv/bin/python -m scripts.regen_resumes unscored   # only apps without a match_score (idempotent)

# Re-render all PDFs with the friendly naming + delete orphan files
venv/bin/python -m scripts.rename_pdfs

# Benchmark LLM models on one real job (writes data/applications/_bench_*.json)
venv/bin/python -m scripts.model_bench

# Smoke-test the scored tailoring loop end-to-end (sample JD)
venv/bin/python -m src.tailor.engine
```

Always run scripts as modules from the repo root (`-m scripts.X`). They `sys.path`-insert the root and the engine loads `.env` via an absolute path, so cwd is tolerant — but `app.py`'s own `.env`/relative paths assume the repo root is cwd.

`requirements.txt` is **incomplete** — the real runtime deps (`fastapi`, `uvicorn`, `weasyprint`, `httpx`) are already in `venv/`. Install missing ones into `venv` rather than trusting that file.

## LLM backend (read before touching tailoring)

All LLM calls go through one OpenAI-compatible client in `src/tailor/engine.py::_client()`, configured **entirely by `.env`** (loaded by `engine._load_env()` at import, before `TAILOR_MODEL` is read):

```
LLM_BASE_URL=http://10.0.0.18:11434/v1   # local Ollama (free, default). Omit for OpenRouter.
LLM_API_KEY=ollama                        # ignored by local servers
TAILOR_MODEL=qwen3.6:35b-256k             # any OpenAI-style model id for the configured endpoint
```

- Default is the **free local Ollama box**; it must be reachable or generation fails (no cloud fallback wired).
- To use cloud: set a cloud `TAILOR_MODEL` (e.g. `google/gemini-2.5-flash-lite`), remove `LLM_BASE_URL`, and provide `OPENROUTER_API_KEY` (read from project `.env` then `~/.hermes/.env` by `get_api_key()`).
- **Claude Pro/Max subscriptions cannot be used** — they don't grant API access.
- Local/reasoning models are slow (minutes/resume) and "think" before answering, so the client timeout is 600s and token budgets are deliberately high. `_chat_json()` requests `response_format=json_object` (with a fallback) and `_parse_json_response()` uses a balanced-brace extractor to survive markdown fences / reasoning preambles. Don't lower these without understanding why they exist.

## Core architecture

**The heart is the scored, fidelity-checked tailoring loop** in `src/tailor/engine.py` — understanding it requires reading that one file end to end:

1. `extract_requirements(jd)` — LLM pulls must/nice-have JD keywords.
2. `tailor_resume(master, jd, feedback="")` — faithful low-temp rewrite (accepts gap feedback for retries).
3. `score_match(tailored, requirements, master)` — **pure Python, not an LLM self-grade**: keyword coverage + flags any skill that doesn't trace to the master.
4. `tailor_resume_scored(...)` — loops 1→3 until must-coverage ≥ `target` (0.85), then `_strip_fabricated()` deterministically removes any untraceable skill. **Net effect: 0 fabrications by construction, independent of model quality** — the model only affects coverage polish. The returned `match_score` doubles as a fit-triage signal (≥ ~0.7 = worth applying).

`src/pipeline.py` orchestrates the whole run (scrape → fetch JD → salary filter → `tailor_resume_scored` → cover letter → PDF) and persists results. `app.py` exposes it as FastAPI endpoints; long runs execute via `BackgroundTasks` gated by a module-level `_pipeline_running` flag.

**Single-link entry point.** `pipeline.add_job_from_url(url, template, tailor=True)` builds a job from a pasted URL: it scrapes the JD off the page, calls `engine.extract_job_meta(jd)` (one LLM call → title/company/location, since a pasted link has no job-card metadata), and upserts the job **flagged `source="manual"`** under the **same `_job_key` id scheme** as the scraper (re-pasting updates, never duplicates). Returns `{"error": ...}` if the page yields too little text (scrape-blocked sites). Two endpoints drive it:
- `POST /api/jobs/add-url` (`tailor=False`, **synchronous**) — powers the dedicated **Add Job** dashboard tab: adds the manual job *without* tailoring and returns the detected title/company. The user then tailors on demand via the per-job **Run via pipeline** button (`POST /api/applications/{id}/process` → `run_single_job`).
- `POST /api/pipeline/run-url` (`tailor=True`, `BackgroundTasks` behind `_pipeline_running`) — one-shot add **and** tailor. Kept as an API capability; the UI no longer calls it.

Manual jobs render with a violet "Manual" badge + accent row and are pinned to the top of the Jobs list (the dashboard's only `source`-based styling).

`src/db.py` (SQLite at `data/job_autopilot.db`) runs `init_db()` **on import** (creates tables, runs column migrations like `match_score`/`match_report`, and seeds default `settings`). The DB file is **gitignored** (it's runtime data that changes every run) — a fresh clone auto-creates an empty, ready DB on first import; there is no schema dump to keep in sync (`init_db` is the schema). `data/master/resume.json` is the single source of truth for resume content.

## Non-obvious conventions

- **Dedup depends on stable job ids.** `pipeline.py` sets `job["id"] = scraper._job_key(title, company)` (an MD5 hash), and `upsert_job` does **not** reset `status` on conflict. This is what makes the every-3-days cron safe: a re-scraped job is updated, not duplicated, and isn't re-tailored. Never go back to random/uuid job ids.
- **`tailored_resume` is stored as a Python `str(dict)`, not JSON.** Read it back with `ast.literal_eval` (see `scripts/regen_resumes.py`) or `eval` (see `app.py`) — `json.loads` will fail.
- **`match_score` / `match_report` are computed in code**, never by the model. Treat them as ground truth for fidelity; don't replace with an LLM grade.
- **PDF filenames are `<Name>_<JobTitle>_<Company>.pdf`** (cover: `..._CoverLetter.pdf`), built in `pdf_gen._pdf_filename()` from the resume's own `personal.name`. The download endpoints serve with the on-disk basename. `regen_resumes`/`rename_pdfs` overwrite in place (no orphans); the older `/api/pipeline/regenerate` endpoint deletes+recreates and can orphan files.
- **Scraping is gated by the `auto_scrape_enabled` setting** (in the `settings` table). `scheduled_scrape.py` checks it and no-ops if not `"true"`. The cron (`0 6 */3 * *`) calls that script. Currently **enabled**.
- **`scheduled_scrape.py` holds an exclusive `fcntl` lock** (`data/.scrape.lock`) for the whole run and skips if it can't acquire it. This is the **only cross-process guard** — `_pipeline_running` in `app.py` is in-memory and does **not** stop a separate cron process. The lock exists because a run can take many hours on the local LLM, and an overlapping run double-tailors jobs and creates duplicate applications (this actually happened on 2026-06-19 when the cron fired during a manual run). Don't remove it; if you add another headless pipeline entry point, have it take the same lock.
- `data/master/resume.json` has per-template `summary_templates` and `bullets` (default/engineering/ai_ml/management), but `pdf_gen.py` currently renders only the `default` keys.
- **Dashboard** is a single static file (`static/index.html`, served at `/`): modern, mobile-responsive, inline SVG icons (no emoji), built around `match_score` (fit chips, distribution, Top-Matches, filters). It reads `match_report` (valid JSON) for the keyword breakdown — do **not** `JSON.parse(tailored_resume)` (Python repr, not JSON; the old code did this and silently failed).

## Project log

`PROJECT.md` (kanban-parser format — exact `##` headings matter) and the dated `SESSION_*.md` files are the running design/decision log. Update them when you make architectural changes.
