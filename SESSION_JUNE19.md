# Job Autopilot — Session Summary (June 19, 2026)

Focus: add a **paste-a-job-link → tailored resume** flow, turn the every-3-days cron
**on**, and recover from + permanently fix a **concurrent-run duplication** incident.

---

## 1. Paste a job link → tailored resume

New single-URL entry point so you don't have to wait for the scraper.

- **`engine.extract_job_meta(jd)`** — one LLM call (reuses `_chat_json`/`_parse_json_response`)
  that pulls `{title, company, location}` out of a JD's text. Needed because a pasted link
  has no job-card metadata (the scraper got those from cards).
- **`pipeline.add_job_from_url(url, template)`** — scrapes the JD via the existing
  `extract_job_description`, detects title/company, upserts the job under the **same
  `_job_key` (title+company hash)** as the scraper (re-pasting updates, never duplicates),
  then reuses `run_single_job` for the scored tailor + cover letter. Returns
  `{"error": ...}` if the page yields < 80 chars (scrape-blocked sites).
- **`POST /api/pipeline/run-url`** (`app.py`) — `{url, template}`, runs in `BackgroundTasks`
  behind the `_pipeline_running` flag, same pattern as the main run button.
- **Dashboard** (`static/index.html`) — new "Paste a job link" card at the top of the
  Pipeline tab + `runUrl()` that polls pipeline status like the other actions.

PDFs are generated lazily on download (the download endpoints regenerate), consistent with
`run_single_job`. No fabrication risk — it goes through the same `tailor_resume_scored` loop.

**Reworked into a dedicated "Add Job" tab (same session):** per user request the flow was
split so *adding* and *tailoring* are separate steps. `add_job_from_url` gained a
`tailor` flag; new **`POST /api/jobs/add-url`** (`tailor=False`, synchronous) just scrapes
+ detects + adds the job flagged `source="manual"`. A new **Add Job** nav tab hosts the
paste box plus a "Your manual jobs" list, each row with a **Run via pipeline** button
(→ `/api/applications/{id}/process`) and a match-score chip once tailored. The older
`POST /api/pipeline/run-url` (add **and** tailor) stays as an API capability but the UI no
longer calls it. Manual jobs are violet-badged and pinned to the top of the Jobs list.

## 2. Auto-scrape enabled (first live cron run)

- Confirmed the cron was already installed (`0 6 */3 * *` → `scripts.scheduled_scrape`,
  logs `data/scrape.log`) but **`auto_scrape_enabled` was `false`**, so it had been a no-op.
- Set **`auto_scrape_enabled = true`**. Settings in effect: 8 keywords (virtual production,
  unreal engine, LED volume, ICVFX, generative AI, …), location LA + Remote, all 10 sources,
  salary filter ≥ $150k.
- Triggered one run manually to verify. It pulled **27 genuinely new jobs** on top of the
  existing 94.

## 3. Concurrency incident + permanent fix

**What happened:** the manual run started 2026-06-18 18:02 and ran ~13h (local LLM is slow,
~100 jobs). The **real cron fired at 06:00 on 06-19 while that run was still going** and
started a *second* full pipeline. `scheduled_scrape.py` had **no cross-process guard** (the
`_pipeline_running` flag lives in `app.py`'s memory, a different process), so the two runs
overlapped and **double-tailored jobs → 86 duplicate applications** (207 total vs. the ~121
expected), with jobs left in `processing`.

**Recovery:**
- Killed the runaway cron process; marked pipeline run #7 `stopped`.
- Deduped applications: for each job kept the **best** (highest `match_score`, tie-break
  newest), deleted the other 86. Duplicate PDFs shared the same on-disk filename (named by
  job, not app id) so they'd overwritten each other — no orphan cleanup needed.
- Result: **121 applications, 0 duplicates.**

**Permanent fix:** `scheduled_scrape.py` now takes an exclusive **`fcntl` advisory lock**
(`data/.scrape.lock`) for the whole run and prints *"another pipeline run is still in
progress — skipping this cycle."* if it can't acquire it. Auto-released on process exit, so
no stale locks. **Verified** by holding the lock and confirming a second invocation skips.
This is the only cross-process guard — any future headless pipeline entry point should take
the same lock.

---

## Status at session end

- **121 applications**, one per job, **0 duplicates**, all 0-fabrication.
  Fit: **46 strong (≥0.70) / 64 partial (0.40–0.69) / 11 weak (<0.40)**.
- **Auto-scrape ON**; next cron **2026-06-22 06:00**, now safe against overlap.
- Paste-a-link flow live on the dashboard.
- Note: a full pipeline run takes ~13h on the local Ollama box — fine for a 3-day cadence,
  but switch `TAILOR_MODEL` to a faster/cloud model if you ever need speed.

## New / changed files

| File | Change |
|------|--------|
| `src/tailor/engine.py` | + `extract_job_meta(jd)` |
| `src/pipeline.py` | + `add_job_from_url(url, template)` |
| `app.py` | + `POST /api/pipeline/run-url` (`UrlRequest`) |
| `static/index.html` | + "Paste a job link" card + `runUrl()` |
| `scripts/scheduled_scrape.py` | + `fcntl` lock guard against overlapping runs |

## Suggested next steps

- Apply to the 46 strong-fit jobs (≥0.70) — Top Matches on the dashboard.
- Enrich `data/master/resume.json` with granular tool keywords to lift partial-fit scores.
- Optional: a textarea fallback to paste JD **text** directly for scrape-blocked sites.
