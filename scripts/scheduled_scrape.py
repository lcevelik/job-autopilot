"""Headless scrape+tailor run for cron (every 3 days).

Runs the full pipeline using the saved settings. Cross-run dedup is handled by
the stable job id (title+company) in src/pipeline.py: jobs already in the DB are
upserted without resetting their status, so only genuinely NEW jobs get a new
resume. Existing jobs are not reprocessed and not duplicated.

Cron example (every 3 days at 06:00):
  0 6 */3 * * cd /media/server/Storage/www/job-autopilot && \
    venv/bin/python -m scripts.scheduled_scrape >> data/scrape.log 2>&1
"""

import sys
import fcntl
from datetime import datetime
from pathlib import Path

# Ensure imports work regardless of cron's cwd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import run_pipeline  # noqa: E402
from src.db import get_setting  # noqa: E402

# A pipeline run can take many hours on the local LLM. This advisory lock stops a
# second invocation (a manual trigger, or the next cron if one ever runs long) from
# overlapping the first — which double-tailors jobs and creates duplicate
# applications. The lock auto-releases when this process exits, so no stale locks.
LOCK_PATH = ROOT / "data" / ".scrape.lock"


def main():
    started = datetime.now().isoformat(timespec="seconds")
    print(f"\n=== scheduled scrape @ {started} ===")

    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another pipeline run is still in progress — skipping this cycle.")
        return

    if get_setting("auto_scrape_enabled", "true").lower() != "true":
        print("auto_scrape_enabled is off — skipping.")
        return

    result = run_pipeline()  # uses saved keywords/location/template/sources
    stats = result.get("stats", {})
    print(f"done: scraped(kept)={stats.get('scraped')} "
          f"tailored={stats.get('tailored')} "
          f"covers={stats.get('covers')} errors={stats.get('errors')}")


if __name__ == "__main__":
    main()
