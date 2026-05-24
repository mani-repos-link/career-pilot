# 05 — Data Model (Postgres)

Single Postgres 18 instance with pgvector extensions available (unused at MVP — kept for future similar-job matching and geo queries). Schema is split into three concerns: **chat substrate**, **observability**, **job-hunt domain**.

```mermaid
erDiagram
    sessions ||--o{ messages : "has"
    sessions ||--o{ memories : "scopes (session)"
    sessions ||--o{ tool_calls : "logs"
    sessions ||--o{ agent_runs : "logs"

    messages ||--o{ messages : "parent_message_id"
    messages ||--o{ messages : "active_response_id"
    messages ||--o{ tool_calls : "executed during"
    messages ||--o{ agent_runs : "triggered by"

    jobs ||--o{ jds : "extracted to"
    jobs ||--o{ applications : "applied to"
    jobs ||--o{ resumes : "tailored for"
    resumes ||--o{ applications : "submitted with"

    sessions {
        text id PK
        text title
        timestamptz created_at
        timestamptz updated_at
        timestamptz archived_at "soft delete"
    }

    messages {
        text id PK
        text session_id FK
        text role "user|assistant|system|tool"
        text content
        text provider
        text model
        text parent_message_id FK "branching"
        text active_response_id FK "regen variants"
        int token_count
        timestamptz created_at
    }

    memories {
        text id PK
        text scope "session|global"
        text session_id FK "null when global"
        text key
        text content
        timestamptz created_at
        timestamptz updated_at
    }

    tool_calls {
        text id PK
        text session_id FK
        text message_id FK
        text agent_name
        text tool_name
        jsonb args
        jsonb result
        bool ok
        int duration_ms
        timestamptz created_at
    }

    agent_runs {
        text id PK
        text session_id FK
        text parent_message_id FK
        text agent_name
        text instruction
        text output
        text provider
        text model
        text status "running|ok|error"
        text error
        timestamptz started_at
        timestamptz finished_at
    }

    jobs {
        text id PK
        text portal "linkedin|indeed|..."
        text external_id "UNIQUE per portal"
        text url
        text title
        text company
        text location
        numeric salary_min
        numeric salary_max
        text salary_currency
        timestamptz posted_at
        timestamptz first_seen_at
        jsonb raw_meta
    }

    jds {
        text id PK
        text job_id FK
        text source_url
        text raw_text
        jsonb parsed
        timestamptz fetched_at
    }

    resumes {
        text id PK
        text slug
        text job_id FK
        text markdown_path
        text html_path
        text pdf_path
        text cover_letter_md
        text cover_letter_pdf
        timestamptz created_at
    }

    applications {
        text id PK
        text job_id FK
        text resume_id FK
        text status "planned|draft|submitted|responded|interview|offer|rejected|withdrawn"
        timestamptz applied_at
        timestamptz last_updated
        text notes
    }
```

## Store CRUD surface (`store/store.py`)

```
Sessions:  list · create · get · update_title · delete (archive)
Messages:  list · list_context · list_page · create · set_active_response
Memories:  list(sid, include_global) · get · upsert · delete   [MemoryStore]
Jobs/JDs/Resumes/Applications: written by tool handlers, read by tracker sub-agent
```
