"""
Job Autopilot — PDF Generator

Generates ATS-friendly resume and cover letter PDFs.
"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "applications"


def generate_resume_pdf(tailored_resume: dict, output_path: str = None) -> str:
    """
    Generate a clean, ATS-friendly resume PDF.
    
    Requirements:
    - Single column (ATS parsers can't read multi-column)
    - Standard fonts (Arial, Calibri, Times)
    - No tables, text boxes, or images
    - Clear section headers
    - Consistent formatting
    """
    # TODO: Implement PDF generation
    # Options:
    # 1. WeasyPrint (HTML → PDF)
    # 2. ReportLab (Python PDF library)
    # 3. Jinja2 HTML template + wkhtmltopdf
    pass


def generate_cover_letter_pdf(cover_letter: str, company: str, output_path: str = None) -> str:
    """Generate cover letter PDF."""
    # TODO: Implement cover letter PDF generation
    pass


if __name__ == "__main__":
    print("Job Autopilot — PDF Generator")
