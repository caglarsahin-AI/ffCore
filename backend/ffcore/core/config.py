"""Process settings read from the environment (.env.example documents every name, C12).

Profile differences are configuration values, never `if profile` branches (PLAN 5).
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CommaList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    deploy_profile: Literal["llmaas", "airgap"]
    # airgap model server (D8); chooses the seed's provider block. None where no local model runs.
    inference_backend: Literal["ollama", "vllm"] | None = None
    offline: bool
    # Contains the database password, so it is a secret too.
    database_url: SecretStr | None = None

    # Internal service account (mcp-search, workers). Bearer token, compared in constant time.
    service_token: SecretStr = Field(min_length=32)
    # HS256 key for X-On-Behalf-Of tokens; separate from service_token so they rotate independently.
    obo_jwt_secret: SecretStr = Field(min_length=32)
    # Audience this backend accepts in X-On-Behalf-Of tokens addressed to itself.
    obo_audience: str = "ffcore-backend"

    # Hosts external calls may reach (exact name or "*.suffix"). Empty means no external host.
    egress_allowlist: CommaList = []
    # Hosts or CIDRs that may resolve to private addresses (compose service names, internal APIs).
    allowed_internal_hosts: CommaList = []

    # --- 03a ---
    # HS256 key for console session tokens; separate from obo_jwt_secret.
    secret_key: SecretStr = Field(min_length=32)
    # Fernet key (urlsafe base64 of 32 bytes) for provider configurations at rest.
    fernet_key: SecretStr
    # The one embedding dimension of this installation; models must measure the same (P5).
    embed_dim: int = Field(gt=0)
    session_ttl_s: int = Field(default=28800, gt=0)
    # Only for plain-http local debugging; browsers treat localhost as secure anyway.
    session_cookie_secure: bool = True
    # Origins the console is served from (scheme://host[:port]); cookie mutations from any
    # other origin are refused (C6). Empty: only requests without a foreign Origin pass.
    console_origins: CommaList = []

    # --- 01 ---
    # LiteLLM proxy on the internal network (e.g. http://litellm:4000); its host must be in
    # ALLOWED_INTERNAL_HOSTS. Unset means no model calls: callers get an explicit error.
    litellm_url: str | None = None
    # Management key: only the reconciler uses it (/model/new|update|delete, /key/generate).
    litellm_master_key: SecretStr | None = None
    # The one key the backend sends model calls with (A4: no per-project team or virtual keys).
    litellm_internal_key: SecretStr | None = None
    # --- 02 ---
    # Root log level; third-party HTTP and telemetry loggers stay at WARNING or above.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Langfuse on the internal network (host in ALLOWED_INTERNAL_HOSTS). All three or none:
    # none means tracing off (said once); some but not all stops the start-up.
    langfuse_host: str | None = None
    # Half of a key pair: kept out of reprs like the secret half.
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None

    # Per-call model timeout (R1.5): llmaas 60, airgap cpu 600, airgap gpu 120. Run timeout is
    # separate (06a run_timeout_s).
    llm_call_timeout_s: int = Field(default=60, gt=0)

    # --- 04a knowledge base ---
    # /readyz C13 check: the context Ollama is started with versus the models' context_tokens.
    inference_backend: Literal["ollama", "vllm"] | None = None
    ollama_context_length: int | None = Field(default=None, gt=0)
    # Ingest queue (arq); contains the Redis password, so it is a secret.
    redis_url: SecretStr | None = None
    # Queue name (C10 name `ingest`); a setting so test runs can use their own (K-04a-0012).
    arq_queue_ingest: str = "ingest"
    # Defaults are PayCore's measured values (KARARLAR "04a kararları", K-04a-0002).
    vector_backend: Literal["pgvector", "qdrant"] = "pgvector"
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    # The one embedding model of this installation (P5); in-process FlagEmbedding (C10).
    embed_model: str = "BAAI/bge-m3"
    embed_batch_size: int = Field(default=64, gt=0)
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_min_score: float = Field(default=0.1, ge=0, le=1)
    # Hybrid candidates handed to the reranker (and logged in kb_queries.candidates, C12).
    retrieval_candidates: int = Field(default=30, gt=0)
    # Deterministic stand-in models for tests (FAKE_EMBED=1); never a silent fallback: the
    # setting is explicit and /readyz reports it.
    fake_embed: bool = False
    allowed_languages: CommaList = ["tr", "en"]
    knowledge_storage_dir: str = "/data/storage"
    convert_timeout_seconds: int = Field(default=600, gt=0)
    # A fresh converter worker's spawn and imports, bounded apart from the file (FOLLOWUP-97).
    convert_worker_start_timeout_seconds: int = Field(default=60, gt=0)
    convert_parallelism: int = Field(default=4, gt=0)
    # Converter process limits (review r1 MAJOR-5). Address space: a worker with Docling and
    # PaddleOCR loaded peaked at 6.6 GB virtual / 2.3 GB resident on the samples (2026-10-29);
    # the limit leaves room for both models plus a large file. CPU per file: six busy cores for
    # the whole default timeout; the wall-clock timeout stays the main stop.
    convert_memory_limit_mb: int = Field(default=10240, gt=0)
    convert_cpu_limit_seconds: int = Field(default=3600, gt=0)
    # One POST /documents request (all its files), checked before the body is parsed: the
    # largest single file Kapı 0 accepts (scope.MAX_BYTES, 500 MiB) plus form overhead.
    upload_max_request_bytes: int = Field(default=516 * 1024 * 1024, gt=0)
    # Where the ingest worker reaches POST /internal/embed (the API loads the model, C10).
    internal_api_url: str = "http://backend:8000"
    # --- 05a: tools ---
    # A tool result longer than this reaches the model cut, ending in "[truncated: N/M chars]"
    # (C13); the call log says truncated=true.
    tool_result_max_chars: int = Field(default=20000, gt=0)
    # Whole MCP call (connect, initialize, call); an action's own timeout_s wins.
    mcp_call_timeout_s: int = Field(default=30, gt=0)
    # mcp-sql: rows returned at most (the rest cut and said) and the statement timeout.
    sql_max_rows: int = Field(default=500, gt=0)
    sql_timeout_s: int = Field(default=20, gt=0)
    # mcp-sql's demo database (13a, K-05a-0002 S5): the read-only login user's URL, and the
    # password `make seed-sql-demo` gives that user (both in .env, written by the user).
    sql_demo_database_url: SecretStr | None = None
    agent_demo_db_password: SecretStr | None = None
    # --- 07: approvals ---
    # A pending approval expires after this many minutes and its run is closed (approval_expired).
    approval_ttl_min: int = Field(default=60, gt=0)
    # A pending approval older than this is reported (approval_pending_age); 03c alerts later.
    approval_alert_age_min: int = Field(default=30, gt=0)
    # Test hooks for end-to-end tests (POST /api/v1/internal/approvals/sweep, FOLLOWUP-111): off
    # by default and in every deployment; only a test stack sets FFCORE_TEST_HOOKS=1.
    ffcore_test_hooks: bool = False

    # --- 06a agent runtime (profile values, PLAN 2b; .env.example lists each profile) ---
    # Concurrent model calls (C10): airgap cpu 1, gpu the server's parallelism, llmaas the
    # provider's concurrency.
    llm_slots: int = Field(default=4, gt=0)
    # When background jobs (exams, judges) may take the slot: "HH:MM-HH:MM" or empty (always).
    # airgap cpu "19:00-07:00" with weekends all day; gpu and llmaas empty (A8).
    background_window: str = ""
    background_window_weekends: bool = False
    background_window_tz: str = "Europe/Istanbul"
    # Run timeout when the agent sets none (C2): llmaas 120, airgap cpu 900, airgap gpu 300.
    run_timeout_s: int = Field(default=120, gt=0)
    # Run queues (C10 names); settings so test runs can use their own, like arq_queue_ingest.
    arq_queue_interactive: str = "llm-interactive"
    arq_queue_background: str = "llm-background"
    sse_keepalive_s: float = Field(default=10, gt=0)
    # Live event stream per run in Redis; past it a reconnecting client replays from run_events.
    run_event_stream_ttl_s: int = Field(default=86400, gt=0)
    # A running run nobody listens to stops at its next step after this long (K-06a-0002 S8).
    run_abandon_grace_s: int = Field(default=120, gt=0)
    # LangSmith is LangChain's cloud tracing: switching it on would send prompts outside. Read
    # only to refuse it (K-06a-0002 S1); Langfuse is the trace store.
    langsmith_tracing: bool = False
    langchain_tracing_v2: bool = False

    # --- 09 evaluation (profile values, PLAN 2b; .env.example lists each profile) ---
    # Default pass threshold of a new suite: llmaas 0.85, airgap 0.8. None: a suite must name
    # its own (no hidden default, ARCH-10).
    eval_pass_threshold: float | None = Field(default=None, gt=0, le=1)
    # Model key (in the suite's project) of the llm_judge scorer: llmaas a strong provider
    # model, airgap the local model. None: suites with llm_judge are refused.
    eval_judge_model: str | None = None
    # Seconds between exam advancer ticks (arq cron on the background worker, K-09-0007 S4);
    # divides 60 and stays under RUN_ABANDON_GRACE_S (the advancer keeps item runs listened).
    eval_advance_interval_s: int = Field(default=15, gt=0, le=60)

    # --- 03c governance ---
    # Wrong API keys from one client address per minute before 429 too_many_auth_failures.
    api_key_auth_failures_per_min: int = Field(default=20, gt=0)
    # last_used_at is written at most once per this many seconds per key (write buffer).
    api_key_last_used_flush_s: int = Field(default=60, ge=0)
    # Retention (03c, R2.2): the daily job only counts while this is true (the "dry run"
    # default); POST /retention/run removes regardless. Old audit partitions are dropped only
    # when RETENTION_AUDIT_DROP_ENABLED is true as well (K-03c-0011, two flags).
    retention_dry_run: bool = True
    retention_audit_drop_enabled: bool = False
    retention_batch: int = Field(default=5000, gt=0)
    # service_down fires when /readyz has failed this long without a break (brief R9.1: 5 min).
    alert_service_down_s: int = Field(default=300, gt=0)

    @field_validator(
        "egress_allowlist", "allowed_internal_hosts", "allowed_languages", mode="before"
    )
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value

    @field_validator("console_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "ollama_context_length",
        "inference_backend",
        "qdrant_url",
        "qdrant_api_key",
        "eval_pass_threshold",
        "eval_judge_model",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # Compose passes unset optional variables as "" (${VAR:-}); that means "not set".
        return None if value == "" else value

    @model_validator(mode="after")
    def _eval_advance_interval(self) -> "Settings":
        if 60 % self.eval_advance_interval_s:
            raise ValueError(
                "eval_advance_interval_invalid: EVAL_ADVANCE_INTERVAL_S must divide 60"
            )
        if self.eval_advance_interval_s >= self.run_abandon_grace_s:
            raise ValueError(
                "eval_advance_interval_invalid: EVAL_ADVANCE_INTERVAL_S must be below "
                "RUN_ABANDON_GRACE_S, or exam runs are abandoned between two ticks"
            )
        return self

    @model_validator(mode="after")
    def _no_langsmith(self) -> "Settings":
        if self.langsmith_tracing or self.langchain_tracing_v2:
            raise ValueError(
                "langsmith_tracing_forbidden: LANGSMITH_TRACING / LANGCHAIN_TRACING_V2 would "
                "send prompts to LangSmith; FFCore traces to Langfuse only"
            )
        return self

    @field_validator("fernet_key")
    @classmethod
    def _valid_fernet_key(cls, value: SecretStr) -> SecretStr:
        from cryptography.fernet import Fernet

        try:
            Fernet(value.get_secret_value())
        except (ValueError, TypeError):
            # The message names the field only; the value never reaches logs.
            raise ValueError("FERNET_KEY must be urlsafe base64 of 32 bytes") from None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
