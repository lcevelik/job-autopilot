# Job Autopilot — Session Summary (June 17-18, 2026)

Focus: make tailored resumes a **truthful, scored match** to each JD, fix scraping
dedup, fix runaway LLM cost, and switch to a **free local model**.

---

## 1. Scored, fidelity-checked resume tailoring

Replaced the old single-pass tailor (which fabricated skills) with a scored loop in
`src/tailor/engine.py`:

- `extract_requirements(jd)` — LLM pulls the JD's must/nice-have keywords.
- `tailor_resume(...)` — temperature 0.3, faithful rewrite, optional gap `feedback`.
- `score_match(tailored, requirements, master)` — **deterministic code** (not an LLM
  self-grade): keyword coverage + flags any skill not traceable to the master.
- `tailor_resume_scored(...)` — loops extract → tailor → score → re-tailor with gap
  feedback until must-coverage ≥ 0.85 (default `max_attempts=2`), then a
  **deterministic `_strip_fabricated()`** removes any untraceable skill. Result:
  **0 fabrications by construction**, regardless of model.
- Fidelity uses lenient token-overlap (`_skill_traces_to_master`, with a stopword
  filter) so rephrasings pass but genuinely-new skills (e.g. "Niagara") are stripped.

**Match score is stored** on each application (`applications.match_score` +
`match_report` JSON) and exposed via `/api/applications`. It doubles as a
**fit-triage signal** — low score = bad fit, don't apply (the old system hid bad fits
behind 15-31 fabricated skills; avg was 18.6 fabrications/resume across all 94).

## 2. Cross-run scraping dedup (was broken)

`pipeline.py` assigned **random UUID** job ids, so re-scraping created duplicate
jobs + duplicate resumes. Fixed: job id = `scraper._job_key(title, company)` (stable).
`upsert_job` does not reset status on conflict, so existing jobs aren't reprocessed.
`scripts/rekey_jobs.py` re-keyed the 95 existing jobs. **Verified**: re-scraping a job
produces no duplicate and no new resume.

## 3. PDF naming + clean folder

PDFs now generate as `Libor_Cevelik_<JobTitle>_<Company>.pdf`
(cover: `..._CoverLetter.pdf`), name derived from the resume's `personal.name`, job
title/company sanitized. `scripts/rename_pdfs.py` re-rendered all from DB content and
removed old `{hash}_resume.pdf` files. Download endpoint serves with the friendly name.

## 4. Cost blowup → cheap models → FREE LOCAL

- Opus 4.8 via OpenRouter cost **~$28 in one day**; account then hit **$0 of $45.26**.
- **Claude Pro/Max subscriptions cannot power API calls** (claude.ai + Claude Code only).
- User directive: **no Claude models**. Benchmarked non-Claude options
  (`scripts/model_bench.py`): Gemini Flash Lite (fast/cheap), DeepSeek-v4-pro (best
  quality, slow), Qwen3.6-plus (too slow), MiMo (doesn't respect JSON schema).
- **Final: local Ollama at `10.0.0.18` running `qwen3.6:35b-256k` — free.**
  Quality good (0.89 match on a fit job, 0 fab, valid JSON); slow (~16.8 tok/s,
  ~3-8 min/resume). `engine._client()` reads `LLM_BASE_URL`/`LLM_API_KEY` (600s
  timeout); `engine._load_env()` loads project `.env` so cron + scripts inherit it.

`.env` (new):
```
LLM_BASE_URL=http://10.0.0.18:11434/v1
LLM_API_KEY=ollama
TAILOR_MODEL=qwen3.6:35b-256k
```
Switch back to cloud = edit `.env` (set a cloud `TAILOR_MODEL`, remove `LLM_BASE_URL`)
and top up OpenRouter.

## 5. Robustness for cheap/reasoning models

`_chat_json()` requests `response_format=json_object` (BadRequestError fallback);
`_extract_json_object()` balanced-brace parser tolerates markdown fences + reasoning
text; None-content guard; token budgets raised (extract 4000, tailor 12000); non-dict
`skills` guarded. Reasoning models (MiMo, qwen3.6) "think" ~3k tokens before answering
and wrap output in markdown — these make them work.

## 6. Cron (every 3 days)

`crontab`: `0 6 */3 * *` runs `scripts/scheduled_scrape.py` → `run_pipeline()`, logs to
`data/scrape.log`. Now free (inherits local Qwen). **`auto_scrape_enabled` set to
`false`** (2026-06-18, user request) so the cron no-ops — no new jobs pulled while the
backfill runs. Re-enable: `set_setting('auto_scrape_enabled','true')`.

---

## 7. Dashboard redesign (`static/index.html`)

Full rewrite per user request: **clean modern light theme, inline SVG icons (NO emoji),
mobile-responsive** (desktop sidebar → fixed bottom tab bar; cards instead of cramped
tables). **Match-score-centric**: color chips (green ≥70% / amber 50-69% / red <50%),
a distribution bar + median on the dashboard, a Top-Matches list with Apply buttons, and
filter chips (All/Strong/Partial/Weak) on Applications. Detail view shows covered vs.
missing keywords from `match_report`. **Fixed a latent bug**: the old detail view did
`JSON.parse(tailored_resume)` which always failed silently (it's a Python `str(dict)`,
not JSON) — now uses `match_report` (valid JSON) + PDF links. Added an Auto-scrape toggle
in Settings. App runs via `venv/bin/python app.py` on :8080 (Apache proxy →
job.steadiczech.com); auto-refreshes the dashboard every 15s.

Also added `CLAUDE.md` (repo guidance for future Claude Code instances).

## Status at session end

- **All 94 resumes redone clean** on local Qwen — 0 failures, **0 fabrications**.
  Score distribution: median 0.60, range 0.20–0.96 → **26 strong (≥0.70), 41 partial,
  27 weak**. (The overnight backfill log was `data/regen67.log`.)
- Re-tailor again any time (idempotent): `venv/bin/python -m scripts.regen_resumes [N|unscored]`
- **Scraping disabled** (`auto_scrape_enabled=false`); cron is a no-op until re-enabled
  (toggle in the Settings page, or `set_setting('auto_scrape_enabled','true')`).
- Dashboard live at http://localhost:8080.

## Suggested next steps

- Apply to the 26 strong-fit jobs (≥0.70) — list them via the dashboard Top Matches.
- Enrich `data/master/resume.json` with granular tool keywords to lift partial-fit scores.
- Optional: cloud fallback when the Ollama box is down; show scores already done.
- Clean up `data/applications/_bench_*.json` benchmark artifacts when no longer needed.

## New / changed files

| File | Purpose |
|------|---------|
| `.env` | LLM backend config (local Ollama) — loaded by `engine._load_env()` |
| `src/tailor/engine.py` | scored loop, fidelity strip, JSON robustness, env-driven client |
| `src/pipeline.py` | stable job-id dedup, scored tailor, match_score persistence, PDF naming |
| `src/generator/pdf_gen.py` | friendly `Name_Title_Company.pdf` filenames |
| `src/db.py` | `match_score` + `match_report` columns (migration) |
| `scripts/scheduled_scrape.py` | cron entry (respects `auto_scrape_enabled`) |
| `scripts/regen_resumes.py` | in-place resume regen (`[N]` / `unscored`) |
| `scripts/rekey_jobs.py` | one-time stable-id migration |
| `scripts/rename_pdfs.py` | re-render PDFs with friendly names + clean orphans |
| `scripts/model_bench.py` | benchmark models on one job |
| `static/index.html` | redesigned dashboard (modern, mobile, SVG icons, match-score) |
| `CLAUDE.md` | repo guidance for future Claude Code instances |

## Known issues / next

- Local Qwen depends on the `10.0.0.18` Ollama box being up; no cloud fallback wired.
- Match scores sit ~0.4–0.6 on many jobs — the master resume lacks some granular tool
  keywords those JDs list (master-content improvement, not a model issue).
- `gemma4:12b` not installed on the Ollama box (only `gemma4:31b`).
- Leftover `data/applications/_bench_*.json` comparison files can be deleted.
