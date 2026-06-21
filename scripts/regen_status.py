"""Append a one-line regen progress snapshot to data/regen_progress.log.

Meant for cron (e.g. every 30 min) so you can check on a long re-tailor backfill
without an interactive session. "Re-tailored" = the stored resume carries the
current master's `awards` key, which only exists after a tailor against the new
master. Self-pathing so cron's cwd doesn't matter.
"""

import sys
import ast
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_applications  # noqa: E402

LOG = ROOT / "data" / "regen_progress.log"


def main():
    apps = get_applications(limit=5000)
    total = len(apps)
    done = 0
    for a in apps:
        tr = a.get("tailored_resume")
        if not tr:
            continue
        try:
            d = ast.literal_eval(tr) if isinstance(tr, str) else tr
            if d.get("awards"):
                done += 1
        except Exception:
            pass

    running = bool(subprocess.run(
        ["pgrep", "-f", "regen_resumes"], capture_output=True).stdout.strip())

    pct = round(done / total * 100) if total else 0
    state = "running" if running else "STOPPED"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] regen {state}: {done}/{total} re-tailored ({pct}%)\n"
    with open(LOG, "a") as f:
        f.write(line)
    print(line, end="")


if __name__ == "__main__":
    main()
