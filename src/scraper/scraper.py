"""
Job Autopilot — Multi-Source Job Scraper

Scrapes from: LinkedIn, Indeed, Google Jobs (SerpAPI), Glassdoor,
ZipRecruiter, Built In, We Work Remotely, RemoteOK, Hired.

Features:
- Deduplication against DB (never re-scrape same title+company)
- Target company priority scoring
- JD extraction with fallback selectors
"""

import requests
import hashlib
import json
import os
import re
import time
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from src.db import get_jobs


class JobScraper:
    """Multi-source job scraper with dedup and company targeting."""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.timeout = 8  # 8 second timeout per request
        # Load target companies from settings
        self.target_companies = self._load_target_companies()

    def _load_target_companies(self) -> List[str]:
        """Load target companies from DB settings."""
        try:
            from src.db import get_setting
            raw = get_setting("target_companies", "")
            if raw:
                return [c.strip().lower() for c in raw.split(",") if c.strip()]
        except Exception:
            pass
        return []

    def _job_key(self, title: str, company: str) -> str:
        """Generate dedup key from title + company."""
        normalized = f"{title.lower().strip()}|{company.lower().strip()}"
        return hashlib.md5(normalized.encode()).hexdigest()

    def _location_score(self, location: str) -> int:
        """Score location preference. LA > USA > Remote > Worldwide."""
        if not location:
            return 50
        loc = location.lower()
        if "los angeles" in loc or "la," in loc or "la " in loc:
            return 100
        if "california" in loc or "ca," in loc:
            return 90
        if any(s in loc for s in ["usa", "united states", "u.s.", "remote"]):
            return 80
        if any(s in loc for s in ["new york", "san francisco", "sf", "seattle", "austin", "boston", "chicago"]):
            return 75
        if "remote" in loc:
            return 70
        return 50  # International

    def _is_duplicate(self, title: str, company: str, seen_keys: set) -> bool:
        """Check if job already exists in DB or current batch."""
        key = self._job_key(title, company)
        if key in seen_keys:
            return True
        # Check DB
        existing = get_jobs(limit=500)
        for j in existing:
            if self._job_key(j.get("title", ""), j.get("company", "")) == key:
                return True
        return False

    def _company_score(self, company: str) -> int:
        """Score job by target company match. Higher = more relevant."""
        if not self.target_companies:
            return 0
        company_lower = company.lower()
        for i, target in enumerate(self.target_companies):
            if target in company_lower or company_lower in target:
                return 100 - i  # Earlier in list = higher score
        return 0

    def _make_job(self, title: str, company: str, location: str, url: str, source: str) -> Dict:
        """Create a job dict with dedup key, company score, and location score."""
        # Skip mock/fake data
        if source == "mock" or "example.com" in (url or "").lower():
            return None
        
        # Skip garbage/irrelevant titles
        title_lower = title.lower().strip()
        if not title_lower or len(title_lower) < 5:
            return None
        
        # Reject career page text, admin roles, etc.
        garbage = [
            'explore open', 'sign in', 'join our', 'stay in', 'widget title',
            'no results', 'job search', 'recommended', 'saved jobs', 'job alerts',
            'career areas', 'business support', 'administration', 'asset management',
            'human resources', 'legal and', 'project management', 'visit the',
            'explore open', 'building', 'principles that', 'act for the',
            'hold light', 'be good', 'ignite a race', 'do the simple',
            'be helpful', 'put the mission', 'join us', 'refine by',
            'location00', 'keyword00', 'teams00', 'products and services00',
            'language skills00', 'search results', 'title card', 'careers at',
            'everything you need', 'we are building', '55 open roles',
            'life at', 'work at', 'see open roles', 'freelance recording',
            'executive assistant', 'administrative assistant',
        ]
        if any(g in title_lower for g in garbage):
            return None
        
        # Reject intern/junior/associate/coordinator roles
        skip_levels = ['intern', 'internship', 'coordinator', 'administrative',
                       'assistant', 'junior', 'associate level', 'entry level',
                       'cath lab', 'ultrasound', 'echocardiogram', 'cardiac',
                       'vascular', 'special procedures', 'medical claims']
        if any(s in title_lower for s in skip_levels):
            # But keep if it has strong relevant keywords
            strong = ['vfx', 'ai ', 'creative technologist', 'pipeline', 'unreal',
                     'machine learning', 'real-time', 'lighting', 'technical artist']
            if not any(k in title_lower for k in strong):
                return None
        
        return {
            "title": title.strip(),
            "company": company.strip(),
            "location": location.strip() if location else "",
            "url": url.strip() if url else "",
            "source": source,
            "company_score": self._company_score(company),
            "location_score": self._location_score(location),
        }

    # ── LinkedIn ──────────────────────────────────────────────────────────────

    def scrape_linkedin_jobs(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape LinkedIn public job listings."""
        url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(keywords)}&location={quote_plus(location)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  LinkedIn: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            job_cards = soup.find_all('div', class_='base-card')

            for card in job_cards[:num_results]:
                title = card.find('h3', class_='base-search-card__title')
                company = card.find('h4', class_='base-search-card__subtitle')
                loc = card.find('span', class_='job-search-card__location')
                link = card.find('a', class_='base-card__full-link')

                if title and company:
                    jobs.append(self._make_job(
                        title.text, company.text,
                        loc.text if loc else "",
                        link['href'] if link else "",
                        "linkedin"
                    ))
            return jobs
        except Exception as e:
            print(f"  LinkedIn error: {e}")
            return []

    # ── Indeed ────────────────────────────────────────────────────────────────

    def scrape_indeed_jobs(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Indeed job listings."""
        url = f"https://www.indeed.com/jobs?q={quote_plus(keywords)}&l={quote_plus(location)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  Indeed: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            job_cards = soup.find_all('div', class_='job_seen_beacon')

            for card in job_cards[:num_results]:
                title = card.find('h2', class_='jobTitle')
                company = card.find('span', class_='companyName')
                loc = card.find('div', class_='companyLocation')
                link = card.find('a', id=lambda x: x and 'job_' in str(x))

                if title and company:
                    jobs.append(self._make_job(
                        title.text, company.text,
                        loc.text if loc else "",
                        f"https://www.indeed.com{link['href']}" if link else "",
                        "indeed"
                    ))
            return jobs
        except Exception as e:
            print(f"  Indeed error: {e}")
            return []

    # ── Google Jobs (via SerpAPI) ─────────────────────────────────────────────

    def scrape_google_jobs(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Google Jobs via SerpAPI. Requires SERPAPI_KEY env var."""
        api_key = os.getenv("SERPAPI_KEY", "")
        if not api_key:
            print("  Google Jobs: No SERPAPI_KEY set, skipping")
            return []

        try:
            params = {
                "engine": "google_jobs",
                "q": keywords,
                "location": location,
                "api_key": api_key,
                "num": num_results,
            }
            response = requests.get("https://serpapi.com/search", params=params, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  Google Jobs: HTTP {response.status_code}")
                return []

            data = response.json()
            jobs = []
            for item in data.get("jobs_results", [])[:num_results]:
                jobs.append(self._make_job(
                    item.get("title", ""),
                    item.get("company_name", ""),
                    item.get("location", ""),
                    item.get("share_link", item.get("related_links", [{}])[0].get("link", "") if item.get("related_links") else ""),
                    "google"
                ))
            return jobs
        except Exception as e:
            print(f"  Google Jobs error: {e}")
            return []

    # ── Glassdoor ─────────────────────────────────────────────────────────────

    def scrape_glassdoor(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Glassdoor job listings."""
        url = f"https://www.glassdoor.com/Job/{quote_plus(location)}-{quote_plus(keywords)}-jobs-SRCH_IL.0,9_IS11746_KO10,28.htm"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  Glassdoor: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            # Glassdoor uses various selectors
            cards = soup.select('[data-test="jobListing"]') or soup.select('.jobListing') or soup.select('[class*="JobCard"]')

            for card in cards[:num_results]:
                title_el = card.select_one('[data-test="job-title"]') or card.select_one('a[data-test="job-title"]') or card.select_one('h2') or card.select_one('a')
                company_el = card.select_one('[data-test="employer-short-name"]') or card.select_one('.employerShortName')
                loc_el = card.select_one('[data-test="emp-location"]') or card.select_one('.loc')
                link_el = card.select_one('a[href*="/job-listing/"]') or card.select_one('a[href*="/job/"]')

                if title_el:
                    title_text = title_el.get_text(strip=True)
                    company_text = company_el.get_text(strip=True) if company_el else ""
                    loc_text = loc_el.get_text(strip=True) if loc_el else ""
                    link = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        link = href if href.startswith("http") else f"https://www.glassdoor.com{href}"

                    if title_text:
                        jobs.append(self._make_job(title_text, company_text, loc_text, link, "glassdoor"))
            return jobs
        except Exception as e:
            print(f"  Glassdoor error: {e}")
            return []

    # ── ZipRecruiter ──────────────────────────────────────────────────────────

    def scrape_ziprecruiter(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape ZipRecruiter job listings."""
        url = f"https://www.ziprecruiter.com/jobs-search?search={quote_plus(keywords)}&location={quote_plus(location)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  ZipRecruiter: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            cards = soup.select('article.job_result') or soup.select('[data-testid="job-card"]') or soup.select('.job_content')

            for card in cards[:num_results]:
                title_el = card.select_one('h2') or card.select_one('a.job_link')
                company_el = card.select_one('.company_name') or card.select_one('[data-testid="company-name"]')
                loc_el = card.select_one('.location') or card.select_one('[data-testid="job-location"]')
                link_el = card.select_one('a[href*="/job/"]') or card.select_one('a.job_link')

                if title_el:
                    title_text = title_el.get_text(strip=True)
                    company_text = company_el.get_text(strip=True) if company_el else ""
                    loc_text = loc_el.get_text(strip=True) if loc_el else ""
                    link = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        link = href if href.startswith("http") else f"https://www.ziprecruiter.com{href}"

                    if title_text:
                        jobs.append(self._make_job(title_text, company_text, loc_text, link, "ziprecruiter"))
            return jobs
        except Exception as e:
            print(f"  ZipRecruiter error: {e}")
            return []

    # ── Built In ──────────────────────────────────────────────────────────────

    def scrape_built_in(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Built In (great for tech companies)."""
        # Built In uses city-specific URLs
        city_map = {
            "los angeles": "los-angeles",
            "new york": "nyc",
            "san francisco": "sf-bay-area",
            "remote": "remote",
        }
        city = city_map.get(location.lower(), location.lower().replace(" ", "-"))
        url = f"https://builtin.com/jobs/{city}?search={quote_plus(keywords)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  Built In: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            cards = soup.select('[class*="job-card"]') or soup.select('[class*="JobCard"]') or soup.select('article')

            for card in cards[:num_results]:
                title_el = card.select_one('h3') or card.select_one('a[class*="title"]')
                company_el = card.select_one('[class*="company"]') or card.select_one('a[class*="company"]')
                loc_el = card.select_one('[class*="location"]')
                link_el = card.select_one('a[href*="/job/"]')

                if title_el:
                    title_text = title_el.get_text(strip=True)
                    company_text = company_el.get_text(strip=True) if company_el else ""
                    loc_text = loc_el.get_text(strip=True) if loc_el else location
                    link = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        link = href if href.startswith("http") else f"https://builtin.com{href}"

                    if title_text:
                        jobs.append(self._make_job(title_text, company_text, loc_text, link, "builtin"))
            return jobs
        except Exception as e:
            print(f"  Built In error: {e}")
            return []

    # ── We Work Remotely ─────────────────────────────────────────────────────

    def scrape_weworkremotely(self, keywords: str, location: str = "Remote", num_results: int = 10) -> List[Dict]:
        """Scrape We Work Remotely."""
        url = f"https://weworkremotely.com/remote-jobs/search?term={quote_plus(keywords)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  We Work Remotely: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            cards = soup.select('section.jobs li') or soup.select('[class*="job"]')

            for card in cards[:num_results]:
                title_el = card.select_one('h2') or card.select_one('a')
                company_el = card.select_one('span.company') or card.select_one('[class*="company"]')
                link_el = card.select_one('a[href*="/remote-jobs/"]') or card.select_one('a')

                if title_el:
                    title_text = title_el.get_text(strip=True)
                    company_text = company_el.get_text(strip=True) if company_el else ""
                    link = ""
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        link = href if href.startswith("http") else f"https://weworkremotely.com{href}"

                    if title_text:
                        jobs.append(self._make_job(title_text, company_text, "Remote", link, "weworkremotely"))
            return jobs
        except Exception as e:
            print(f"  We Work Remotely error: {e}")
            return []

    # ── RemoteOK ──────────────────────────────────────────────────────────────

    def scrape_remoteok(self, keywords: str, location: str = "Remote", num_results: int = 10) -> List[Dict]:
        """Scrape RemoteOK via their JSON API."""
        try:
            response = requests.get("https://remoteok.com/api", headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  RemoteOK: HTTP {response.status_code}")
                return []

            data = response.json()
            jobs = []
            # First item is metadata
            for item in data[1:]:  # Skip first metadata item
                title = item.get("position", "")
                company = item.get("company", "")
                tags = " ".join(item.get("tags", [])).lower()

                # Filter by keywords
                kw_lower = keywords.lower()
                if kw_lower in title.lower() or kw_lower in tags or any(k in title.lower() for k in kw_lower.split()):
                    jobs.append(self._make_job(
                        title, company,
                        item.get("location", "Remote"),
                        item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id', '')}"),
                        "remoteok"
                    ))
                if len(jobs) >= num_results:
                    break
            return jobs
        except Exception as e:
            print(f"  RemoteOK error: {e}")
            return []

    # ── Hired ─────────────────────────────────────────────────────────────────

    def scrape_hired(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Hired job listings."""
        url = f"https://hired.com/jobs?q={quote_plus(keywords)}&l={quote_plus(location)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                print(f"  Hired: HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            cards = soup.select('[class*="job-card"]') or soup.select('[class*="JobListing"]')

            for card in cards[:num_results]:
                title_el = card.select_one('h2') or card.select_one('a')
                company_el = card.select_one('[class*="company"]')
                loc_el = card.select_one('[class*="location"]')

                if title_el:
                    title_text = title_el.get_text(strip=True)
                    company_text = company_el.get_text(strip=True) if company_el else ""
                    loc_text = loc_el.get_text(strip=True) if loc_el else location

                    if title_text:
                        jobs.append(self._make_job(title_text, company_text, loc_text, url, "hired"))
            return jobs
        except Exception as e:
            print(f"  Hired error: {e}")
            return []

    # ── Target Company Search ─────────────────────────────────────────────────

    def scrape_target_companies(self, keywords: str, num_results: int = 5) -> List[Dict]:
        """Search target companies' career pages directly."""
        company_careers = {
            "google": "https://www.google.com/about/careers/applications/jobs/results/?q={kw}",
            "disney": "https://jobs.disney.com/search/?q={kw}",
            "anthropic": "https://www.anthropic.com/careers#open-positions",
            "sony": "https://jobs.sony.com/search/?q={kw}",
            "nvidia": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q={kw}",
            "epic games": "https://www.epicgames.com/site/en-US/careers/jobs?keywords={kw}",
            "netflix": "https://jobs.netflix.com/search?q={kw}",
            "adobe": "https://careers.adobe.com/us/en/search-results?keywords={kw}",
            "runway": "https://runwayml.com/careers/",
            "luma ai": "https://lumalabs.ai/careers",
            "apple": "https://jobs.apple.com/en-us/search?search={kw}",
            "meta": "https://www.metacareers.com/jobs?q={kw}",
        }

        jobs = []
        for company, url_template in company_careers.items():
            # Only search if company is in target list or keywords match
            if self.target_companies and not any(t in company for t in self.target_companies):
                continue

            url = url_template.format(kw=quote_plus(keywords))
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')

                # Generic extraction - look for job-like elements
                title_els = soup.select('a[href*="job"], a[href*="career"], h3, h2')
                for el in title_els[:num_results]:
                    title_text = el.get_text(strip=True)
                    if title_text and len(title_text) > 5 and len(title_text) < 100:
                        link = el.get("href", "")
                        if link and not link.startswith("http"):
                            link = f"https://{company.replace(' ', '')}.com{link}"
                        jobs.append(self._make_job(title_text, company.title(), "", link, f"careers:{company}"))
            except Exception:
                continue
            time.sleep(0.5)  # Rate limit

        return jobs

    # ── JD Extraction ─────────────────────────────────────────────────────────

    def extract_job_description(self, url: str) -> str:
        """Extract full job description from a URL."""
        if not url or "example.com" in url:
            return ""
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.content, 'html.parser')

            selectors = [
                'div.jobsearch-JobComponent-description',
                'div.description__text',
                'div.job-description',
                'section.job-description',
                'div#jobDescriptionText',
                '[class*="description"]',
                'article',
                'main',
            ]

            for selector in selectors:
                desc_div = soup.select_one(selector)
                if desc_div:
                    text = desc_div.get_text(separator='\n', strip=True)
                    if len(text) > 100:
                        return text[:5000]

            main = soup.find('body')
            return main.get_text(separator='\n', strip=True)[:3000] if main else ""
        except Exception as e:
            print(f"  JD extraction error: {e}")
            return ""

    # ── Main Scrape Method ────────────────────────────────────────────────────

    def scrape_all(self, keywords: str, location: str = "Los Angeles",
                   sources: List[str] = None, num_per_source: int = 10) -> List[Dict]:
        """
        Scrape all sources, deduplicate, and sort by company score.
        Sources: linkedin, indeed, google, glassdoor, ziprecruiter,
                 builtin, weworkremotely, remoteok, hired, targets
        """
        if sources is None:
            sources = ["linkedin", "indeed", "remoteok", "builtin"]

        all_jobs = []
        seen_keys = set()

        source_map = {
            "linkedin": lambda: self.scrape_linkedin_jobs(keywords, location, num_per_source),
            "indeed": lambda: self.scrape_indeed_jobs(keywords, location, num_per_source),
            "google": lambda: self.scrape_google_jobs(keywords, location, num_per_source),
            "glassdoor": lambda: self.scrape_glassdoor(keywords, location, num_per_source),
            "ziprecruiter": lambda: self.scrape_ziprecruiter(keywords, location, num_per_source),
            "builtin": lambda: self.scrape_built_in(keywords, location, num_per_source),
            "weworkremotely": lambda: self.scrape_weworkremotely(keywords, location, num_per_source),
            "remoteok": lambda: self.scrape_remoteok(keywords, location, num_per_source),
            "hired": lambda: self.scrape_hired(keywords, location, num_per_source),
            "targets": lambda: self.scrape_target_companies(keywords, num_per_source),
        }

        for source in sources:
            if source in source_map:
                print(f"  Scraping {source}...")
                try:
                    jobs = source_map[source]()
                    for job in jobs:
                        key = self._job_key(job["title"], job["company"])
                        if not self._is_duplicate(job["title"], job["company"], seen_keys):
                            seen_keys.add(key)
                            all_jobs.append(job)
                except Exception as e:
                    print(f"  {source} failed: {e}")

        # Also search with "Remote" keyword if location includes it
        if "remote" in location.lower():
            for source in ["linkedin", "remoteok", "weworkremotely"]:
                if source in [s for s in sources]:
                    print(f"  Scraping {source} (remote)...")
                    try:
                        remote_fn = source_map.get(source)
                        if remote_fn:
                            jobs = remote_fn()
                            for job in jobs:
                                job["location"] = "Remote"
                                key = self._job_key(job["title"], job["company"])
                                if not self._is_duplicate(job["title"], job["company"], seen_keys):
                                    seen_keys.add(key)
                                    all_jobs.append(job)
                    except Exception:
                        pass

        # Also search "Worldwide" / international if location includes it
        if "worldwide" in location.lower() or "international" in location.lower():
            for source in ["linkedin", "indeed"]:
                if source in [s for s in sources]:
                    print(f"  Scraping {source} (worldwide)...")
                    try:
                        remote_fn = source_map.get(source)
                        if remote_fn:
                            jobs = remote_fn()
                            for job in jobs:
                                key = self._job_key(job["title"], job["company"])
                                if not self._is_duplicate(job["title"], job["company"], seen_keys):
                                    seen_keys.add(key)
                                    all_jobs.append(job)
                    except Exception:
                        pass

        # Sort: target company first, then location preference (LA/USA/Remote), then source reliability
        source_priority = {"google": 5, "linkedin": 4, "builtin": 3, "indeed": 2, "glassdoor": 2,
                          "ziprecruiter": 2, "hired": 2, "remoteok": 1, "weworkremotely": 1}
        
        # Filter out None values from rejected jobs
        all_jobs = [j for j in all_jobs if j is not None]
        
        all_jobs.sort(key=lambda j: (
            -j.get("company_score", 0),
            -j.get("location_score", 0),
            -source_priority.get(j["source"], 0),
        ))

        print(f"  Total unique jobs: {len(all_jobs)}")
        return all_jobs


# Need BeautifulSoup import at module level
from bs4 import BeautifulSoup


if __name__ == "__main__":
    scraper = JobScraper()
    print("Testing multi-source scrape...")
    jobs = scraper.scrape_all("virtual production", "Los Angeles",
                              sources=["linkedin", "indeed", "remoteok"])
    for j in jobs[:5]:
        score = j.get("company_score", 0)
        print(f"  [{j['source']}] {j['title']} at {j['company']} (score: {score})")
