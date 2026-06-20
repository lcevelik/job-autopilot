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

## 8. Dedicated "Add Job" tab (split add vs. tailor)

Reworked the paste flow into a 7th nav tab. `add_job_from_url` gained a `tailor`
flag; **`POST /api/jobs/add-url`** (synchronous, `tailor=False`) just scrapes + detects
title/company + adds the job flagged `source="manual"`. The tab has the paste box plus a
"Your manual jobs" list, each row with a **Run via pipeline** button
(→ `/api/applications/{id}/process`) and a match-score chip once tailored. Manual jobs get
a violet badge + accent and are pinned to the top of the Jobs list.
`POST /api/pipeline/run-url` (add **and** tailor) kept as an API capability, unused by UI.

## 9. Stop tracking the SQLite DB

`data/job_autopilot.db` changed every run, constantly dirtying the tree. Untracked it
(`git rm --cached`) + gitignored `data/*.db` (+ wal/shm); `init_db()` already builds the
schema and seeds settings on import, so a fresh clone auto-creates a ready DB (verified).
Added `data/.gitkeep`. Trade-off noted: the 121 apps now live only on this box.

## 10. systemd unit (install pending)

Added `deploy/job-autopilot.service` (Restart=always, journal logging) + `deploy/
install-service.sh`. Needs `sudo bash deploy/install-service.sh` (root) — **not yet run**;
the app is still a manual `setsid python app.py` process, no boot/crash auto-restart.

## 11. Summary voice auto-matched to the JD

The 5 summary "voices" were half-wired: `pdf_gen` always rendered the `default` slot, so
the category dropdown never affected output. Now **`select_summary_angle(jd, requirements)`**
deterministically scores the 5 voices by signal phrases in the JD + extracted requirements
and picks the best (fallback `default`); `tailor_resume` seeds the rendered slot with that
voice so the model tailors the right angle. Recorded as `report.summary_angle`, logged,
stored as the app's `template`, and shown as a chip in the app detail. Verified end-to-end:
an "AI/ML Architect" JD selected `ai_ml` and rendered the ai_ml voice (score 0.759).
Distribution across 126 stored JDs: ai_ml 45 / engineering 31 / management 33 / executive
10 / default 7.

## 12. Resume data gaps fixed (from LiborCevelik2026.pdf)

Compared the master against the real PDF in `/media/server/Storage/Sync`. Master was missing
the **Studio Mirage** job (Video Producer & Director, Prague 2005–2009), the entire
**Awards & Recognition** section (Moonlight/Academy Award, Latin Grammy nom), and the
**Illumination Experience (Hurlbut Visuals)** cert. Added all three to the master (backup at
`data/master/resume.json.bak`) and added a **conditional awards render block** in `pdf_gen.py`
(renders only when awards exist, so old apps stay clean). Verified by rendering a PDF.
**Existing 121 apps are snapshots** — they won't show the new content until re-tailored
(`scripts.regen_resumes`, ~13h on local LLM).

## New / changed files (whole session)

| File | Change |
|------|--------|
| `src/tailor/engine.py` | + `extract_job_meta`, `select_summary_angle`, summary-seed in `tailor_resume`, angle in scored loop |
| `src/pipeline.py` | + `add_job_from_url` (with `tailor` flag), store `summary_angle` as template, log angle |
| `app.py` | + `POST /api/pipeline/run-url`, `POST /api/jobs/add-url` |
| `static/index.html` | Add Job tab + manual badges, summary-angle chip |
| `scripts/scheduled_scrape.py` | `fcntl` lock guard |
| `src/generator/pdf_gen.py` | conditional Awards & Recognition block |
| `data/master/resume.json` | + Studio Mirage, awards, missing cert (gitignored) |
| `.gitignore` | ignore logs, lock, `*.db` |
| `deploy/job-autopilot.service`, `deploy/install-service.sh` | systemd unit + installer |

## Suggested next steps

- **Run `sudo bash deploy/install-service.sh`** to finish the systemd setup.
- Optionally re-tailor the 121 apps so they get Studio Mirage + awards (`regen_resumes`, slow).
- Apply to the strong-fit jobs (≥0.70) — Top Matches on the dashboard.
- Optional: a textarea fallback to paste JD **text** directly for scrape-blocked sites.
