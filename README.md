# Job Autopilot

AI-powered job application automation. Apply to 50+ jobs/week with tailored resumes, auto-submit, tracking, and follow-up sequences.

## Quick Start

1. Add your resume data to `data/master/resume.json`
2. Configure job preferences in `data/master/preferences.json`
3. Import n8n workflows from `workflows/`
4. Run daily job scraper → AI tailor → auto-apply

## Structure

```
src/
  scraper/       # Job board scrapers (LinkedIn, Indeed, BuiltIn)
  tailor/        # AI resume tailoring engine
  generator/     # PDF resume + cover letter generation
  submitter/     # Auto-apply via Playwright
workflows/       # n8n workflow JSON exports
data/
  master/        # Your resume data + preferences (JSON)
  jobs/          # Scraped job listings
  applications/  # Application history
templates/
  resume/        # Resume PDF templates
  cover-letter/  # Cover letter templates
docs/            # Architecture docs, guides
```

## Architecture

See [PROJECT.md](PROJECT.md) for full architecture diagram and task list.

## Tech Stack

- **n8n** — workflow orchestration
- **OpenRouter** — AI (scoring, tailoring, cover letters)
- **Playwright** — browser automation
- **Google Sheets** — tracking
- **Himalaya** — email
- **Telegram** — notifications

## Status

🚧 Early planning — see PROJECT.md for progress.
