"""SQLite database for Job Autopilot — jobs, applications, pipeline runs."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "job_autopilot.db"


def get_db():
    """Get a database connection with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_conn():
    """Context manager for database connections."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                url TEXT,
                source TEXT,
                description TEXT,
                scraped_at TEXT NOT NULL,
                status TEXT DEFAULT 'new'
            );

            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                job_id TEXT REFERENCES jobs(id),
                template TEXT DEFAULT 'default',
                tailored_resume TEXT,
                cover_letter TEXT,
                status TEXT DEFAULT 'pending',
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'running',
                jobs_scraped INTEGER DEFAULT 0,
                jobs_fetched INTEGER DEFAULT 0,
                resumes_tailored INTEGER DEFAULT 0,
                cover_letters_generated INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                log TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        # Migrations: add columns that may not exist on older databases
        existing_cols = {r["name"] for r in conn.execute("PRAGMA table_info(applications)")}
        if "match_score" not in existing_cols:
            conn.execute("ALTER TABLE applications ADD COLUMN match_score REAL")
        if "match_report" not in existing_cols:
            conn.execute("ALTER TABLE applications ADD COLUMN match_report TEXT")

        # Insert default settings if not present
        defaults = {
            "search_keywords": "virtual production,unreal engine,LED volume,VP supervisor",
            "search_location": "Los Angeles",
            "auto_scrape_enabled": "true",
            "scrape_interval_minutes": "60",
            "default_template": "default",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


# ── Jobs ──────────────────────────────────────────────────────────────────────


def upsert_job(job: dict):
    """Insert or update a job."""
    with db_conn() as conn:
        conn.execute(
            """INSERT INTO jobs (id, title, company, location, url, source, description, scraped_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   title=excluded.title, company=excluded.company, location=excluded.location,
                   url=excluded.url, source=excluded.source, description=COALESCE(excluded.description, jobs.description)""",
            (
                job["id"],
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("url", ""),
                job.get("source", ""),
                job.get("description"),
                job.get("scraped_at", datetime.now().isoformat()),
                job.get("status", "new"),
            ),
        )


def get_jobs(status=None, limit=100):
    """Get jobs, optionally filtered by status."""
    with db_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY scraped_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY scraped_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_job(job_id):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job(job_id, **kwargs):
    with db_conn() as conn:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [job_id]
        conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", vals)


# ── Applications ──────────────────────────────────────────────────────────────


def create_application(app_id, job_id, template="default"):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO applications (id, job_id, template, status, created_at) VALUES (?, ?, ?, 'processing', ?)",
            (app_id, job_id, template, datetime.now().isoformat()),
        )


def update_application(app_id, **kwargs):
    with db_conn() as conn:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [app_id]
        conn.execute(f"UPDATE applications SET {sets} WHERE id=?", vals)


def get_applications(status=None, limit=100):
    with db_conn() as conn:
        if status:
            rows = conn.execute(
                """SELECT a.*, j.title as job_title, j.company as job_company,
                          j.location as job_location, j.url as job_url, j.source as job_source
                   FROM applications a JOIN jobs j ON a.job_id = j.id
                   WHERE a.status=? ORDER BY a.created_at DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT a.*, j.title as job_title, j.company as job_company,
                          j.location as job_location, j.url as job_url, j.source as job_source
                   FROM applications a JOIN jobs j ON a.job_id = j.id
                   ORDER BY a.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_application(app_id):
    with db_conn() as conn:
        row = conn.execute(
            """SELECT a.*, j.title as job_title, j.company as job_company,
                      j.location as job_location, j.url as job_url, j.source as job_source
               FROM applications a JOIN jobs j ON a.job_id = j.id WHERE a.id=?""",
            (app_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_application(app_id):
    with db_conn() as conn:
        conn.execute("DELETE FROM applications WHERE id=?", (app_id,))


# ── Pipeline Runs ─────────────────────────────────────────────────────────────


def create_pipeline_run():
    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (started_at, status) VALUES (?, 'running')",
            (datetime.now().isoformat(),),
        )
        return cur.lastrowid


def update_pipeline_run(run_id, **kwargs):
    with db_conn() as conn:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [run_id]
        conn.execute(f"UPDATE pipeline_runs SET {sets} WHERE id=?", vals)


def get_pipeline_runs(limit=10):
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Settings ──────────────────────────────────────────────────────────────────


def get_setting(key, default=None):
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def get_all_settings():
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Stats ─────────────────────────────────────────────────────────────────────


def get_stats():
    with db_conn() as conn:
        return {
            "jobs_total": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "jobs_new": conn.execute("SELECT COUNT(*) FROM jobs WHERE status='new'").fetchone()[0],
            "jobs_processing": conn.execute("SELECT COUNT(*) FROM jobs WHERE status='processing'").fetchone()[0],
            "apps_total": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "apps_processing": conn.execute("SELECT COUNT(*) FROM applications WHERE status='processing'").fetchone()[0],
            "apps_done": conn.execute("SELECT COUNT(*) FROM applications WHERE status='done'").fetchone()[0],
            "apps_error": conn.execute("SELECT COUNT(*) FROM applications WHERE status='error'").fetchone()[0],
            "pipeline_runs": conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0],
            "resume_loaded": os.path.exists(Path(__file__).parent.parent / "data" / "master" / "resume.json"),
        }


# Initialize on import
init_db()
