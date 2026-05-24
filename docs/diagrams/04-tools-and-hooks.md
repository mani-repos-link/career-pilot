# 04 — Tools & Hooks

**Tools** are the model's hands. **Hooks** are the event bus the runtime fires at fixed lifecycle points; handlers can observe, mutate, short-circuit, or persist.

## Tool registry

```mermaid
flowchart TB
    subgraph Parse["Inbound parsing"]
        Raw["LLM raw output"]
        Dialect["dialects.select_dialect(model)<br/>QWEN · LLAMA · GEMMA<br/>LONGCAT · NEMOTRON · MINIMAX · DEFAULT"]
        Parsed["ToolRequest{tool, arguments}"]
    end

    subgraph Registry["tools/registry.py — HANDLERS dict"]
        direction LR
        subgraph Local["Local FS (sync)"]
            ls
            grep
            read_file
            project_tree
            find_symbol
        end
        subgraph Web["Web (sync)"]
            fetch_url
            curl
            wget
            web_search
            read_llms_txt
            crawl_site
        end
        subgraph Mem["Memory (async)"]
            remember
            forget
            recall
        end
        subgraph Render["Rendering (sync)"]
            render_resume
            save_document
            render_pdf
        end
        subgraph Job["Job domain"]
            search_jobs["search_jobs <i>async</i>"]
            parse_jd
            store_job
            store_jd
            log_application
            update_status
            list_applications
            explain_context
        end
    end

    subgraph Exec["Execution"]
        Sync["execute_tool_call(...)<br/>sync — used by tests"]
        Async["execute_tool_call_async(...)<br/>used by agent loop"]
        Result["ToolExecutionResult{tool, ok, output}"]
    end

    Raw --> Dialect --> Parsed
    Parsed --> Async
    Parsed --> Sync
    Async -. awaits .-> Registry
    Sync -. calls .-> Registry
    Registry --> Result

    classDef async fill:#dbeafe,stroke:#1d4ed8,color:#000
    classDef sync fill:#e5e7eb,stroke:#374151,color:#000
    class search_jobs,remember,forget,recall,Async async
    class Sync sync
```

Async awared dispatch: Required for Playwright-based handlers (`search_jobs`) and async memory I/O. They run on the FastAPI event loop without spawning new ones.

## Tool capabilities ↔ system prompt

`agents/system_prompt.py:format_capabilities` injects a per-capability list into the prompt, gated by:
- `tools.enabled` — master switch
- `tools.internet_enabled` — hides web/job-domain tools when off
- per-sub-agent `tool_names` allowlist

The model only sees tools it can actually call.

## Hook lifecycle

```mermaid
flowchart LR
    subgraph Loop["agent loop (per turn)"]
        TS[turn.start]
        MP1[model.pre_call]
        MP2[model.post_call]
        TP1[tool.pre_call]
        TP2[tool.post_call]
        TE[turn.end]
    end

    subgraph Delegate["delegation"]
        DP1[delegate.pre]
        DP2[delegate.post]
    end

    TS --> MP1 --> MP2 --> TP1 --> TP2 -.->|"iterate"| MP1
    MP2 -.->|"no tool call"| TE
    MP2 -. "&lt;delegate&gt; tag" .-> DP1 --> DP2 --> TE

    classDef ev fill:#fef3c7,stroke:#d97706,color:#000
    class TS,MP1,MP2,TP1,TP2,TE,DP1,DP2 ev
```

## Built-in handlers (registered at startup)

| Handler | Event | Effect |
|---|---|---|
| `_memory_injector` | `model.pre_call` | Loads session plus global memories and appends to `system_prompt` |
| `_profile_injector` | `delegate.pre` (resume_tailor only) | Wraps the instruction with `profile.yml` YAML |
| `LifecycleLogger` | all 6 events + turn.start/end | Structured logs with session_id, sequence #, agent, model, call counts |
| `llm_call_throttle` | `model.pre_call` | Rate-limit guard |

## Handler contract

```python
async def handler(event: str, payload: dict) -> dict
```

- Return value is shallow merged into payload for next handler in chain.
- Raise `HookHalt(payload)` to short-circuit (skip remaining handlers + the natural operation). Used by `pre_tool` to inject cached results, by `pre_call` to inject mocked LLM responses in tests.
- Handlers are async; the registry `await`s each one in registration order.


- **Composability.** Adding caching, observability, or a rate limit doesn't touch the loop.
- **Test surface.** Hooks let tests inject deterministic results at the same seam production runs.
- **Plugin slot.** Future evals, OpenTelemetry exports, or token accounting all hang off these events without rewriting `loop.py`.
