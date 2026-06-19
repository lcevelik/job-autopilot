"""Regenerate existing resumes in place with the scored/fidelity-checked system.

Operates on existing application rows (keeps the same app_id, so PDFs overwrite
cleanly with no orphans). Prints a before/after fabrication + match comparison.

Usage:
  venv/bin/python -m scripts.regen_resumes [N] [unscored]
    N         = how many to redo (default all)
    unscored  = only redo applications without a match_score (i.e. not yet redone
                with the scored/fidelity-checked system)
"""

import ast
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import db_conn, update_application, get_setting  # noqa: E402
from src.tailor.engine import (  # noqa: E402
    tailor_resume_scored, generate_cover_letter, _flatten_text, _keyword_covered,
)
from src.generator.pdf_gen import generate_resume_pdf, generate_cover_letter_pdf  # noqa: E402

MASTER = str(ROOT / "data" / "master" / "resume.json")


def _fab_count(tailored_repr, master_text):
    try:
        t = ast.literal_eval(tailored_repr)
    except Exception:
        return None
    skills = list(t.get("skills", {}).get("all", []))
    for cat in t.get("skills", {}).get("categories", {}).values():
        skills.extend(cat)
    return len({s for s in skills if s and not _keyword_covered(s, master_text)})


def main():
    args = sys.argv[1:]
    only_unscored = "unscored" in args
    nums = [int(a) for a in args if a.isdigit()]
    limit = nums[0] if nums else None
    template = get_setting("default_template", "default")
    master = json.load(open(MASTER))
    master_text = _flatten_text(master).lower()

    where = "WHERE j.description IS NOT NULL AND j.description != ''"
    if only_unscored:
        where += " AND a.match_score IS NULL"
    with db_conn() as c:
        q = (f"SELECT a.id app_id, j.company, j.title, j.description, a.tailored_resume "
             f"FROM applications a JOIN jobs j ON a.job_id=j.id "
             f"{where} ORDER BY a.created_at DESC")
        rows = c.execute(q).fetchall()
    if limit:
        rows = rows[:limit]

    print(f"Regenerating {len(rows)} resume(s)...\n")
    for i, r in enumerate(rows, 1):
        app_id = r["app_id"]
        old_fab = _fab_count(r["tailored_resume"], master_text)
        try:
            tailored, report = tailor_resume_scored(MASTER, r["description"], template)
            generate_resume_pdf(tailored, app_id, r["title"], r["company"])
            cover = ""
            try:
                cover = generate_cover_letter(MASTER, r["description"], r["company"] or "")
                p = tailored.get("personal", {})
                generate_cover_letter_pdf(cover, p.get("name", ""), p.get("email", ""),
                                          p.get("phone", ""), p.get("location", ""), app_id, r["title"], r["company"])
            except Exception as e:
                print(f"    cover letter failed: {e}")
            update_application(
                app_id,
                tailored_resume=str(tailored),
                cover_letter=cover,
                match_score=report["score"],
                match_report=json.dumps(report),
            )
            print(f"[{i}/{len(rows)}] {r['title'][:45]:45} @ {(r['company'] or '')[:20]:20}")
            print(f"    fabrications: {old_fab} -> {len(report['fabricated'])}    "
                  f"match score: {report['score']}  (must {report['must_coverage']})")
            if report["fabricated"]:
                print(f"    still flagged: {report['fabricated']}")
        except Exception as e:
            print(f"[{i}/{len(rows)}] {app_id}  FAILED: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
