# Career Pilot

A personal job hunt assistant. Chat first interface, using tools, LLM agents, Postgres backed history. Built solo, open source, for anyone who wants the same workflow. LLMs agnostic and can be used with free LLMs from different providers like Huggingface and openrouter.


## What's in the box today

- **Chat UI** with streaming responses, session history, and message branching (regenerate any assistant turn).
- **Tool calling agent loop** the model can call typed tools, see the result, and continue reasoning. Tools are async-aware so Playwright based handlers run on the same event loop as the API.
- **Orchestrator + four focused sub agents** — `resume_tailor`, `job_scout`, `applier`, `tracker`. The main agent delegates one turn at a time; each sub-agent has its own system prompt and tool allowlist.
- **Memory** — scoped key value store (session + global). The model can pin facts (`remember`), recall them (`recall`), or drop them (`forget`). Session memories are auto injected into the system prompt. _Space for improvement. Have something in mind..._
- **Hooks** — lifecycle events (`model.pre_call`, `tool.post_call`, `delegate.pre`, etc.) you can subscribe to for logging, caching, rate limiting, or test mocking.
- **Job domain tools** — `search_jobs` (cookies auth Playwright against configured portals), `parse_jd`, `store_job`, `store_jd`, `log_application`, `update_status`, `list_applications`.
- **Resume rendering** — `render_resume`, `save_document`, `render_pdf` (Markdown → HTML → PDF via WeasyPrint).
- **YAML driven config** — agents, prompts, portal definitions, and your profile all live in editable YAML/Markdown files. No code change to retune an agent or add a portal.

## Stack (Monorepo)

- **Frontend** — Vue 3 + Vite + TypeScript (`apps/web`).
- **Backend** — Python 3.10 + FastAPI (`apps/pyapi`), uv managed.
- **Database** — Postgres 18 with `pgvector` extensions available (Docker image: `pgvector/pgvector:pg18-trixie`).
- **LLM providers** — OpenRouter and HuggingFace adapters out of the box ut can be added easily more by implementing the `ChatProvider` protocol.
- **Browser automation** — Playwright (Chromium).
- **Workspace** — pnpm workspace tying web + shared TS packages.

## Architecture

A small documentaion with some diagrams 

| Diagram | What it shows |
|---|---|
| [01 — System Architecture](./docs/diagrams/01-system-architecture.md) | Component layers and external edges |
| [02 — Request Flow](./docs/diagrams/02-request-flow.md) | One HTTP request through the tool loop |
| [03 — Agent Orchestration](./docs/diagrams/03-agent-orchestration.md) | Main agent ↔ four sub-agents, delegation handshake |
| [04 — Tools & Hooks](./docs/diagrams/04-tools-and-hooks.md) | Tool registry, dialects, and the hook lifecycle |
| [05 — Data Model](./docs/diagrams/05-data-model.md) | Postgres ERD across chat, observability, and job-hunt rings |

Start with [the diagrams README](./docs/diagrams/README.md) for the suggested
reading order.

## Layout

```
.
├── apps/
│   ├── pyapi/
│   └── web/
├── packages/
│   └── utils/
├── config/
│   ├── agents.yml
│   ├── tools.yml
│   └── prompts/
│       └── agents/
├── data/
│   ├── cookies.example.yml
│   └── job-search-portals.example.yml
├── docs/diagrams/
├── migrations/
├── docker-compose.yml
└── .env.example
```

## Run locally

```bash
pnpm install
cp .env.example .env        # fill in LLM API keys
docker-compose up -d postgres
playwright install chromium
cp data/cookies.example.yml data/cookies.yml
cp data/job-search-portals.example.yml data/job-search-portals.yml
pnpm dev
```

Web → http://localhost:5173, API → http://localhost:8080,
health check → http://localhost:8080/healthz.

Run the Python tests:

```bash
cd apps/pyapi && uv run python -m unittest discover -v
```

## Configuration

| File | Purpose |
|---|---|
| `.env` | LLM keys, database URL, per-agent model overrides (format `RESUME_TAILOR_LLM=provider|:model`, e.g. `openrouter|:openrouter/owl-alpha:free`) |
| `config/agents.yml` | Each sub-agent's prompt path, tool allowlist, and description |
| `config/prompts/agents/*.md` | System prompt for each sub-agent — edit freely |
| `config/tools.yml` | Capability flags (internet, etc.) |
| `data/profile/profile.yml` | Your candidate profile — auto-injected into `resume_tailor` instructions |
| `data/cookies.yml` | Per portal cookie jar (see template) |
| `data/job-search-portals.yml` | Portal definitions: search URLs, roles to include/exclude |

## Adding a new tool

1. Write a handler in `apps/pyapi/pyapi/tools/<name>.py` — sync `def` or `async def`, signature `(config, args, session_id) -> str`.
2. Register it in `apps/pyapi/pyapi/tools/registry.py` under `HANDLERS`.
3. Declare its capability in `pyapi/tools/manifest.py` so the system prompt surfaces it.
4. Add it to the relevant sub-agent's `tools:` list in `config/agents.yml` (or leave it main agent only).

## Adding a new sub-agent

1. Drop a markdown system prompt in `config/prompts/agents/<name>.md`.
2. Add an entry in `config/agents.yml` with `name`, `prompt`, `tools`, and a one paragraph `description` (the orchestrator uses the description to decide when to route to it).
3. Optionally pin a model: `<NAME>_LLM=provider|:model` in `.env` (e.g. `RESUME_TAILOR_LLM=openrouter|:openrouter/owl-alpha:free`).

That's it — restart the API and the orchestrator can delegate to it.

## A note on portal scraping

`search_jobs` uses cookie authenticated Playwright sessions. LinkedIn and Indeed both prohibit scraping in their terms of service; treat this tool as "polite, personal use automation that walks the same paths a logged-in user would." Run sparingly, respect rate limits, and don't redistribute scraped data. Cookies live in plain text under `data/cookies.yml` — keep mode `600` and don't commit the file.

## Project status

Pre-release. The chat UI, agent loop, hook system, memory store, resume rendering, and `search_jobs` are working. Sub-agent tool allowlists for `applier` are still in scaffolding — the form fill flow is the next milestone.

## Nice to have features

Ideas already on the radar, not yet built:

- **Bounded delegation depth** — a configurable `MAX_DELEGATIONS` cap so sub-agents could safely re-delegate without infinite loops. Today delegation is naturally capped at one per user turn; lifting that restriction would unlock multi-step planner → executor flows.
- **Auto-apply via `applier`** — Playwright form-fill for LinkedIn Easy Apply and Indeed quick apply, with captcha fallback to a manual step.
- **Encrypted cookie jar** — AES-GCM at rest for `data/cookies.yml` with the key in an OS keyring instead of plain text.
- **Multi-portal scout** — beyond LinkedIn + Indeed: extensible portal adapters defined entirely in `job-search-portals.yml`.
- **Scheduled runs** — cron-style background searches that drop new matches into a session for review.
- **Status-board view** — Kanban over the `applications` table (planned → submitted → interview → offer/rejected).
- **Similar-job matching** — wire up the pgvector extension to surface "you've already applied to 3 like this" while browsing.

PRs picking any of these up are welcome.
