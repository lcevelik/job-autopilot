"""Auto-pipeline: scrape → fetch JD → tailor resume → generate cover letter."""

import uuid
import traceback
from datetime import datetime
from pathlib import Path

from src.db import (
    upsert_job, get_jobs, get_job, update_job,
    create_application, update_application,
    create_pipeline_run, update_pipeline_run,
    get_setting, get_stats,
)
from src.scraper.scraper import JobScraper
from src.tailor.engine import tailor_resume_scored, generate_cover_letter
from src.generator.pdf_gen import generate_resume_pdf, generate_cover_letter_pdf

MASTER_RESUME = str(Path(__file__).parent.parent / "data" / "master" / "resume.json")


def _extract_salary(job_text: str) -> int:
    """Extract salary from job text. Returns annual salary or 0 if not found."""
    if not job_text:
        return 0
    text = job_text.lower()
    
    import re
    
    # Hourly rate → annual (2080 hrs/year)
    hourly_patterns = [
        r'\$(\d+(?:\.\d+)?)\s*(?:-|to)\s*\$(\d+(?:\.\d+)?)\s*(?:usd\s*)?(?:/hr|per hour|hourly)',  # $24.00 - $26.00 USD hourly
        r'\$(\d+(?:\.\d+)?)\s*(?:/hr|per hour|hourly)',  # $24/hr
        r'(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:usd\s*)?(?:/hr|per hour|hourly)',  # 24-26 hourly
        r'pay[:\s]*\$(\d+(?:\.\d+)?)\s*(?:-|to)\s*\$(\d+(?:\.\d+)?)',  # Pay: $24.00 - $26.00
    ]
    
    for pattern in hourly_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if isinstance(m, tuple):
                rate = float(m[1])  # Take upper end of range
            else:
                rate = float(m)
            annual = int(rate * 2080)
            if annual > 10000:  # Sanity check
                return annual
    
    # Annual salary patterns
    annual_patterns = [
        r'salary[:\s]*\$(\d{2,3})[kK]',                        # salary: $150k
        r'compensation[:\s]*\$(\d{2,3})[kK]',                  # compensation: $150k
        r'\$(\d{2,3})[kK]\s*(?:-|to)\s*\$(\d{2,3})[kK]',     # $150K - $200K
        r'(\d{2,3})k\s*(?:-|to)\s*(\d{2,3})k',                # 150k-200k
        r'\$(\d{3}),(\d{3})',                                   # $150,000
        r'\$(\d{3})[kK]',                                       # $150K (standalone)
    ]
    
    for pattern in annual_patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if isinstance(m, tuple):
                val = int(m[0])
            else:
                val = int(m)
            if val < 1000:
                val *= 1000
            if val > 10000:
                return val
    
    return 0  # No salary found


def _check_salary_filter(job: dict, salary_min: int) -> bool:
    """Check if job passes salary filter. Returns True if job should be kept.
    
    Rules:
    - If no salary info found → KEEP (most jobs don't list salary)
    - If salary IS listed and >= min → KEEP
    - If salary IS listed and < min → SKIP
    - Senior/Lead/Staff/Director/VP titles auto-pass regardless
    """
    if salary_min <= 0:
        return True
    
    # Senior roles typically pay $150k+ regardless of what's listed
    title = job.get("title", "").lower()
    senior_keywords = ["senior", "lead", "staff", "principal", "director", "vp", "head", "architect", "manager"]
    if any(kw in title for kw in senior_keywords):
        return True
    
    # Check description for salary info
    desc = job.get("description", "") or ""
    salary = _extract_salary(desc + " " + title)
    
    if salary == 0:
        # No salary info found → KEEP (don't penalize for missing info)
        return True
    
    return salary >= salary_min


def run_pipeline(keywords: str = None, location: str = None, template: str = None, sources: str = None):
    """
    Full automation pipeline:
    1. Scrape jobs from LinkedIn/Indeed
    2. Fetch job descriptions
    3. Tailor resume for each
    4. Generate cover letter for each
    5. Store everything in DB
    """
    run_id = create_pipeline_run()
    log_lines = []

    if not keywords:
        keywords = get_setting("search_keywords", "virtual production,unreal engine")
    if not location:
        location = get_setting("search_location", "Los Angeles")
    if not template:
        template = get_setting("default_template", "default")

    sources_raw = sources or get_setting("scrape_sources", "linkedin,indeed,remoteok,builtin")
    sources_list = [s.strip() for s in sources_raw.split(",") if s.strip()]

    stats = {"scraped": 0, "fetched": 0, "tailored": 0, "covers": 0, "errors": 0}

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        log_lines.append(line)
        print(line)

    try:
        log(f"Pipeline started — keywords='{keywords}', location='{location}'")

        # ── Step 1: Scrape jobs ────────────────────────────────────────────────
        scraper = JobScraper()
        keyword_list = [k.strip() for k in keywords.split(",")]

        all_new_jobs = []
        for kw in keyword_list:
            log(f"Scraping: '{kw}' in {location}")
            # Search each keyword across all sources, 10 results each
            jobs = scraper.scrape_all(kw, location, sources=sources_list, num_per_source=10)

            for job in jobs:
                # Stable id derived from title+company so re-scraping the same job
                # across runs hits upsert's ON CONFLICT (which preserves status) and
                # does NOT create a duplicate or a second resume. Random UUIDs broke this.
                job["id"] = scraper._job_key(job["title"], job["company"])
                job["scraped_at"] = datetime.now().isoformat()
                job["status"] = "new"

                all_new_jobs.append(job)

        log(f"Scraped {len(all_new_jobs)} unique jobs")

        # Save to DB first
        for job in all_new_jobs:
            upsert_job(job)

        # ── Step 2: Fetch ALL job descriptions first ──────────────────────────
        jobs_to_process = get_jobs(status="new", limit=30)
        log(f"Fetching descriptions for {len(jobs_to_process)} jobs...")

        for i, job in enumerate(jobs_to_process):
            job_id = job["id"]
            try:
                update_job(job_id, status="processing")
                description = ""
                if job.get("url") and job["url"] != "":
                    description = scraper.extract_job_description(job["url"])

                if not description:
                    description = f"Position: {job['title']} at {job['company']}. Location: {job.get('location', 'N/A')}."

                update_job(job_id, description=description, status="fetched")
                stats["fetched"] += 1
            except Exception as e:
                log(f"  JD fetch failed for {job_id}: {e}")
                update_job(job_id, status="error")

        # ── Step 3: Salary filter (AFTER descriptions are fetched) ────────────
        salary_min = int(get_setting("salary_min", "0"))
        if salary_min > 0:
            fetched_jobs = get_jobs(status="fetched")
            removed = 0
            for job in fetched_jobs:
                if not _check_salary_filter(job, salary_min):
                    # Delete job and mark as filtered
                    update_job(job["id"], status="filtered")
                    removed += 1
                    log(f"  Salary filter: removed '{job['title']}' at {job['company']}")
            if removed:
                log(f"Salary filter: removed {removed} jobs below ${salary_min:,}/yr")

        stats["scraped"] = len(get_jobs(status="fetched"))

        # ── Step 4: Tailor resumes + cover letters ───────────────────────────
        jobs_to_tailor = get_jobs(status="fetched", limit=100)
        log(f"Tailoring resumes for {len(jobs_to_tailor)} jobs")

        for i, job in enumerate(jobs_to_tailor):
            job_id = job["id"]
            try:
                update_job(job_id, status="processing")
                log(f"[{i+1}/{len(jobs_to_tailor)}] {job['title']} at {job['company']}")

                # Get description from DB (already fetched in step 2)
                description = job.get("description", "")
                if not description:
                    description = f"Position: {job['title']} at {job['company']}."

                # ── Tailor resume ──────────────────────────────────────
                app_id = str(uuid.uuid4())[:8]
                create_application(app_id, job_id, template)
                log(f"  Tailoring resume (app: {app_id})")

                match_report = None
                try:
                    tailored, match_report = tailor_resume_scored(MASTER_RESUME, description, template)
                    log(f"  Resume tailored OK — match {match_report['score']} "
                        f"(must {match_report['must_coverage']}), "
                        f"missing {len(match_report['missing'])}, "
                        f"fabricated {len(match_report['fabricated'])}")
                except Exception as e:
                    log(f"  Tailor FAILED: {e}")
                    update_application(app_id, status="error", error=str(e))
                    stats["errors"] += 1
                    update_job(job_id, status="error")
                    continue

                # ── Generate cover letter ──────────────────────────────
                log(f"  Generating cover letter")
                try:
                    cover = generate_cover_letter(MASTER_RESUME, description, job.get("company", "the company"))
                    log(f"  Cover letter generated OK")
                    stats["covers"] += 1
                except Exception as e:
                    log(f"  Cover letter FAILED: {e}")
                    cover = ""

                # Save application
                import json as _json
                update_application(
                    app_id,
                    tailored_resume=str(tailored) if tailored else None,
                    cover_letter=cover,
                    match_score=match_report["score"] if match_report else None,
                    match_report=_json.dumps(match_report) if match_report else None,
                    status="done",
                    completed_at=datetime.now().isoformat(),
                )

                # Generate PDFs
                try:
                    if tailored:
                        generate_resume_pdf(tailored, app_id, job.get("title", ""), job.get("company", ""))
                        log(f"  Resume PDF generated")
                    if cover:
                        personal = tailored.get("personal", {}) if tailored else {}
                        generate_cover_letter_pdf(
                            cover,
                            personal.get("name", ""),
                            personal.get("email", ""),
                            personal.get("phone", ""),
                            personal.get("location", ""),
                            app_id,
                            job.get("title", ""),
                            job.get("company", ""),
                        )
                        log(f"  Cover letter PDF generated")
                except Exception as e:
                    log(f"  PDF generation failed (non-fatal): {e}")

                stats["tailored"] += 1
                log(f"  Application {app_id} complete")

            except Exception as e:
                log(f"  ERROR processing {job_id}: {e}")
                stats["errors"] += 1
                update_job(job_id, status="error")

        # ── Done ───────────────────────────────────────────────────────────────
        log(f"Pipeline complete: {stats}")
        update_pipeline_run(
            run_id,
            completed_at=datetime.now().isoformat(),
            status="done",
            jobs_scraped=stats["scraped"],
            jobs_fetched=stats["fetched"],
            resumes_tailored=stats["tailored"],
            cover_letters_generated=stats["covers"],
            errors=stats["errors"],
            log="\n".join(log_lines),
        )

    except Exception as e:
        log(f"FATAL: {e}\n{traceback.format_exc()}")
        update_pipeline_run(
            run_id,
            completed_at=datetime.now().isoformat(),
            status="error",
            errors=stats["errors"],
            log="\n".join(log_lines),
        )

    return {"run_id": run_id, "stats": stats, "log": log_lines}


def add_job_from_url(url: str, template: str = "default", tailor: bool = True) -> dict:
    """Build a job from a pasted job-posting URL.

    Reads the JD off the page, detects title/company via the LLM, stores the job
    with the same stable id scheme as the scraper (so re-pasting updates rather
    than duplicates), and flags it `source="manual"`. With `tailor=True` it then
    reuses run_single_job for the scored tailor + cover letter and returns that
    result; with `tailor=False` it just adds the job (status "fetched") and
    returns the detected metadata, leaving the user to run the pipeline manually.
    Returns {"error": ...} if the page couldn't be read.
    """
    from src.tailor.engine import extract_job_meta

    scraper = JobScraper()
    description = scraper.extract_job_description(url)
    if not description or len(description.strip()) < 80:
        return {"error": "Couldn't read a job description from that link — the site "
                         "may block scraping. Try a direct posting URL."}

    meta = extract_job_meta(description)
    title = meta.get("title") or "Untitled role"
    company = meta.get("company") or "Unknown company"

    job_id = scraper._job_key(title, company)
    upsert_job({
        "id": job_id,
        "title": title,
        "company": company,
        "location": meta.get("location", ""),
        "url": url,
        "source": "manual",
        "description": description,
        "scraped_at": datetime.now().isoformat(),
        "status": "fetched",
    })

    if not tailor:
        return {"job_id": job_id, "title": title, "company": company, "status": "added"}

    result = run_single_job(job_id, template)
    result.update({"job_id": job_id, "title": title, "company": company})
    return result


def run_single_job(job_id: str, template: str = "default"):
    """Process a single job through the pipeline (fetch JD → tailor → cover letter)."""
    job = get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    scraper = JobScraper()

    # Fetch JD
    description = job.get("description", "")
    if not description and job.get("url"):
        description = scraper.extract_job_description(job["url"])
    if not description:
        description = f"Position: {job['title']} at {job['company']}."

    update_job(job_id, description=description, status="fetched")

    # Create application
    app_id = str(uuid.uuid4())[:8]
    create_application(app_id, job_id, template)

    # Tailor
    try:
        tailored, match_report = tailor_resume_scored(MASTER_RESUME, description, template)
    except Exception as e:
        update_application(app_id, status="error", error=str(e))
        return {"error": str(e), "app_id": app_id}

    # Cover letter
    try:
        cover = generate_cover_letter(MASTER_RESUME, description, job.get("company", ""))
    except Exception:
        cover = ""

    import json as _json
    update_application(
        app_id,
        tailored_resume=str(tailored) if tailored else None,
        cover_letter=cover,
        match_score=match_report["score"] if match_report else None,
        match_report=_json.dumps(match_report) if match_report else None,
        status="done",
        completed_at=datetime.now().isoformat(),
    )

    return {"app_id": app_id, "status": "done", "match_score": match_report["score"]}
