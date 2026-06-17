import os
import json
from openai import OpenAI
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

def tailor_resume(master_resume_path: str, job_description: str, role_template: str = "default") -> dict:
    """
    Tailor the master resume to a specific job description using an LLM.
    
    Args:
        master_resume_path: Path to the master resume JSON
        job_description: The full text of the job description
        role_template: Which template to use (default, engineering, ai_ml, management)
    
    Returns:
        Tailored resume as a dictionary
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found. Set it in .env or environment.")
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )
    
    # Load master resume
    with open(master_resume_path) as f:
        master = json.load(f)
    
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
7. Do NOT fabricate experience or skills not present in the master resume
8. Output ONLY valid JSON, no markdown or explanations"""

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
- Keywords injected naturally for ATS optimization

Output the complete tailored resume as JSON:"""

    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=4000,
    )
    
    content = response.choices[0].message.content
    
    # Clean up the response - remove markdown code blocks if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    content = content.strip()
    
    try:
        tailored = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            tailored = json.loads(json_match.group())
        else:
            raise ValueError(f"Failed to parse LLM response as JSON:\n{content[:500]}")
    
    return tailored

def generate_cover_letter(master_resume_path: str, job_description: str, company_name: str) -> str:
    """Generate a tailored cover letter for the job application."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found.")
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=httpx.Timeout(60.0, connect=10.0),
    )
    
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
        model="anthropic/claude-sonnet-4",
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
    
    print("Tailoring resume...")
    tailored = tailor_resume(master_path, sample_jd, "default")
    
    # Save tailored version
    output_path = "data/applications/tailored_sample.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(tailored, f, indent=2)
    
    print(f"Saved to {output_path}")
    print(f"Summary preview: {tailored['summary_templates']['default'][:200]}...")
