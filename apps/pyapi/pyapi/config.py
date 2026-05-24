from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class ChatConfig:
    provider: str
    model: str
    openrouter_api_key: str
    openrouter_base_url: str
    huggingface_api_key: str
    huggingface_base_url: str
    http_referer: str
    app_title: str


@dataclass(frozen=True)
class ContextConfig:
    max_response_tokens: int
    max_history_messages: int
    max_memory_chars: int
    llm_call_throttle_seconds: float = 0.0


@dataclass(frozen=True)
class ToolConfig:
    enabled: bool
    database_url: str
    workspace_root: Path
    max_iterations: int
    max_output_chars: int
    internet_enabled: bool
    network_timeout_seconds: float
    max_network_bytes: int
    crawl_max_pages: int


@dataclass(frozen=True)
class AgentLLM:
    provider: str
    model: str


@dataclass(frozen=True)
class Config:
    addr: str
    database_url: str
    frontend_origins: list[str]
    chat: ChatConfig
    context: ContextConfig
    tools: ToolConfig
    agents: dict[str, AgentLLM]

    @property
    def host(self) -> str:
        if self.addr.startswith(":"):
            return "127.0.0.1"
        return self.addr.rsplit(":", 1)[0]

    @property
    def port(self) -> int:
        return int(self.addr.rsplit(":", 1)[-1])


AGENT_LLM_NAMES: tuple[str, ...] = (
    "orchestrator",
    "resume_tailor",
    "job_scout",
    "applier",
    "tracker",
    "context_summarizer",
    "scrape_data_summarizer",
)


def load_config() -> Config:
    dotenv_path = load_dotenv_upwards()
    provider = env("DEFAULT_CHAT_PROVIDER", "openrouter").lower()
    model = chat_model()
    workspace_root = resolve_path_env("TOOL_WORKSPACE_ROOT", "../..", dotenv_path.parent if dotenv_path else Path.cwd())

    return Config(
        addr=env("APP_ADDR", ":8080"),
        database_url=env("DATABASE_URL", "file:../../data/chatbot.sqlite"),
        frontend_origins=split_csv(env("FRONTEND_ORIGINS", env("FRONTEND_ORIGIN", "http://localhost:5173"))),
        chat=ChatConfig(
            provider=provider,
            model=model,
            openrouter_api_key=env("OPENROUTER_API_KEY", ""),
            openrouter_base_url=env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
            huggingface_api_key=env("HUGGINGFACE_API_KEY", env("HF_TOKEN", "")),
            huggingface_base_url=env("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1").rstrip("/"),
            http_referer=provider_http_referer(),
            app_title=provider_app_title(),
        ),
        context=ContextConfig(
            max_response_tokens=int_env("MAX_RESPONSE_TOKENS", 2000),
            max_history_messages=max(1, int_env("MAX_HISTORY_MESSAGES", 30)),
            max_memory_chars=max(0, int_env("MAX_MEMORY_CHARS", 2000)),
            llm_call_throttle_seconds=max(0.0, float_env("LLM_CALL_THROTTLE_SECONDS", 0.0)),
        ),
        tools=ToolConfig(
            enabled=bool_env("TOOLS_ENABLED", False),
            database_url=env("DATABASE_URL", "file:../../data/chatbot.sqlite"),
            workspace_root=workspace_root,
            max_iterations=max(1, int_env("MAX_TOOL_ITERATIONS", 3)),
            max_output_chars=max(1000, int_env("MAX_TOOL_OUTPUT_CHARS", 12000)),
            internet_enabled=bool_env("INTERNET_TOOLS_ENABLED", False),
            network_timeout_seconds=max(1.0, float_env("TOOL_NETWORK_TIMEOUT_SECONDS", 10.0)),
            max_network_bytes=max(1000, int_env("MAX_TOOL_NETWORK_BYTES", 300000)),
            crawl_max_pages=max(1, int_env("TOOL_CRAWL_MAX_PAGES", 5)),
        ),
        agents=load_agent_llms(provider, model),
    )


def load_agent_llms(default_provider: str, default_model: str) -> dict[str, AgentLLM]:
    resolved: dict[str, AgentLLM] = {}
    for name in AGENT_LLM_NAMES:
        raw = env(f"{name.upper()}_LLM", "").strip()
        resolved[name] = parse_agent_llm(raw, default_provider, default_model)
    return resolved


def parse_agent_llm(raw: str, default_provider: str, default_model: str) -> AgentLLM:
    if not raw:
        return AgentLLM(provider=default_provider, model=default_model)
    if "|:" not in raw:
        return AgentLLM(provider=default_provider, model=raw)
    provider_part, model_part = raw.split("|:", 1)
    provider_part = provider_part.strip().lower() or default_provider
    model_part = model_part.strip().lstrip(":").strip() or default_model
    return AgentLLM(provider=provider_part, model=model_part)


def chat_model() -> str:
    return env("CHAT_MODEL", "meta-llama/llama-3.1-8b-instruct:free")


def provider_http_referer() -> str:
    return env("PROVIDER_HTTP_REFERER", env("FRONTEND_ORIGIN", "http://localhost:5173"))


def provider_app_title() -> str:
    return env("PROVIDER_APP_TITLE", "Career Pilot")


def find_config_dir(marker: str = "agents.yml") -> Path:
    return find_repo_dir("config", marker)


def find_migrations_dir(marker: str = "001_init.sql") -> Path:
    return find_repo_dir("migrations", marker)


def find_repo_root() -> Path:
    return find_config_dir().parent


def find_data_dir() -> Path:
    return find_repo_root() / "data"


def find_repo_dir(dirname: str, marker: str) -> Path:
    start = Path(__file__).resolve().parent
    for path in [start, *start.parents]:
        candidate = path / dirname
        if (candidate / marker).is_file():
            return candidate
    raise RuntimeError(f"{dirname}/{marker} not found upward from {start}")


def load_dotenv_upwards(filename: str = ".env") -> Path | None:
    directory = Path.cwd()
    for path in [directory, *directory.parents]:
        dotenv = path / filename
        if dotenv.exists():
            load_dotenv(dotenv)
            return dotenv
    return None


def load_dotenv(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ[key] = value


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def env(key: str, fallback: str) -> str:
    return os.environ.get(key) or fallback


def int_env(key: str, fallback: int) -> int:
    try:
        return int(os.environ.get(key, ""))
    except ValueError:
        return fallback


def float_env(key: str, fallback: float) -> float:
    try:
        return float(os.environ.get(key, ""))
    except ValueError:
        return fallback


def bool_env(key: str, fallback: bool) -> bool:
    value = os.environ.get(key, "")
    if not value:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_path_env(key: str, fallback: str, base_dir: Path) -> Path:
    raw_value = env(key, fallback)
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()
