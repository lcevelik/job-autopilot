"""One-time migration: re-key existing jobs from random UUIDs to the stable
title+company key, so future scrapes dedupe against them instead of creating
duplicate rows (and duplicate resumes).

Safe to run more than once — jobs already on a stable key are skipped.
"""

import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DB_PATH  # noqa: E402
from src.scraper.scraper import JobScraper  # noqa: E402


def main():
    scraper = JobScraper()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=OFF")  # we update PK + child FK together

    jobs = conn.execute("SELECT id, title, company FROM jobs").fetchall()
    existing_ids = {j["id"] for j in jobs}

    rekeyed = skipped = collisions = 0
    for j in jobs:
        new_id = scraper._job_key(j["title"], j["company"])
        if new_id == j["id"]:
            skipped += 1
            continue
        if new_id in existing_ids and new_id != j["id"]:
            # Another job already owns the stable key — true duplicate. Leave it
            # for manual review rather than silently merging.
            print(f"  COLLISION: '{j['title']}' @ {j['company']} -> {new_id} already exists; skipping")
            collisions += 1
            continue
        conn.execute("UPDATE applications SET job_id=? WHERE job_id=?", (new_id, j["id"]))
        conn.execute("UPDATE jobs SET id=? WHERE id=?", (new_id, j["id"]))
        existing_ids.discard(j["id"])
        existing_ids.add(new_id)
        rekeyed += 1

    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()
    print(f"re-keyed: {rekeyed}  already-stable: {skipped}  collisions: {collisions}")


if __name__ == "__main__":
    main()
