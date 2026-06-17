import requests
from bs4 import BeautifulSoup
import json
import os
import re
from typing import List, Dict, Optional

class JobScraper:
    """Scrapes job listings from various boards."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def scrape_linkedin_jobs(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """
        Scrape LinkedIn public job listings (limited by anti-bot measures).
        For production, use LinkedIn API or a service like ProxyCrawl.
        """
        # Note: LinkedIn aggressively blocks scrapers. This is a basic template.
        # For real usage, consider using LinkedIn's official API or a job aggregator.
        url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"LinkedIn returned status {response.status_code}. Using mock data.")
                return self._get_mock_jobs(keywords)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            
            # LinkedIn's HTML structure changes frequently
            job_cards = soup.find_all('div', class_='base-card')
            
            for card in job_cards[:num_results]:
                title = card.find('h3', class_='base-search-card__title')
                company = card.find('h4', class_='base-search-card__subtitle')
                location = card.find('span', class_='job-search-card__location')
                link = card.find('a', class_='base-card__full-link')
                
                if title and company:
                    jobs.append({
                        'title': title.text.strip(),
                        'company': company.text.strip(),
                        'location': location.text.strip() if location else '',
                        'url': link['href'] if link else '',
                        'source': 'linkedin'
                    })
            
            return jobs if jobs else self._get_mock_jobs(keywords)
            
        except Exception as e:
            print(f"Error scraping LinkedIn: {e}. Using mock data.")
            return self._get_mock_jobs(keywords)
    
    def scrape_indeed_jobs(self, keywords: str, location: str = "Los Angeles", num_results: int = 10) -> List[Dict]:
        """Scrape Indeed job listings."""
        url = f"https://www.indeed.com/jobs?q={keywords}&l={location}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"Indeed returned status {response.status_code}. Using mock data.")
                return self._get_mock_jobs(keywords)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            jobs = []
            
            job_cards = soup.find_all('div', class_='job_seen_beacon')
            
            for card in job_cards[:num_results]:
                title = card.find('h2', class_='jobTitle')
                company = card.find('span', class_='companyName')
                location = card.find('div', class_='companyLocation')
                link = card.find('a', id=lambda x: x and 'job_' in str(x))
                
                if title and company:
                    jobs.append({
                        'title': title.text.strip(),
                        'company': company.text.strip(),
                        'location': location.text.strip() if location else '',
                        'url': f"https://www.indeed.com{link['href']}" if link else '',
                        'source': 'indeed'
                    })
            
            return jobs if jobs else self._get_mock_jobs(keywords)
            
        except Exception as e:
            print(f"Error scraping Indeed: {e}. Using mock data.")
            return self._get_mock_jobs(keywords)
    
    def _get_mock_jobs(self, keywords: str) -> List[Dict]:
        """Return mock job data for testing when scraping fails."""
        return [
            {
                'title': f'Senior {keywords.title()} Engineer',
                'company': 'TechCorp Industries',
                'location': 'Los Angeles, CA (Hybrid)',
                'url': 'https://example.com/job/1',
                'source': 'mock'
            },
            {
                'title': f'{keywords.title()} Supervisor',
                'company': 'Creative Studios Inc',
                'location': 'Remote',
                'url': 'https://example.com/job/2',
                'source': 'mock'
            },
            {
                'title': f'Lead {keywords.title()} Architect',
                'company': 'Innovation Labs',
                'location': 'Los Angeles, CA',
                'url': 'https://example.com/job/3',
                'source': 'mock'
            }
        ]
    
    def extract_job_description(self, url: str) -> str:
        """Extract full job description from a URL."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try common job description selectors
            selectors = [
                'div.jobsearch-JobComponent-description',
                'div.description__text',
                'div.job-description',
                'section.job-description',
                'div#jobDescriptionText'
            ]
            
            for selector in selectors:
                desc_div = soup.select_one(selector)
                if desc_div:
                    return desc_div.get_text(separator='\n', strip=True)
            
            # Fallback to main content
            main = soup.find('main') or soup.find('body')
            return main.get_text(separator='\n', strip=True)[:5000] if main else ""
            
        except Exception as e:
            print(f"Error extracting JD: {e}")
            return ""
    
    def save_jobs(self, jobs: List[Dict], filename: str = "scraped_jobs.json"):
        """Save scraped jobs to JSON file."""
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(jobs, f, indent=2)
        print(f"Saved {len(jobs)} jobs to {filename}")

if __name__ == "__main__":
    scraper = JobScraper()
    
    # Test with virtual production keywords
    print("Scraping LinkedIn for Virtual Production jobs...")
    linkedin_jobs = scraper.scrape_linkedin_jobs("virtual production", "Los Angeles", 5)
    
    print("\nScraping Indeed for Unreal Engine jobs...")
    indeed_jobs = scraper.scrape_indeed_jobs("unreal engine", "Los Angeles", 5)
    
    all_jobs = linkedin_jobs + indeed_jobs
    
    # Save results
    scraper.save_jobs(all_jobs, "data/jobs/scraped_jobs.json")
    
    print(f"\nFound {len(all_jobs)} total jobs")
    for job in all_jobs[:3]:
        print(f"- {job['title']} at {job['company']} ({job['source']})")
