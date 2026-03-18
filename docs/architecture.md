# Architecture

## Overview

`local-recruiter-outreach` is a local-first monorepo with:

- `backend/`: FastAPI API, SQLite persistence, public web discovery, resume parsing, local Ollama integration, SMTP sending.
- `frontend/`: React + Vite + TypeScript + Tailwind UI for the four-input workflow, settings, review, export, and manual send.
- `docs/`: architecture notes and operating constraints.

## Backend flow

1. `POST /api/analyze`
2. Parse resume file with `pdfplumber`, `python-docx`, or plain text decoding.
3. Normalize job context and extract lightweight keywords.
4. Run layered public discovery:
   - DuckDuckGo HTML search
   - optional cached results from SQLite
   - optional public page fetch for non-authenticated URLs
   - optional Playwright fallback for public JS-rendered pages
5. Filter contacts to US-based candidates using heuristics only when evidence is present.
6. Rank contacts transparently with company match, title relevance, source confidence, US confidence, and public email bonus.
7. Select the most relevant resume bullets/projects for the role with `sentence-transformers` when available, then fallback to lexical overlap.
8. Draft one email per contact through the local Ollama HTTP API.
9. Persist jobs, resumes, contacts, generated emails, and send logs in SQLite.

## Discovery realism

- The app never logs into LinkedIn.
- The app never fabricates recruiter emails.
- A contact card can exist without an email address.
- Source URLs are preserved and exposed in the API and UI.
- If fewer than five valid contacts are found, the backend returns fewer than five and includes warnings.

## Local settings model

The frontend stores runtime settings in browser local storage and passes them to the backend per request:

- Ollama base URL and model
- SMTP configuration

Environment variables still provide the default local configuration in `backend/.env`.

## Persistence

SQLite tables:

- `jobs`
- `resumes`
- `contacts`
- `generated_emails`
- `send_logs`
- `search_cache` for lightweight public search caching

## Testing

The backend test suite covers:

- US location heuristics
- deduplication behavior
- recruiter title matching
- email hallucination guard behavior
- one integration-style analyze pipeline test with mocked discovery and mocked Ollama-style email generation

