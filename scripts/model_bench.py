"""Benchmark several models on the SAME job description so you can compare
quality/fidelity/speed before committing one as TAILOR_MODEL.

Runs the full scored+fidelity-checked tailor for each model, saves each output
to data/applications/_bench_<slug>.json for eyeballing, and prints a table.

No DB writes — this does not touch your real applications.

Usage:  venv/bin/python -m scripts.model_bench
"""

import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import tailor  # noqa: E402
from src.tailor import engine  # noqa: E402
from src.db import db_conn  # noqa: E402

MASTER = str(ROOT / "data" / "master" / "resume.json")
OUT = ROOT / "data" / "applications"

MODELS = [
    "google/gemini-2.5-flash-lite",   # current default (baseline)
    "xiaomi/mimo-v2.5-pro",
    "deepseek/deepseek-v4-pro",
    "qwen/qwen3.6-plus",
]


FIT_KEYWORDS = ("virtual production", "technical artist", "creative technolog",
                "unreal", "vfx", "real-time", "led volume", "gaussian")


def pick_job():
    """Pick a job the candidate actually fits (so the comparison reflects model
    quality, not a bad job match). Falls back to the longest description."""
    with db_conn() as c:
        rows = c.execute(
            "SELECT title, company, description FROM jobs "
            "WHERE description IS NOT NULL AND length(description) > 400 "
            "ORDER BY length(description) DESC"
        ).fetchall()
    for r in rows:
        if any(k in (r["title"] or "").lower() for k in FIT_KEYWORDS):
            return r
    return rows[0] if rows else None


def main():
    job = pick_job()
    print(f"Test job: {job['title']} @ {job['company']}  (JD {len(job['description'])} chars)\n")

    results = []
    for model in MODELS:
        engine.TAILOR_MODEL = model  # override for this run
        t0 = time.time()
        try:
            tailored, report = engine.tailor_resume_scored(MASTER, job["description"])
            secs = time.time() - t0
            slug = model.replace("/", "_").replace(".", "_")
            (OUT / f"_bench_{slug}.json").write_text(json.dumps(tailored, indent=2))
            results.append({
                "model": model, "ok": True, "secs": round(secs, 1),
                "score": report["score"], "must": report["must_coverage"],
                "fab": len(report["fabricated"]), "missing": len(report["missing"]),
            })
            print(f"OK   {model:32} {secs:5.1f}s  score {report['score']}  must {report['must_coverage']}  fab {len(report['fabricated'])}")
        except Exception as e:
            results.append({"model": model, "ok": False, "err": str(e)[:120]})
            print(f"FAIL {model:32} {str(e)[:90]}")

    print("\n=== SUMMARY ===")
    print(f"{'model':34}{'ok':>4}{'secs':>7}{'score':>7}{'must':>7}{'fab':>5}{'miss':>6}")
    for r in results:
        if r["ok"]:
            print(f"{r['model']:34}{'Y':>4}{r['secs']:>7}{r['score']:>7}{r['must']:>7}{r['fab']:>5}{r['missing']:>6}")
        else:
            print(f"{r['model']:34}{'N':>4}   {r['err']}")
    print("\nInspect actual output quality:  data/applications/_bench_*.json")


if __name__ == "__main__":
    main()
