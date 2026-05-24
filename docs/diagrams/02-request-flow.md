# 02 — Request Flow

End-to-end sequence of `POST /api/sessions/{sid}/messages` — from HTTP in to assistant reply out. Covers the main (non-delegating) loop. Delegation path is in `03-agent-orchestration.md`.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant R as routers/messages.py
    participant CV as services/conversation.py
    participant ST as store/store.py
    participant LP as agents/loop.py<br/>(tool_step)
    participant SP as agents/system_prompt.py
    participant H as hooks/HookRegistry
    participant MEM as memory/MemoryStore
    participant LLM as providers/<br/>OpenRouter|HF
    participant REG as tools/registry.py
    participant T as tool handler<br/>(e.g. search_jobs)

    U->>R: POST /messages {content}
    R->>CV: answer_user_message(sid, msg)
    CV->>ST: create_message(role=user)
    CV->>ST: list_context_messages(sid)
    ST-->>CV: history[]
    CV->>SP: assistant_system_prompt(catalog)
    SP-->>CV: system_prompt

    loop tool loop (≤ max_iterations)
        CV->>H: emit turn.start / iteration
        CV->>LP: tool_step(provider, sysprompt, turns)
        LP->>H: emit model.pre_call
        H->>MEM: list(session_id) ▸ inject into prompt
        MEM-->>H: memories
        H-->>LP: enriched payload
        LP->>LLM: complete(history, sysprompt)
        LLM-->>LP: ChatResult.content
        LP->>H: emit model.post_call

        alt content has <tool_call>
            LP->>REG: parse_tool_call(content)
            LP->>H: emit tool.pre_call
            LP->>REG: execute_tool_call_async(req)
            REG->>T: await handler(config, args, sid)
            T-->>REG: output str
            REG-->>LP: ToolExecutionResult
            LP->>H: emit tool.post_call
            LP-->>CV: step{request, result}
            CV->>CV: append_tool_turns(turns, step)
            Note over CV: continues loop with<br/>assistant + tool turns appended
        else final answer
            LP-->>CV: step{request=None}
            Note over CV: exits loop
        end
    end

    CV->>ST: create_message(role=assistant, content)
    CV->>H: emit turn.end (reason)
    CV-->>R: AssistantResponseResult
    R-->>U: 200 {message}
```

## Key invariants

- **One LLM round-trip per iteration.** `tool_step` makes exactly one `provider.complete()` call. The loop iterates until the model emits no tool call OR `max_iterations` is hit.
- **Tool results are system turns.** `append_tool_turns` adds an `assistant` turn (the raw tool call) followed by a `system` turn (`Tool result (name, ok|error): ...`). The next iteration sees both.
- **Hooks can short-circuit.** A handler raising `HookHalt(payload)` replaces the natural result (used for caching, rate-limiting, mocking).
- **Async-aware tool dispatch.** `execute_tool_call_async` (`tools/registry.py`) inspects handler return; awaits coroutines, returns sync results as-is. Lets Playwright-based handlers run on the FastAPI event loop without `asyncio.run()`.
- **Failures are visible, not fatal.** A tool exception becomes `ToolExecutionResult(ok=False, output=str(err))` — the model sees the error and decides next step.

## Persisted records are written

| Table | Written by | When |
|---|---|---|
| `sessions` | `Store.create_session` | router POST `/api/sessions` |
| `messages` (user) | `Store.create_message` | `answer_user_message` start |
| `messages` (assistant) | `Store.create_message` | `answer_user_message` end |
| `tool_calls` | `tool.post_call` hook handler | every successful/failed tool exec |
| `memories` | `remember` / `forget` tool handlers | on demand by the model |
