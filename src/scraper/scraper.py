"""
Job Autopilot — Job Board Scraper

Scrapes job listings from LinkedIn, Indeed, BuiltIn, Wellfound.
"""

import json
from pathlib import Path
from datetime import datetime

JOBS_DIR = Path(__file__).parent.parent.parent / "data" / "jobs"


def scrape_linkedin(keywords: str, location: str, remote: bool = True) -> list:
    """
    Scrape LinkedIn job listings.
    
    Note: LinkedIn RSS is dead (404). Options:
    1. LinkedIn API (requires OAuth app approval)
    2. SerpAPI / RapidAPI LinkedIn endpoint
    3. Browser automation (Playwright)
    """
    # TODO: Implement LinkedIn scraping
    pass


def scrape_indeed(keywords: str, location: str) -> list:
    """Scrape Indeed job listings via their search page."""
    # TODO: Implement Indeed scraping
    pass


def scrape_builtin(keywords: str, location: str) -> list:
    """Scrape BuiltIn job listings."""
    # TODO: Implement BuiltIn scraping
    pass


def scrape_wellfound(keywords: str, location: str) -> list:
    """Scrape Wellfound (AngelList) job listings."""
    # TODO: Implement Wellfound scraping
    pass


def save_jobs(jobs: list, source: str):
    """Save scraped jobs to daily JSON file."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = JOBS_DIR / f"{source}_{date_str}.json"
    with open(output_file, "w") as f:
        json.dump(jobs, f, indent=2)
    return output_file


def load_todays_jobs() -> list:
    """Load all jobs scraped today."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    all_jobs = []
    for f in JOBS_DIR.glob(f"*_{date_str}.json"):
        with open(f) as fh:
            all_jobs.extend(json.load(fh))
    return all_jobs


if __name__ == "__main__":
    print("Job Autopilot — Job Board Scraper")
    print("Configure keywords and location in data/master/preferences.json")
