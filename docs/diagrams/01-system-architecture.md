# 01 — System Architecture (High level layering)

Web client talks to FastAPI and FastAPI composes one immutable `AppServices` bundle. Then, it hands to every service call. The side-effect adapters (LLM API, Postgres, Playwright, FS) have to sit at the edge.

```mermaid
flowchart TB
    subgraph Client["apps/web — Vue 3 + Vite"]
        UI[Chat UI / streaming]
    end

    subgraph API["apps/pyapi — FastAPI"]
        direction TB
        Routers["routers/<br/>sessions · messages · providers · healthz"]
        Services["services/<br/>conversation · dispatch · titles"]
        Agents["agents/<br/>orchestrator · catalog · loop · system_prompt"]
        Tools["tools/<br/>registry · dialects · handlers"]
        Hooks["hooks/<br/>HookRegistry · builtins · lifecycle_logger"]
        Memory["memory/<br/>MemoryStore (session + global)"]
        Store["store/<br/>SQLModel · engine · migrations"]
        Providers["providers/<br/>OpenRouter · HuggingFace"]
        Inputs["inputs/<br/>profile.yml · cookies.yml · job-search-portals.yml"]
    end

    subgraph Edge["External"]
        LLM["LLM gateways<br/>(OpenRouter / HF)"]
        PG[("Postgres 18<br/>pgvector + PostGIS")]
        Browser["Playwright Chromium<br/>(LinkedIn / Indeed)"]
        FS["Local FS<br/>data/ · resumes · JD snapshots"]
    end

    UI -->|HTTP / SSE| Routers
    Routers --> Services
    Services --> Agents
    Services --> Store
    Agents --> Tools
    Agents --> Providers
    Agents -. emit events .-> Hooks
    Services -. emit events .-> Hooks
    Hooks --> Memory
    Hooks --> Inputs
    Tools --> Memory
    Tools --> Inputs
    Tools --> Browser
    Tools --> FS
    Tools --> Store
    Memory --> Store
    Store --> PG
    Providers --> LLM

    classDef edge fill:#fef3c7,stroke:#d97706,color:#000
    classDef api fill:#dbeafe,stroke:#1d4ed8,color:#000
    classDef client fill:#dcfce7,stroke:#15803d,color:#000
    class LLM,PG,Browser,FS edge
    class Routers,Services,Agents,Tools,Hooks,Memory,Store,Providers,Inputs api
    class UI client
```

## Layer responsibilities

| Layer | Purpose | Knows about |
|---|---|---|
| **Routers** | HTTP surface — validation, pagination, status codes | Services + DTOs |
| **Services** | Use-case orchestration (one request = one service call) | Agents, Store, AppServices |
| **Agents** | LLM tool-calling loop + sub-agent delegation | Providers, Tools, Hooks |
| **Tools** | Side-effect actions (search jobs, parse JD, render PDF, memory CRUD) | Browser, FS, Store, Inputs |
| **Hooks** | Cross-cutting concerns: memory injection, profile injection, rate-limit, logging | Memory, Inputs |
| **Memory** | Scoped key-value store (per-session + global), injected into system prompt | Store |
| **Store** | Postgres CRUD via SQLModel | Postgres |
| **Providers** | Stateless LLM clients implementing `ChatProvider` protocol | LLM gateways |
| **Inputs** | Static YAML config loaders (profile, cookies, job-search prefs) | FS |

## AppServices (the dependency bundle)
```
AppServices(
    store, chat_provider, chat_config, context, tools,
    catalog,           # dict[str, SubAgent]
    hooks,             # HookRegistry
    lifecycle,         # LifecycleLogger
)
```
