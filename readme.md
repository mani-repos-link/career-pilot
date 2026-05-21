# Career Pilot

Personal job-hunt assistant. Tailors resumes per job description, scrapes LinkedIn / Indeed, auto-applies, tracks responses. Built solo, personal use first, may grow into SaaS.

Forked from the chatbot project — reuses the chat UI, tool-calling loop, session/memory, and RAG layer.

## Goals

- Per-JD tailored resumes (LLM-rewritten, rendered to PDF).
- Job search across LinkedIn / Indeed (cookie auth, Playwright).
- Parse JDs (skills, requirements, keywords).
- Auto-apply via form fill (LinkedIn Easy Apply first, then Indeed quick apply).
- Track applications + replies in one place.
- Store resumes, JDs, statuses, and history.

## Stack

- **Frontend:** Vue 3, Vite, TypeScript, Tailwind (via `apps/web`).
- **Backend:** Python + FastAPI (`apps/pyapi`).
- **Database:** Postgres 18 + pgvector (vectors) + PostGIS (location queries on jobs). Runs via `docker-compose up postgres`.
- **Storage:** local filesystem or S3 for resume + JD PDFs.
- **Scraping:** Playwright (stealth), cookie-based portal auth.
- **Shared:** `packages/utils` — TS helpers, tool-call parser inherited from chatbot.

## Layout

```
.
├── apps
│   ├── pyapi          # FastAPI backend
│   └── web            # Vue 3 frontend
├── packages
│   └── utils          # Shared TS
├── docker-compose.yml # postgres + pyapi + web
├── .env.example
└── CLAUDE.md          # project context for Claude
```

## Run locally

```bash
pnpm install
cp .env.example .env   # fill in keys, generate COOKIE_ENCRYPTION_KEY
docker-compose up -d postgres
pnpm dev
```

Frontend → http://localhost:5173, API → http://localhost:8080.

## MVP order

1. **Week 1** — Resume tailoring. User pastes JD, system outputs tailored resume PDF. Pure LLM + render. Zero scraping risk.
2. **Week 2** — JD parsing + Postgres schema. Save jobs + tailored resumes, history view.
3. **Week 3** — LinkedIn search via cookie. Playwright + stealth. Manual cookie paste.
4. **Week 4** — Auto-apply (LinkedIn Easy Apply, then Indeed quick apply).
5. **Later** — Multi-portal, status tracking, scheduled runs.

## Risks

- LinkedIn / Indeed ToS forbid scraping — IP-ban risk. Use rotating proxies and respect rate limits. Personal use only initially.
- Cookies must be encrypted at rest (AES-GCM, key from `COOKIE_ENCRYPTION_KEY`). Never logged.
- Captcha fallback via Playwright stealth + manual intervention.

## Status

Early. Skeleton inherited from chatbot fork. Active work: resume tailoring (MVP week 1).
