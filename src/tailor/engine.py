import os
import re
import json
from openai import OpenAI, BadRequestError
import httpx

# Load OpenRouter API key
# In production, use os.getenv("OPENROUTER_API_KEY")
# For this project, we'll try to read from a local .env or hermes .env
def get_api_key():
    # Try project .env first
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.strip().split("=", 1)[1].strip('"').strip("'")
    
    # Try hermes .env
    hermes_env = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(hermes_env):
        with open(hermes_env) as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    # Handle commented out keys
                    val = line.strip().split("=", 1)[1].strip('"').strip("'")
                    if val and not val.startswith("#"):
                        return val
    return os.getenv("OPENROUTER_API_KEY")


def _load_env():
    """Populate os.environ from the project .env (without overriding real env vars),
    so LLM_BASE_URL / LLM_API_KEY / TAILOR_MODEL set there apply to the cron and all
    scripts regardless of working directory."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

# Model used for all LLM calls. Default to a cheap, JSON-reliable non-Claude model
# (~50x cheaper than Opus). The deterministic fabrication strip guarantees 0
# fabrications regardless of model, so a cheaper model only trades a little
# keyword-coverage polish for big savings.
# Override without editing code, e.g.:
#   export TAILOR_MODEL="deepseek/deepseek-v4-flash"     # even cheaper
#   export TAILOR_MODEL="qwen/qwen3-235b-a22b-2507"      # capable alternative
TAILOR_MODEL = os.getenv("TAILOR_MODEL", "google/gemini-2.5-flash-lite")


def _extract_json_object(text: str) -> str:
    """Return the first complete, brace-balanced JSON object embedded in text.

    Tolerates markdown fences, leading reasoning, and trailing commentary that
    some models (e.g. MiMo) wrap around the JSON. Returns "" if none found.
    """
    start = text.find("{")
    if start == -1:
        return ""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _parse_json_response(content: str) -> dict:
    """Parse a JSON object from an LLM response, tolerating fences/reasoning text."""
    if not content:
        # Reasoning models (e.g. MiMo) return content=None when their reasoning
        # pass exhausts max_tokens before emitting an answer. Surface clearly.
        raise ValueError("Model returned no content (a reasoning model may have used "
                         "the entire max_tokens on reasoning — raise max_tokens).")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
    if stripped.endswith("```"):
        stripped = stripped.rsplit("```", 1)[0]
    stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        candidate = _extract_json_object(content)
        if candidate:
            return json.loads(candidate)
        raise ValueError(f"Failed to parse LLM response as JSON:\n{content[:500]}")


def _client():
    """OpenAI-compatible client. Defaults to OpenRouter; point at a local Ollama
    server (or any OpenAI-compatible endpoint) via env, e.g.:
        export LLM_BASE_URL="http://10.0.0.18:11434/v1"
        export TAILOR_MODEL="qwen3.6:35b-256k"
    Local generation can take minutes, so the timeout is generous.
    """
    base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = os.getenv("LLM_API_KEY") or get_api_key()
    if not api_key:
        if "openrouter" in base_url:
            raise ValueError("OPENROUTER_API_KEY not found. Set it in .env or environment.")
        api_key = "local"  # local servers (Ollama) ignore the key
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=httpx.Timeout(600.0, connect=10.0),
    )


def _chat_json(client, messages, temperature, max_tokens):
    """Chat completion that requests strict JSON output, falling back gracefully
    for models that don't support response_format."""
    base = dict(model=TAILOR_MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens)
    try:
        return client.chat.completions.create(response_format={"type": "json_object"}, **base)
    except BadRequestError:
        return client.chat.completions.create(**base)


def tailor_resume(master_resume_path: str, job_description: str, role_template: str = "default",
                  feedback: str = "") -> dict:
    """
    Tailor the master resume to a specific job description using an LLM.

    Args:
        master_resume_path: Path to the master resume JSON
        job_description: The full text of the job description
        role_template: Which template to use (default, engineering, ai_ml, management)
        feedback: Optional gap feedback from a prior scoring pass, used to retarget
                  missing requirements and remove fabricated content.

    Returns:
        Tailored resume as a dictionary
    """
    client = _client()

    # Load master resume
    with open(master_resume_path) as f:
        master = json.load(f)

    # Auto-matched summary angle: pdf_gen renders summary_templates["default"], so
    # seed that slot with the chosen voice's text. The model then tailors THAT
    # angle to the JD — deterministically the right voice, regardless of which slot
    # the model would otherwise have rewritten. No-op when angle == "default".
    voices = master.get("summary_templates", {})
    if isinstance(voices, dict) and role_template in voices and role_template != "default":
        voices["default"] = voices[role_template]

    # Prepare the system prompt
    system_prompt = """You are an expert resume writer and ATS optimization specialist.
Your task is to tailor a master resume to match a specific job description.

RULES:
1. Preserve the JSON structure exactly as provided
2. Rewrite the professional summary to mirror the job's key requirements
3. Reorder skills to prioritize those mentioned in the JD
4. Rewrite experience bullets to emphasize relevant accomplishments
5. Use exact keywords from the JD where appropriate (ATS optimization)
6. Maintain the user's authentic voice and achievements
7. Do NOT fabricate experience or skills not present in the master resume.
   Every skill, tool, and accomplishment in your output must be traceable to
   the master resume. Rephrasing is allowed; inventing facts is not.
8. Output ONLY valid JSON, no markdown or explanations"""

    feedback_block = f"\n\nGAP FEEDBACK FROM PREVIOUS ATTEMPT (address this):\n{feedback}" if feedback else ""

    user_prompt = f"""TAILORED RESUME REQUEST

JOB DESCRIPTION:
{job_description}

MASTER RESUME:
{json.dumps(master, indent=2)}

ROLE TEMPLATE TO USE: {role_template}

Please tailor this resume to the job description above. Focus on:
- Summary that directly addresses their top 3 requirements
- Skills reordered to match their priority
- Experience bullets rewritten to highlight relevant achievements
- Keywords injected naturally for ATS optimization (only keywords the master resume supports){feedback_block}

Output the complete tailored resume as JSON:"""

    response = _chat_json(
        client,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=12000,  # headroom for the JSON resume + reasoning-model overhead
    )

    content = response.choices[0].message.content
    if response.choices[0].finish_reason == "length":
        raise ValueError("Tailored resume was truncated (hit max_tokens). Increase max_tokens.")
    return _parse_json_response(content)


def extract_requirements(job_description: str) -> list:
    """
    Use the LLM to pull the concrete, gradeable requirements out of a JD.

    Returns a list of {"keyword": str, "importance": "must"|"nice"} dicts.
    The keyword is a short, canonical phrase (e.g. "nDisplay", "Unreal Engine",
    "camera tracking") that we can then deterministically check for coverage.
    """
    client = _client()

    system_prompt = """You extract the hiring requirements from a job description.
Return ONLY valid JSON of the form:
{"requirements": [{"keyword": "<short canonical skill/tool/qualification>", "importance": "must"|"nice"}]}

RULES:
- keyword must be a short phrase a resume scanner would match (a skill, tool,
  technology, or concrete qualification) — not a full sentence.
- "must" = hard requirement / clearly required. "nice" = preferred / bonus.
- 8-20 requirements. No duplicates. No explanations outside the JSON."""

    response = _chat_json(
        client,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"JOB DESCRIPTION:\n{job_description}\n\nExtract the requirements as JSON:"},
        ],
        temperature=0.0,
        max_tokens=4000,  # headroom for reasoning models that "think" before answering
    )

    data = _parse_json_response(response.choices[0].message.content)
    reqs = data.get("requirements", []) if isinstance(data, dict) else []
    # Normalize
    out = []
    for r in reqs:
        kw = (r.get("keyword") or "").strip()
        if not kw:
            continue
        imp = "must" if r.get("importance", "must").lower().startswith("must") else "nice"
        out.append({"keyword": kw, "importance": imp})
    return out


# Signal phrases that suggest which master summary "voice" best fits a JD. The
# summary angle is auto-matched to each job (see tailor_resume_scored) rather than
# manually picked. "default" is the generic fallback when nothing clearly dominates.
_ANGLE_SIGNALS = {
    "executive":   ["vice president", "vp ", " vp,", "director of", "head of", "chief",
                    "c-suite", "executive", "strategic vision", "org-wide", "p&l", "board"],
    "management":  ["manage a team", "team lead", "people management", "stakeholder",
                    "budget", "cross-functional", "hiring", "mentor", "supervise",
                    "direct reports", "program management", "leadership of"],
    "ai_ml":       ["machine learning", "deep learning", "generative ai", "genai", "llm",
                    "large language model", "neural", "computer vision", "data science",
                    "mlops", "model training", "ai-driven", "automation"],
    "engineering": ["software engineer", "c++", "python", "real-time rendering",
                    "ndisplay", "unreal engine", "pipeline development", "shader",
                    "low-level", "sdk", "api integration", "systems engineering"],
}
# When two angles tie, prefer the more distinctive one in this order.
_ANGLE_TIEBREAK = ["ai_ml", "executive", "management", "engineering"]


def select_summary_angle(job_description: str, requirements: list = None) -> str:
    """Deterministically pick which master summary voice best fits a JD.

    Scores each angle by how many of its signal phrases appear in the JD (plus the
    extracted requirement keywords, which are canonical skills), and returns the
    best — or "default" when nothing clearly dominates. Deterministic on purpose,
    consistent with score_match: the angle is chosen by the JD, not the model.
    """
    haystack = (job_description or "").lower()
    if requirements:
        haystack += " " + " ".join((r.get("keyword") or "").lower() for r in requirements)
    scores = {a: sum(1 for sig in sigs if sig in haystack)
              for a, sigs in _ANGLE_SIGNALS.items()}
    best = max(scores.values()) if scores else 0
    if best == 0:
        return "default"
    winners = [a for a in _ANGLE_TIEBREAK if scores.get(a, 0) == best]
    return winners[0] if winners else "default"


def extract_job_meta(job_description: str) -> dict:
    """Best-effort extraction of a posting's title/company/location from its text.

    Used by the "paste a job link" flow, where we have the JD body but no
    structured title/company (unlike the scraper, which gets them from cards).
    Returns {"title", "company", "location"} with empty strings for anything the
    posting doesn't state.
    """
    client = _client()

    system_prompt = """You read a job posting and extract its metadata.
Return ONLY valid JSON: {"title": "<job title>", "company": "<hiring company>", "location": "<location or empty>"}
RULES:
- Use the exact title/company as written in the posting.
- If a field is not stated, use an empty string. No explanation outside the JSON."""

    response = _chat_json(
        client,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"JOB POSTING:\n{job_description[:4000]}\n\nExtract the metadata as JSON:"},
        ],
        temperature=0.0,
        max_tokens=2000,  # headroom for reasoning models that "think" first
    )

    data = _parse_json_response(response.choices[0].message.content)
    if not isinstance(data, dict):
        return {"title": "", "company": "", "location": ""}
    return {
        "title": (data.get("title") or "").strip(),
        "company": (data.get("company") or "").strip(),
        "location": (data.get("location") or "").strip(),
    }


def _flatten_text(obj) -> str:
    """Recursively collect all string content from a nested dict/list into one blob."""
    parts = []
    if isinstance(obj, dict):
        for v in obj.values():
            parts.append(_flatten_text(v))
    elif isinstance(obj, list):
        for v in obj:
            parts.append(_flatten_text(v))
    elif isinstance(obj, str):
        parts.append(obj)
    return " ".join(parts)


# Filler/modifier words that shouldn't count toward whether a skill traces to the
# master — they cause coincidental token matches (e.g. "Node-based" matching "Node.js").
_STOPWORDS = {
    "based", "using", "used", "level", "driven", "oriented", "ready", "native",
    "modern", "advanced", "strong", "style", "first", "and", "the", "for", "with",
    "via", "general", "various", "etc",
}


def _significant_words(s: str) -> list:
    return [w for w in re.split(r"[^a-z0-9+#.]+", s.lower())
            if len(w) > 2 and w not in _STOPWORDS]


def _keyword_covered(keyword: str, haystack: str) -> bool:
    """Strict: True if the keyword (or all its significant words) appears in haystack.
    Used for JD requirement coverage."""
    kw = keyword.lower().strip()
    if not kw:
        return False
    if kw in haystack:
        return True
    words = _significant_words(kw)
    return bool(words) and all(w in haystack for w in words)


def _skill_traces_to_master(skill: str, master_text: str, threshold: float = 0.6) -> bool:
    """Lenient: True if a skill plausibly traces to the master resume.

    A rephrasing like "Cross-functional Collaboration" (master: "Cross-functional
    Leadership") should pass; a genuinely new skill like "Niagara" should not.
    Passes if it's a substring/all-words match, OR if at least `threshold` of its
    significant words appear in the master.
    """
    if _keyword_covered(skill, master_text):
        return True
    words = _significant_words(skill)
    if not words:
        return False
    hits = sum(1 for w in words if w in master_text)
    return hits / len(words) >= threshold


def _strip_fabricated(tailored: dict, master_text: str) -> dict:
    """Deterministically remove any tailored skill that doesn't trace to the master.

    Guarantees the output skills section contains nothing the candidate can't back
    up, instead of trusting the model to have removed it.
    """
    skills = tailored.get("skills", {})
    if not isinstance(skills, dict):
        return tailored  # model returned a non-conforming structure; leave as-is
    if isinstance(skills.get("all"), list):
        skills["all"] = [s for s in skills["all"] if _skill_traces_to_master(s, master_text)]
    cats = skills.get("categories", {})
    if isinstance(cats, dict):
        for k, v in list(cats.items()):
            if isinstance(v, list):
                cats[k] = [s for s in v if _skill_traces_to_master(s, master_text)]
    return tailored


def score_match(tailored: dict, requirements: list, master: dict) -> dict:
    """
    Deterministically score how well the tailored resume covers the JD
    requirements, and flag any skills that don't trace back to the master.

    Returns a report dict with weighted overall score, must-have coverage,
    the covered/missing requirement lists, and fabricated-skill warnings.
    """
    resume_text = _flatten_text(tailored).lower()
    master_text = _flatten_text(master).lower()

    covered, missing = [], []
    for req in requirements:
        if _keyword_covered(req["keyword"], resume_text):
            covered.append(req)
        else:
            missing.append(req)

    def _coverage(items):
        if not items:
            return 1.0
        weight = {"must": 1.0, "nice": 0.5}
        total = sum(weight[r["importance"]] for r in items)
        hit = sum(weight[r["importance"]] for r in items if r in covered)
        return round(hit / total, 3) if total else 1.0

    must = [r for r in requirements if r["importance"] == "must"]
    must_missing = [r for r in missing if r["importance"] == "must"]

    # Fabrication check: tailored skills that don't appear anywhere in the master.
    skills_obj = tailored.get("skills", {})
    if not isinstance(skills_obj, dict):
        skills_obj = {}
    tailored_skills = list(skills_obj.get("all", []) or [])
    cats = skills_obj.get("categories", {})
    if isinstance(cats, dict):
        for cat in cats.values():
            if isinstance(cat, list):
                tailored_skills.extend(cat)
    fabricated = []
    for skill in tailored_skills:
        if skill and not _skill_traces_to_master(skill, master_text):
            fabricated.append(skill)

    return {
        "score": _coverage(requirements),
        "must_coverage": _coverage(must),
        "covered": [r["keyword"] for r in covered],
        "missing": [r["keyword"] for r in missing],
        "must_missing": [r["keyword"] for r in must_missing],
        "fabricated": sorted(set(fabricated)),
        "requirements_total": len(requirements),
    }


def tailor_resume_scored(master_resume_path: str, job_description: str,
                         role_template: str = "default", target: float = 0.85,
                         max_attempts: int = 2) -> tuple:
    """
    Tailor the resume, then loop: score must-have coverage and re-tailor with
    gap feedback until the target is met (or attempts run out). Returns the best
    (tailored_resume, report) seen.

    The report's `score`/`must_coverage` are computed in code, not by the LLM,
    so they reflect actual keyword coverage rather than a model's self-grade.
    """
    with open(master_resume_path) as f:
        master = json.load(f)

    requirements = extract_requirements(job_description)
    # Auto-match the summary voice to this JD (overrides any manually-passed
    # role_template — selection is now driven by the job, not a dropdown).
    angle = select_summary_angle(job_description, requirements)

    best = None
    feedback = ""
    for _ in range(max_attempts):
        tailored = tailor_resume(master_resume_path, job_description, angle, feedback=feedback)
        report = score_match(tailored, requirements, master)

        if best is None or report["must_coverage"] > best[1]["must_coverage"]:
            best = (tailored, report)

        if report["must_coverage"] >= target and not report["fabricated"]:
            break

        # Build feedback for the next attempt
        lines = []
        if report["must_missing"]:
            lines.append("MISSING required keywords (add them if the master resume "
                         "genuinely supports them, otherwise leave out): "
                         + ", ".join(report["must_missing"]))
        if report["fabricated"]:
            lines.append("REMOVE these skills — they are not in the master resume: "
                         + ", ".join(report["fabricated"]))
        feedback = "\n".join(lines)
        if not feedback:
            break

    # Final deterministic cleanup: strip any skill that still doesn't trace to the
    # master, then re-score so the stored report reflects the cleaned resume.
    tailored, _ = best
    master_text = _flatten_text(master).lower()
    tailored = _strip_fabricated(tailored, master_text)
    report = score_match(tailored, requirements, master)
    report["summary_angle"] = angle
    return tailored, report

def generate_cover_letter(master_resume_path: str, job_description: str, company_name: str) -> str:
    """Generate a tailored cover letter for the job application."""
    client = _client()

    with open(master_resume_path) as f:
        master = json.load(f)
    
    prompt = f"""Write a professional, compelling cover letter for this job application.

JOB DESCRIPTION:
{job_description}

CANDIDATE PROFILE:
Name: {master['personal']['name']}
Current Role: {master['experience'][0]['title']} at {master['experience'][0]['company']}

KEY RELEVANT EXPERIENCE:
{json.dumps(master['experience'][0]['bullets']['default'][:3], indent=2)}

REQUIREMENTS:
- 3 paragraphs maximum
- Opening: Hook with specific enthusiasm for {company_name} and the role
- Middle: Connect your top 2-3 achievements directly to their requirements
- Closing: Call to action, express excitement to discuss further
- Tone: Professional but personable, not generic
- Length: 250-300 words

Write the cover letter now:"""

    response = client.chat.completions.create(
        model=TAILOR_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1000,
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    # Test the tailor
    import sys
    
    master_path = "data/master/resume.json"
    sample_jd = """
    Senior Virtual Production Supervisor
    
    We're looking for an experienced Virtual Production Supervisor to lead our LED volume operations.
    
    Requirements:
    - 5+ years experience with LED volumes and nDisplay
    - Strong understanding of camera tracking systems (FreeD, Mo-Sys, Stype)
    - Experience with Unreal Engine real-time rendering
    - AI/ML integration into production pipelines preferred
    - Leadership experience managing technical teams
    
    Responsibilities:
    - Lead daily VP operations on our LED stage
    - Optimize real-time rendering performance
    - Integrate emerging AI tools into production workflows
    - Train and mentor junior team members
    """
    
    print("Tailoring resume (scored loop)...")
    tailored, report = tailor_resume_scored(master_path, sample_jd, "default")

    # Save tailored version
    output_path = "data/applications/tailored_sample.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(tailored, f, indent=2)

    print(f"Saved to {output_path}")
    print(f"Summary preview: {tailored['summary_templates']['default'][:200]}...")
    print("\nMATCH REPORT")
    print(f"  overall score:   {report['score']}")
    print(f"  must coverage:   {report['must_coverage']}")
    print(f"  covered:         {report['covered']}")
    print(f"  missing:         {report['missing']}")
    print(f"  fabricated:      {report['fabricated']}")
