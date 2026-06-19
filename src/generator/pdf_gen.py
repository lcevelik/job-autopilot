"""
Job Autopilot — PDF Generator

Professional ATS-friendly resume and cover letter PDFs.
Design: Corporate Deep Blue + Accent Amber, A4, WeasyPrint.
"""

import re
from pathlib import Path
from weasyprint import HTML

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "applications"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _slug(text: str, max_len: int = 60) -> str:
    """Turn arbitrary text into a safe filename fragment (underscores, no punctuation)."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", (text or "").strip()).strip("_")
    return s[:max_len].strip("_")


def _pdf_filename(name: str, job_title: str, app_id: str, company: str = "", suffix: str = "") -> str:
    """Build a human-readable PDF filename like
    'Libor_Cevelik_Senior_VFX_Artist_Tencent.pdf'.

    Falls back to the app_id when the job title and company are both missing, so a
    file is always produced. `suffix` distinguishes e.g. the cover letter.
    """
    name_slug = _slug(name) or "Resume"
    parts = [p for p in (_slug(job_title), _slug(company, 40)) if p]
    stem = f"{name_slug}_" + "_".join(parts) if parts else f"{name_slug}_{app_id}"
    if suffix:
        stem = f"{stem}_{suffix}"
    return f"{stem}.pdf"

# ── Resume CSS ────────────────────────────────────────────────────────────────

RESUME_CSS = """
@page {
    size: A4;
    margin: 14mm 12mm;
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #718096;
    }
}

* { box-sizing: border-box; }

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.4;
    color: #2d3748;
    margin: 0;
    padding: 0;
}

p, li { text-align: justify; }

/* ── Header Block ── */
.header { margin-bottom: 14px; padding-bottom: 10px; border-bottom: 2px solid #2b6cb0; }

.header h1 {
    font-size: 24pt;
    font-weight: 700;
    letter-spacing: -0.5px;
    text-transform: uppercase;
    color: #1a202c;
    margin: 0 0 2px;
}

.header .tagline {
    font-size: 11pt;
    font-weight: 700;
    text-transform: uppercase;
    color: #2b6cb0;
    margin: 0 0 6px;
}

.header .contact {
    font-size: 9pt;
    color: #4a5568;
    margin: 0;
}

.header .contact a { color: #4a5568; text-decoration: none; }

/* ── Section Headings ── */
h2 {
    font-size: 12pt;
    font-weight: 700;
    text-transform: uppercase;
    color: #2b6cb0;
    margin: 16px 0 6px;
    padding: 0 0 3px 6px;
    border-left: 4px solid #d69e2e;
    border-bottom: 1px solid #e2e8f0;
    page-break-after: avoid;
}

/* ── Skills Matrix Table ── */
.skills-table {
    width: 100%;
    border-collapse: collapse;
    margin: 4px 0 8px;
    font-size: 9pt;
}

.skills-table td {
    padding: 4px 8px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
}

.skills-table .cat {
    width: 25%;
    font-weight: 700;
    color: #2b6cb0;
    background: #f7fafc;
}

.skills-table .items { width: 75%; }

/* ── Experience Blocks ── */
.experience-block {
    margin-bottom: 10px;
    page-break-inside: auto;
}

.exp-title {
    font-size: 10pt;
    font-weight: 700;
    margin: 0;
    page-break-after: avoid;
}

.exp-title .company { float: left; }
.exp-title .dates { float: right; color: #718096; font-weight: 400; }

.exp-subtitle {
    font-size: 9pt;
    font-style: italic;
    color: #4a5568;
    margin: 1px 0 4px;
    clear: both;
}

.exp-subtitle .role { font-weight: 600; color: #2b6cb0; font-style: normal; }

ul { padding-left: 18px; margin: 2px 0 0; }
li { margin-bottom: 4px; font-size: 10pt; }

/* ── Summary ── */
.summary { margin-bottom: 8px; font-size: 10pt; }

/* ── Projects ── */
.project { margin-bottom: 6px; }
.project strong { font-size: 10pt; }
.project .desc { font-size: 9.5pt; color: #4a5568; }
"""

RESUME_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>

<div class="header">
    <h1>{name}</h1>
    <div class="tagline">{tagline}</div>
    <div class="contact">
        {phone} &middot; {email} &middot; {location}<br>
        {linkedin}{vimeo}{website}
    </div>
</div>

<h2>Professional Summary</h2>
<div class="summary">{summary}</div>

<h2>Experience</h2>
{experience}

<h2>Key Projects</h2>
{projects}

<h2>Skills</h2>
<table class="skills-table">
{skills_table}
</table>

<h2>Education</h2>
<ul>{education}</ul>

<h2>Certifications</h2>
<ul>{certifications}</ul>

</body></html>
"""

# ── Cover Letter CSS ──────────────────────────────────────────────────────────

COVER_CSS = """
@page {
    size: A4;
    margin: 25mm 20mm;
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 8pt;
        color: #718096;
    }
}

* { box-sizing: border-box; }

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #2d3748;
}

.header { margin-bottom: 24px; padding-bottom: 12px; border-bottom: 2px solid #2b6cb0; }

.header h1 {
    font-size: 20pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: -0.5px;
    color: #1a202c;
    margin: 0 0 2px;
}

.header .contact {
    font-size: 9pt;
    color: #4a5568;
}

.date { font-size: 10pt; color: #718096; margin-bottom: 16px; }
.greeting { margin-bottom: 12px; font-weight: 600; }
p { margin: 0 0 12px; text-align: justify; }
.signature { margin-top: 24px; }
.signature p { text-align: left; }
"""


COVER_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>

<div class="header">
    <h1>{name}</h1>
    <div class="contact">{email} &middot; {phone} &middot; {location}</div>
</div>

<div class="date">{date}</div>

<div class="greeting">Dear Hiring Manager,</div>

{paragraphs}

<div class="signature">
    <p>Sincerely,<br><strong>{name}</strong></p>
</div>

</body></html>
"""


# ── Generators ────────────────────────────────────────────────────────────────


def _get_tagline(resume: dict) -> str:
    """Extract a tagline from summary or generate one."""
    summary = resume.get("summary_templates", {}).get("default", "")
    if summary:
        # Take first sentence
        first = summary.split(".")[0].strip()
        if len(first) < 80:
            return first
        return first[:77] + "..."
    exp = resume.get("experience", [])
    if exp:
        return f"{exp[0].get('title', '')} — {exp[0].get('company', '')}"
    return ""


def _render_experience(experience: list) -> str:
    """Render experience section as HTML blocks."""
    html = ""
    for exp in experience:
        bullets = exp.get("bullets", {})
        bullet_list = bullets.get("default") or next(iter(bullets.values()), []) if bullets else []
        html += f"""
        <div class="experience-block">
            <div class="exp-title">
                <span class="company">{exp.get('company', '')}</span>
                <span class="dates">{exp.get('start', '')} — {exp.get('end', '')}</span>
            </div>
            <div class="exp-subtitle">
                <span class="role">{exp.get('title', '')}</span>
            </div>
            <ul>{''.join(f'<li>{b}</li>' for b in bullet_list)}</ul>
        </div>
        """
    return html


def _render_projects(projects: list) -> str:
    html = ""
    for p in projects:
        html += f'<div class="project"><strong>{p.get("title", "")}</strong><div class="desc">{p.get("description", "")}</div></div>'
    return html


def _render_skills_table(skills: dict) -> str:
    """Render skills as a structured table with categories."""
    categories = skills.get("categories", {})
    all_skills = skills.get("all", [])

    if not categories:
        # Fallback: put all skills in one row
        return f'<tr><td class="cat">Skills</td><td class="items">{", ".join(all_skills)}</td></tr>'

    rows = ""
    cat_labels = {
        "languages": "Languages",
        "frameworks": "Frameworks",
        "cloud": "Cloud & Infra",
        "ai_ml": "AI / ML",
        "tools": "Tools & Hardware",
    }

    for key, label in cat_labels.items():
        if key in categories and categories[key]:
            skills_text = ", ".join(categories[key])
            rows += f'<tr><td class="cat">{label}</td><td class="items">{skills_text}</td></tr>'

    # Add any uncategorized skills
    categorized = set()
    for v in categories.values():
        categorized.update(v)
    remaining = [s for s in all_skills if s not in categorized]
    if remaining:
        rows += f'<tr><td class="cat">Additional</td><td class="items">{", ".join(remaining)}</td></tr>'

    return rows


def generate_resume_pdf(tailored_resume: dict, app_id: str, job_title: str = "", company: str = "") -> str:
    """Generate ATS-friendly resume PDF. Returns path to the PDF.

    Filename is '<Name>_<Job Title>_<Company>.pdf'
    (e.g. Libor_Cevelik_Senior_VFX_Artist_Tencent.pdf).
    """
    personal = tailored_resume.get("personal", {})
    summary = tailored_resume.get("summary_templates", {}).get("default", "")
    experience = tailored_resume.get("experience", [])
    projects = tailored_resume.get("key_projects", [])
    skills = tailored_resume.get("skills", {})
    education = tailored_resume.get("education", [])
    certifications = tailored_resume.get("certifications", [])

    tagline = _get_tagline(tailored_resume)

    linkedin = ""
    if personal.get("linkedin"):
        linkedin = f'<a href="https://{personal["linkedin"]}">{personal["linkedin"]}</a>'
    vimeo = ""
    if personal.get("vimeo"):
        vimeo = f' &middot; <a href="https://{personal["vimeo"]}">{personal["vimeo"]}</a>'
    website = ""
    if personal.get("website"):
        website = f' &middot; <a href="https://{personal["website"]}">{personal["website"]}</a>'

    html = RESUME_TEMPLATE.format(
        css=RESUME_CSS,
        name=personal.get("name", ""),
        tagline=tagline,
        phone=personal.get("phone", ""),
        email=personal.get("email", ""),
        location=personal.get("location", ""),
        linkedin=linkedin,
        vimeo=vimeo,
        website=website,
        summary=summary,
        experience=_render_experience(experience),
        projects=_render_projects(projects),
        skills_table=_render_skills_table(skills),
        education="".join(f"<li>{e}</li>" for e in education),
        certifications="".join(f"<li>{c}</li>" for c in certifications),
    )

    out_path = str(OUTPUT_DIR / _pdf_filename(personal.get("name", ""), job_title, app_id, company))
    HTML(string=html).write_pdf(out_path)
    return out_path


def generate_cover_letter_pdf(cover_letter: str, name: str, email: str, phone: str, location: str, app_id: str, job_title: str = "", company: str = "") -> str:
    """Generate cover letter PDF. Returns path to the PDF.

    Filename is '<Name>_<Job Title>_<Company>_CoverLetter.pdf'.
    """
    from datetime import datetime

    paragraphs = ""
    for para in cover_letter.strip().split("\n\n"):
        para = para.strip()
        if para:
            paragraphs += f"<p>{para}</p>"

    html = COVER_TEMPLATE.format(
        css=COVER_CSS,
        name=name,
        email=email,
        phone=phone,
        location=location,
        date=datetime.now().strftime("%B %d, %Y"),
        paragraphs=paragraphs,
    )

    out_path = str(OUTPUT_DIR / _pdf_filename(name, job_title, app_id, company, suffix="CoverLetter"))
    HTML(string=html).write_pdf(out_path)
    return out_path


if __name__ == "__main__":
    import json

    sample = {
        "personal": {"name": "Libor Cevelik", "email": "libor.cevelik@gmail.com", "phone": "424.236.9069", "location": "Los Angeles, CA", "linkedin": "linkedin.com/in/liborcevelik", "website": "steadiczech.com"},
        "summary_templates": {"default": "VP/ICVFX specialist and full-stack engineer with deep expertise in real-time 3D, Gaussian splatting, AI integration, and infrastructure automation. Currently leading virtual production initiatives at Sony's DMPC lab."},
        "experience": [
            {"title": "Virtual Production Supervisor", "company": "Sony Electronics — DMPC", "start": "Apr 2023", "end": "Present", "bullets": {"default": ["Led VP operations on LED volume and nDisplay workflows", "Integrated AI/ML tools into production pipelines"]}},
            {"title": "Full-Stack AI Engineer", "company": "Self-Employed", "start": "Apr 2020", "end": "Present", "bullets": {"default": ["Built commercial Gaussian splatting service", "Developed FonixFlow AI transcription SaaS"]}}
        ],
        "key_projects": [{"title": "3DGS Gallery", "description": "React 19 + Three.js web project showcasing 17 splat scenes"}],
        "skills": {
            "all": ["Unreal Engine", "nDisplay", "Python", "AI/ML", "Gaussian Splatting"],
            "categories": {
                "languages": ["Python", "JavaScript", "TypeScript"],
                "frameworks": ["Unreal Engine 5", "FastAPI", "React"],
                "ai_ml": ["Ollama", "Gaussian Splatting", "ComfyUI"],
                "tools": ["Steadicam", "Ultimatte", "Sony Ocellus"]
            }
        },
        "education": ["BFA Multimedia Communications"],
        "certifications": ["Unreal Fellowship 2025"]
    }

    resume_path = generate_resume_pdf(sample, "test_resume")
    print(f"Resume PDF: {resume_path}")

    cover_path = generate_cover_letter_pdf(
        "Dear Hiring Manager,\n\nI am excited to apply for the Creative Technologist role at Google. With over 20 years of experience in virtual production and AI-driven workflows, I bring a unique blend of technical depth and creative vision.\n\nAt Sony's DMPC lab, I architect real-time compositing pipelines using nDisplay and LED volumes while integrating emerging AI tools like Gaussian splatting into production workflows.\n\nI would welcome the opportunity to discuss how my experience can contribute to Google's innovative projects.",
        "Libor Cevelik", "libor.cevelik@gmail.com", "424.236.9069", "Los Angeles, CA", "test_cover"
    )
    print(f"Cover PDF: {cover_path}")
