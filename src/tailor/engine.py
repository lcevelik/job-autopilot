"""
Job Autopilot — Resume Tailor Engine

Takes master resume data + job description, produces a tailored resume.
"""

import json
from pathlib import Path

MASTER_DIR = Path(__file__).parent.parent.parent / "data" / "master"


def load_master_resume():
    """Load master resume data from JSON."""
    resume_path = MASTER_DIR / "resume.json"
    if not resume_path.exists():
        raise FileNotFoundError(f"Master resume not found: {resume_path}")
    with open(resume_path) as f:
        return json.load(f)


def load_preferences():
    """Load job preferences."""
    prefs_path = MASTER_DIR / "preferences.json"
    with open(prefs_path) as f:
        return json.load(f)


def analyze_job_description(jd_text: str, llm_client=None) -> dict:
    """
    Extract key requirements from a job description.
    
    Returns:
        {
            "title": str,
            "required_skills": [str],
            "preferred_skills": [str],
            "keywords": [str],
            "seniority": str,  # junior/mid/senior/lead/exec
            "tone": str,       # startup/corporate/technical
            "remote": bool,
            "salary_range": str
        }
    """
    # TODO: Implement LLM-based JD analysis
    pass


def tailor_resume(master_resume: dict, jd_analysis: dict) -> dict:
    """
    Generate a tailored resume based on job requirements.
    
    - Reorders skills to match JD priority
    - Selects most relevant experience bullets
    - Rewrites summary to mirror JD language
    - Injects ATS keywords naturally
    """
    # TODO: Implement AI-powered resume tailoring
    pass


def generate_cover_letter(master_resume: dict, jd_analysis: dict, company_research: dict = None) -> str:
    """
    Generate a tailored cover letter.
    
    - Paragraph 1: Hook + why this company
    - Paragraph 2: Relevant experience + achievements
    - Paragraph 3: Cultural fit + call to action
    """
    # TODO: Implement cover letter generation
    pass


if __name__ == "__main__":
    print("Job Autopilot — Resume Tailor Engine")
    print("Place your resume.json in data/master/ to get started.")
