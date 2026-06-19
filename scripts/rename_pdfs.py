"""Re-render every application's PDFs from current DB content using the friendly
'<Name>_<Job Title>_<Company>.pdf' naming, then delete any leftover/orphan PDFs
so the data/applications folder contains exactly the current set.

No LLM calls — this only re-renders stored resume/cover content, so it's cheap
and safe to run any time the naming convention changes.

Usage:  venv/bin/python -m scripts.rename_pdfs
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import db_conn  # noqa: E402
from src.generator.pdf_gen import (  # noqa: E402
    generate_resume_pdf, generate_cover_letter_pdf, OUTPUT_DIR,
)


def main():
    written = set()
    with db_conn() as c:
        rows = c.execute(
            "SELECT a.id app_id, j.title, j.company, a.tailored_resume, a.cover_letter "
            "FROM applications a JOIN jobs j ON a.job_id=j.id "
            "WHERE a.tailored_resume IS NOT NULL"
        ).fetchall()

    for r in rows:
        try:
            tailored = ast.literal_eval(r["tailored_resume"])
        except Exception as e:
            print(f"  skip {r['app_id']}: unparseable tailored_resume ({e})")
            continue
        title, company = r["title"] or "", r["company"] or ""
        written.add(Path(generate_resume_pdf(tailored, r["app_id"], title, company)).name)
        if r["cover_letter"]:
            p = tailored.get("personal", {})
            cp = generate_cover_letter_pdf(
                r["cover_letter"], p.get("name", ""), p.get("email", ""),
                p.get("phone", ""), p.get("location", ""), r["app_id"], title, company,
            )
            written.add(Path(cp).name)

    removed = 0
    for f in OUTPUT_DIR.glob("*.pdf"):
        if f.name not in written:
            f.unlink()
            removed += 1

    print(f"regenerated {len(written)} PDFs with friendly names; removed {removed} old/orphan PDFs")


if __name__ == "__main__":
    main()
