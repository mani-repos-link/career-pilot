# 03 — Agent Orchestration

The main agent (Career Pilot persona) can delegate a turn to one focused sub-agent. Each sub-agent has a tool allowlist, its own system prompt, and optionally its own model. Delegations are stateless one-shots; a sub-agent's result is returned to the user directly, so at most one delegation happens per user turn.

## Catalog

```mermaid
flowchart LR
    subgraph Main["Main agent (orchestrator)"]
        Persona["Career Pilot persona<br/>system_prompt.py"]
    end

    subgraph SubAgents["catalog.py — sub-agents"]
        RT["resume_tailor<br/>rewrites base resume vs JD<br/><i>render_resume · save_document<br/>render_pdf · recall · remember</i>"]
        JS["job_scout<br/>searches portals · parses JDs<br/><i>search_jobs · parse_jd · fetch_url<br/>store_job · store_jd · remember</i>"]
        AP["applier<br/>Playwright form fill<br/><i>apply_job · log_application<br/>update_status</i> (planned)"]
        TR["tracker<br/>read/write application records<br/><i>list_applications · update_status<br/>log_application</i>"]
    end

    Persona -->|"&lt;delegate&gt;{agent,instruction}"| RT
    Persona --> JS
    Persona --> AP
    Persona --> TR

    classDef agent fill:#ede9fe,stroke:#6d28d9,color:#000
    classDef main fill:#fee2e2,stroke:#b91c1c,color:#000
    class RT,JS,AP,TR agent
    class Persona main
```

`SubAgent` shape (`agents/base.py:6`):

```python
SubAgent(name, description, system_prompt, tool_names, provider_override?, model_override?)
```

## Delegation sequence

```mermaid
sequenceDiagram
    autonumber
    participant CV as conversation.<br/>complete_with_tools
    participant ORC as orchestrator<br/>(parse_delegate)
    participant DSP as dispatch.<br/>dispatch_delegate
    participant H as HookRegistry
    participant LLM as Provider<br/>(may override)
    participant SUB as run_subagent<br/>(stateless loop)
    participant REG as tools/registry

    CV->>ORC: parse_delegate(model_output, catalog)
    ORC-->>CV: DelegateCall{agent, instruction} | None

    alt has DelegateCall
        CV->>DSP: dispatch_delegate(content, sid)
        DSP->>H: emit delegate.pre {agent, instruction}
        Note over H: _profile_injector wraps<br/>instruction with profile.yml<br/>(resume_tailor only)
        H-->>DSP: {instruction (possibly rewritten)}
        DSP->>LLM: pick provider (override or default)
        DSP->>SUB: run_subagent(provider, agent, instruction)

        loop sub-agent tool loop
            SUB->>LLM: complete(turns, sub.system_prompt)
            LLM-->>SUB: ChatResult
            opt tool_call
                SUB->>REG: execute_tool_call_async<br/>(allowed_names = agent.tool_names)
                REG-->>SUB: ToolExecutionResult
            end
        end

        SUB-->>DSP: final ChatResult
        DSP->>H: emit delegate.post {result}

        alt provider returns error
            DSP->>LLM: fallback to default provider
            DSP->>SUB: retry once
        end

        DSP-->>CV: ChatResult
        Note over CV: returns to user as<br/>final assistant message
    else no delegation
        CV->>CV: continue normal tool loop
    end
```

## hmmm some oversights

- **Cost control.** Sub-agents can pin cheaper models (`model_override`) — the orchestrator routes structured work to a smaller LLM without losing the main persona.
- **Tool least-privilege.** A sub-agent can only call tools in its `tool_names` allowlist. The registry enforces this at `execute_tool_call_async` (`tools/registry.py`).
- **One delegation per turn.** The main loop returns the sub-agent's result to the user immediately, and sub-agents can't parse `<delegate>` tags themselves — so recursion is impossible by construction.
- **Stateless sub-agents.** Sub-agents receive only the instruction string — no prior history. Forces the orchestrator to summarise context, keeps sub-agent prompts deterministic and cacheable.
- **Hot-swap via hooks.** `delegate.pre` lets you mutate the instruction before the sub-agent sees it (today: inject `profile.yml` for `resume_tailor`). Same hook can mock/cache in tests.
