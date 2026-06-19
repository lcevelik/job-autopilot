"""Job Autopilot — Web Dashboard with Auto-Pipeline Backend."""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from src.db import (
    init_db, get_stats, get_jobs, get_job, update_job,
    get_applications, get_application, delete_application,
    get_pipeline_runs, get_setting, set_setting, get_all_settings,
)
from src.pipeline import run_pipeline, run_single_job, add_job_from_url
from src.generator.pdf_gen import generate_resume_pdf, generate_cover_letter_pdf

app = FastAPI(title="Job Autopilot", version="2.0.0")

BASE = Path(__file__).parent
DATA = BASE / "data"
MASTER = DATA / "master" / "resume.json"

# ── Pipeline state ────────────────────────────────────────────────────────────
_pipeline_running = False


# ── API: Stats ────────────────────────────────────────────────────────────────


@app.get("/api/stats")
def stats():
    s = get_stats()
    s["pipeline_running"] = _pipeline_running
    return s


# ── API: Master Resume ────────────────────────────────────────────────────────


@app.get("/api/resume")
def get_resume():
    if not MASTER.exists():
        raise HTTPException(404, "No master resume found")
    return json.loads(MASTER.read_text())


@app.put("/api/resume")
def update_resume(request: Request):
    data = asyncio.run(request.json())
    MASTER.write_text(json.dumps(data, indent=2))
    return {"ok": True, "updated": datetime.now().isoformat()}


# ── API: Jobs ─────────────────────────────────────────────────────────────────


@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 100):
    return get_jobs(status=status, limit=limit)


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404)
    return job


@app.put("/api/jobs/{job_id}")
def api_update_job(job_id: str, request: Request):
    data = asyncio.run(request.json())
    update_job(job_id, **data)
    return {"ok": True}


# ── API: Pipeline ─────────────────────────────────────────────────────────────


class PipelineRequest(BaseModel):
    keywords: Optional[str] = None
    location: Optional[str] = None
    template: Optional[str] = None
    sources: Optional[str] = None  # comma-separated list of sources


@app.post("/api/pipeline/run")
def api_run_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            run_pipeline(
                keywords=req.keywords,
                location=req.location,
                template=req.template,
                sources=req.sources,
            )
        finally:
            _pipeline_running = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Pipeline running in background"}


class UrlRequest(BaseModel):
    url: str
    template: Optional[str] = "default"


@app.post("/api/pipeline/run-url")
def api_run_url(req: UrlRequest, background_tasks: BackgroundTasks):
    """Tailor a resume from a single pasted job-posting URL."""
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(409, "Pipeline already running")
    if not req.url or not req.url.strip().lower().startswith("http"):
        raise HTTPException(400, "Provide a valid job posting URL (starting with http)")

    def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            res = add_job_from_url(req.url.strip(), req.template or "default")
            if res.get("error"):
                print(f"run-url failed: {res['error']}")
        finally:
            _pipeline_running = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Reading link and tailoring in background"}


@app.get("/api/pipeline/status")
def api_pipeline_status():
    runs = get_pipeline_runs(limit=1)
    return {
        "running": _pipeline_running,
        "last_run": runs[0] if runs else None,
    }


@app.get("/api/pipeline/runs")
def api_pipeline_runs(limit: int = 10):
    return get_pipeline_runs(limit=limit)


# ── API: Applications ────────────────────────────────────────────────────────


@app.get("/api/applications")
def list_applications(status: Optional[str] = None, limit: int = 100):
    return get_applications(status=status, limit=limit)


@app.get("/api/applications/{app_id}")
def api_get_application(app_id: str):
    app_data = get_application(app_id)
    if not app_data:
        raise HTTPException(404)
    return app_data


@app.delete("/api/applications/{app_id}")
def api_delete_application(app_id: str):
    delete_application(app_id)
    return {"ok": True}


@app.get("/api/applications/{app_id}/resume.pdf")
def api_download_resume_pdf(app_id: str):
    """Download tailored resume as PDF."""
    app_data = get_application(app_id)
    if not app_data:
        raise HTTPException(404)
    if not app_data.get("tailored_resume"):
        raise HTTPException(404, "No tailored resume available")

    try:
        resume_data = eval(app_data["tailored_resume"]) if isinstance(app_data["tailored_resume"], str) else app_data["tailored_resume"]
    except Exception:
        import json
        resume_data = json.loads(app_data["tailored_resume"])

    pdf_path = generate_resume_pdf(resume_data, app_id, app_data.get("job_title", ""), app_data.get("job_company", ""))
    return FileResponse(pdf_path, filename=os.path.basename(pdf_path), media_type="application/pdf")


@app.get("/api/applications/{app_id}/cover.pdf")
def api_download_cover_pdf(app_id: str):
    """Download cover letter as PDF."""
    app_data = get_application(app_id)
    if not app_data:
        raise HTTPException(404)
    if not app_data.get("cover_letter"):
        raise HTTPException(404, "No cover letter available")

    resume_data = {}
    if app_data.get("tailored_resume"):
        try:
            resume_data = eval(app_data["tailored_resume"]) if isinstance(app_data["tailored_resume"], str) else app_data["tailored_resume"]
        except Exception:
            import json
            resume_data = json.loads(app_data["tailored_resume"])

    personal = resume_data.get("personal", {})
    pdf_path = generate_cover_letter_pdf(
        app_data["cover_letter"],
        personal.get("name", ""),
        personal.get("email", ""),
        personal.get("phone", ""),
        personal.get("location", ""),
        app_id,
        app_data.get("job_title", ""),
        app_data.get("job_company", ""),
    )
    return FileResponse(pdf_path, filename=os.path.basename(pdf_path), media_type="application/pdf")


@app.post("/api/pipeline/regenerate")
def api_regenerate_all(background_tasks: BackgroundTasks):
    """Delete all existing applications and re-tailor from current master resume."""
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(409, "Pipeline already running")

    def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            from src.db import get_jobs, delete_application, db_conn, get_applications, update_job
            from src.pipeline import run_single_job, MASTER_RESUME
            from src.scraper.scraper import JobScraper

            # Clear all existing applications
            with db_conn() as conn:
                conn.execute("DELETE FROM applications")

            # First, fetch descriptions for all jobs that don't have them
            scraper = JobScraper()
            with db_conn() as conn:
                rows = conn.execute(
                    "SELECT id, title, company, url FROM jobs WHERE (description IS NULL OR description = '') AND status != 'error' AND status != 'filtered'"
                ).fetchall()

            if rows:
                print(f"Fetching descriptions for {len(rows)} jobs...")
                for r in rows:
                    job_id, title, company, url = r[0], r[1], r[2], r[3]
                    try:
                        desc = ""
                        if url and url != "":
                            desc = scraper.extract_job_description(url)
                        if not desc:
                            desc = f"Position: {title} at {company}."
                        update_job(job_id, description=desc, status="fetched")
                    except Exception as e:
                        print(f"  JD fetch failed for {job_id}: {e}")

            # Get all jobs that have a description (ready for tailoring)
            with db_conn() as conn:
                rows = conn.execute(
                    "SELECT id FROM jobs WHERE description IS NOT NULL AND description != '' AND status != 'error' AND status != 'filtered'"
                ).fetchall()
                job_ids = [r[0] for r in rows]

            print(f"Regenerating {len(job_ids)} applications...")
            template = get_setting("default_template", "default")
            for i, job_id in enumerate(job_ids):
                try:
                    print(f"  [{i+1}/{len(job_ids)}] {job_id}")
                    run_single_job(job_id, template)
                except Exception as e:
                    print(f"Failed to regenerate {job_id}: {e}")
        finally:
            _pipeline_running = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Regenerating all resumes with updated master"}


@app.post("/api/applications/{app_id}/process")
def api_process_single_job(app_id: str, background_tasks: BackgroundTasks, template: str = "default"):
    """Process a single job through the pipeline."""
    job = get_job(app_id)
    if not job:
        raise HTTPException(404, "Job not found")

    def _run():
        run_single_job(app_id, template)

    background_tasks.add_task(_run)
    return {"status": "started"}


# ── API: Settings ─────────────────────────────────────────────────────────────


@app.get("/api/settings")
def api_get_settings():
    return get_all_settings()


@app.put("/api/settings")
def api_update_settings(request: Request):
    data = asyncio.run(request.json())
    for key, value in data.items():
        set_setting(key, str(value))
    return {"ok": True}


# ── Frontend ─────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "static" / "index.html").read_text()


app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
