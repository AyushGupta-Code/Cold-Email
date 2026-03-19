# local-recruiter-outreach

Local-only recruiter outreach app that finds public US-based recruiter-style contacts, shows the source URLs used, drafts personalized outreach emails through Ollama, and optionally sends reviewed emails manually through SMTP.

Repository root: `Cold-Email/`

## Repo tree

```text
Cold-Email/
├── Makefile
├── README.md
├── requirements.txt
├── backend
│   ├── .env.example
│   ├── app
│   │   ├── api
│   │   │   └── routes.py
│   │   ├── core
│   │   │   └── config.py
│   │   ├── db
│   │   │   └── session.py
│   │   ├── main.py
│   │   ├── models
│   │   │   └── entities.py
│   │   ├── prompts
│   │   │   ├── email_v1_system.txt
│   │   │   └── email_v1_user.txt
│   │   ├── schemas
│   │   │   └── api.py
│   │   ├── services
│   │   │   ├── contact_discovery.py
│   │   │   ├── contact_ranker.py
│   │   │   ├── email_generator.py
│   │   │   ├── job_profile.py
│   │   │   ├── persistence.py
│   │   │   ├── resume_parser.py
│   │   │   ├── smtp_sender.py
│   │   │   └── us_filter.py
│   │   ├── tests
│   │   │   ├── test_analyze_pipeline.py
│   │   │   ├── test_contact_logic.py
│   │   │   ├── test_email_hallucination_guard.py
│   │   │   └── test_us_filter.py
│   │   └── utils
│   │       ├── http.py
│   │       └── text.py
│   ├── requirements.txt
│   └── sample_data
│       ├── mock_search_results.json
│       └── sample_resume.txt
├── docs
│   └── architecture.md
└── frontend
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── src
    │   ├── App.tsx
    │   ├── components
    │   │   ├── AppShell.tsx
    │   │   ├── ContactCard.tsx
    │   │   ├── EmptyState.tsx
    │   │   ├── ExportActions.tsx
    │   │   ├── FormSection.tsx
    │   │   ├── SettingsPanel.tsx
    │   │   └── StageProgress.tsx
    │   ├── lib
    │   │   ├── api.ts
    │   │   ├── storage.ts
    │   │   └── utils.ts
    │   ├── main.tsx
    │   ├── pages
    │   │   └── HomePage.tsx
    │   └── types
    │       └── api.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── tsconfig.node.json
    └── vite.config.ts
```

## Features

- Exactly four main inputs: company name, position, job description, resume upload.
- Public-web discovery only. No paid APIs, no cloud LLM APIs, no authenticated scraping.
- US-based contact filtering with transparent warnings when confidence is limited.
- Up to five ranked contacts with source URLs, profile URL, public email if found, and one draft per contact.
- Local Ollama email generation with prompt templates stored in the repository.
- Optional SMTP manual sending only after review and explicit click.
- CSV/JSON export and editable drafts in the UI.

## Exact setup commands

### 0. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
``` 

### 1. Clone or enter the repo

```bash
cd /mnt/c/Users/ayush/Desktop/Projects/Cold-Email
```

### 2. Backend setup

```bash
conda create -n cold-email python=3.12 -y
conda activate cold-email
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp backend/.env.example backend/.env
```

Optional Playwright browser install if you enable JS fallback:

```bash
python -m playwright install chromium
```

### 3. Ollama setup

Install Ollama locally, start it, and pull a model that fits your machine. For an RTX 4070 8 GB, the default is realistic:

```bash
ollama serve
ollama pull mistral
```

Optional smaller fallback:

```bash
ollama pull phi3:mini
```

### 4. Frontend setup

```bash
cd frontend
npm install
```

## Exact run commands

### Run backend

```bash
cd /mnt/c/Users/ayush/Desktop/Projects/Cold-Email
conda activate cold-email
uvicorn app.main:app --reload --app-dir backend
```

### Run frontend

```bash
cd /mnt/c/Users/ayush/Desktop/Projects/Cold-Email/frontend
npm run dev
```

Open `http://localhost:5173`.

### Run tests

```bash
cd /mnt/c/Users/ayush/Desktop/Projects/Cold-Email
conda activate cold-email
PYTHONPATH=backend pytest backend/app/tests --capture=sys
```

### Build frontend

```bash
cd /mnt/c/Users/ayush/Desktop/Projects/Cold-Email/frontend
npm run build
```

## Backend environment notes

Important `backend/.env` values:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
DISCOVERY_MODE=live
DISCOVERY_USE_PLAYWRIGHT_FALLBACK=false
SMTP_ENABLED=false
```

Set `DISCOVERY_MODE=mock` for offline UI development. Mock mode is explicitly labeled in backend warnings so it is not confused with real public data.

## API endpoints

- `POST /api/analyze`
- `POST /api/regenerate-email`
- `POST /api/send-email`
- `GET /api/health`
- `GET /api/settings/test-ollama`
- `GET /api/settings/test-smtp`

## Known limitations

- Public recruiter emails are often unavailable, so many contact cards will have blank email fields.
- Public search result parsing is intentionally lightweight and can degrade when search engines change markup or rate limit requests.
- US location detection is heuristic-based and conservative by design.
- The first `sentence-transformers` use may download a local embedding model, which adds setup time.
- Local models can occasionally ignore strict JSON formatting; the backend includes a fallback parser, but smaller models may still need regeneration.

## Next improvements

- Add a richer multi-engine search layer with additional public sources and stronger retry controls.
- Expand source extraction for company team pages and public careers pages with per-domain parsers.
- Add a lightweight review history UI backed by the existing SQLite tables.
- Stream progress updates from the backend instead of the current staged frontend loader.
- Add screenshot assets to `docs/` after the first local run for portfolio packaging.
