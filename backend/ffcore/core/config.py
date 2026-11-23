"""Process settings read from the environment (.env.example documents every name, C12).

Profile differences are configuration values, never `if profile` branches (PLAN 5).
"""

import os
from datetime import date
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from ffcore.evaluation.ticks import TICK_PLAN_S

CommaList = Annotated[list[str], NoDecode]
# 17: email, UPN or account name; `{login}` is the escaped value the user typed.
LDAP_DEFAULT_FILTER = "(|(mail={login})(userPrincipalName={login})(sAMAccountName={login}))"


def _plain_proxy_origin(value: str) -> str:
    """Only http://host:port: no credentials (the URL would leak them into logs), no path,
    no TLS to the proxy (an internal service), no other scheme."""
    if not value:
        return value
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        port = None
    if (
        parts.scheme != "http"
        or not parts.hostname
        or port is None
        or parts.username is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError(
            "egress_proxy_url_invalid: EGRESS_PROXY_URL must be http://<host>:<port> "
            "(no credentials, path or query) or empty"
        )
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"http://{host}:{port}"


# FOLLOWUP-208: the one definition of EGRESS_PROXY_URL; every settings class the egress client
# reads (Settings, services/mcp_server_common.McpServiceSettings) declares a field of this type
# (K-HKE-0010: a class without it broke mcp-sql).
EgressProxyUrl = Annotated[str, AfterValidator(_plain_proxy_origin)]


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
    # FOLLOWUP-208: forward proxy for external hosts (http://host:port; the egress profile sets
    # http://egress-proxy:3128). Empty: the backend dials external hosts itself (pinned).
    egress_proxy_url: EgressProxyUrl = ""

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
    # /readyz C13 check: the context Ollama is started with versus the models'
    # `limits.context_window` (triage-2).
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
    # 04b-2 D3: Turkish layer A (circumflex folding) on silver and queries; off by
    # default. Switching it needs `make reindex LAYER=silver FULL=1` (search is 409 until then).
    text_normalize_tr: bool = False
    # 04b-2 D4: video transcription. This build has no transcriber (faster-whisper is a separate
    # class-C PR), so True stops start-up; off, a video is Kapı 0 `video_disabled`.
    video_transcript_enabled: bool = False
    # Hybrid candidates handed to the reranker (and logged in kb_queries.candidates, C12).
    retrieval_candidates: int = Field(default=30, gt=0)
    # Deterministic stand-in models for tests (FAKE_EMBED=1); never a silent fallback: the
    # setting is explicit and /readyz reports it.
    fake_embed: bool = False
    allowed_languages: CommaList = ["tr", "en"]
    knowledge_storage_dir: str = "/data/storage"
    # 16 data sources. Network-folder sources read only below this directory (C5): a source's
    # root is relative to it, `..`, absolute paths and symlinks out are refused.
    fs_sources_base: str = "/data/sources"
    # Safe delete (D4): the largest share of a source's items one run may delete; above it the
    # run is `prune_refused` and deletes nothing unless started with force_prune (admin).
    prune_max_ratio: float = Field(default=0.2, gt=0, le=1)
    # Kapı 0 source-date rule for attachments: older ones are not downloaded (`stale`). Unset
    # means no date rule (the measured PayCore value 2021-01-01 is an installation choice).
    attachment_min_date: date | None = None
    # Queue of the sync worker (C10 name `sync`); a setting so test runs can use their own.
    arq_queue_sync: str = "sync"
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
    # 08 tam 1b: the Turkish NER model of this installation (HF repo + commit), loaded only by
    # the API process; workers call POST /api/v1/internal/guardrails/ner. Unset: a policy with
    # `engine: ner` and the `pii_ner` ingest filter fail loudly (ner_not_configured), nothing
    # falls back to regex.
    ner_model: str | None = None
    ner_revision: str | None = None
    # --- 05a: tools ---
    # A tool result longer than this reaches the model cut, ending in "[truncated: N/M chars]"
    # (C13); the call log says truncated=true.
    tool_result_max_chars: int = Field(default=20000, gt=0)
    # Whole MCP call (connect, initialize, call); an action's own timeout_s wins.
    mcp_call_timeout_s: int = Field(default=30, gt=0)
    # 05b: a published OpenAPI server's upstream answer larger than this is refused
    # (upstream_response_too_large), never cut silently; the result itself then follows C13.
    mcp_upstream_max_bytes: int = Field(default=1_048_576, gt=0)
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
    # Upper bound of items x repeat in one exam (each is a billed background run); more: 422
    # eval_too_many_runs at start (09-1 r1 MINOR-2).
    eval_max_item_runs: int = Field(default=500, gt=0)
    # Judge calls one advancer tick may make for one exam; the rest wait for the next tick, so a
    # tick stays short (09-1 r1 MAJOR-2).
    eval_judge_calls_per_tick: int = Field(default=20, gt=0)
    # Planned length of one judge call (09-1 r4 decision, correction): what a tick plans with,
    # not the hard limit (LLM_CALL_TIMEOUT_S stays that). At most the usable window of a tick
    # (evaluation.ticks.TICK_PLAN_S, r5 MAJOR-r5-1); a CPU judge (airgap) sets its own.
    eval_judge_call_s: int = Field(default=60, gt=0, le=TICK_PLAN_S)

    # --- 14: user memory ---
    # Extraction candidates below this confidence are not written (brief 14: llmaas 0.6,
    # airgap 0.7 for the local model; a profile value in .env.example, not an `if profile`).
    memory_min_confidence: float = Field(default=0.6, ge=0, le=1)

    # --- 17: directory sign-in (LDAP / Active Directory bind; OIDC in 17-2) ---
    # Who may sign in with a local password: all, superadmin_only or off. A superadmin always
    # can (recovery account), whatever the value.
    local_login: Literal["all", "superadmin_only", "off"] = "all"
    # Unset: LDAP sign-in is off. ldaps:// is required; ldap:// only with LDAP_ALLOW_PLAINTEXT.
    ldap_url: str | None = None
    ldap_allow_plaintext: bool = False
    # Service account that searches the directory (the user's own DN then binds).
    ldap_bind_dn: str | None = None
    ldap_bind_password: SecretStr | None = None
    ldap_user_base: str | None = None
    # `{login}` is replaced by the escaped value the user typed.
    ldap_user_filter: str = LDAP_DEFAULT_FILTER
    ldap_group_attr: str = "memberOf"
    # The stable account id: objectGUID (Active Directory) or entryUUID (OpenLDAP); explicit,
    # never guessed (ARCH-10).
    ldap_id_attr: str = "objectGUID"
    # Enterprise CA bundle for ldaps (12 PENDING_ENV); unset: the system trust store.
    ldap_ca_file: str | None = None
    # Connect and each directory answer.
    ldap_timeout_s: int = Field(default=10, gt=0)
    # A new directory account joins this project as user/read (a project key); unset: none.
    default_project_for_new_users: str | None = None
    # Channel users (15) without an account get one from the directory only when true.
    auto_provision_from_channels: bool = False
    # OIDC accounts with no sign-in for this many days are deactivated by identity_sync.
    oidc_inactive_after_days: int = Field(default=90, gt=0)

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

    @field_validator("ldap_user_filter", mode="before")
    @classmethod
    def _filter_default(cls, value: object) -> object:
        # Compose passes an unset LDAP_USER_FILTER as "" (its default syntax cannot hold `}`).
        return LDAP_DEFAULT_FILTER if value == "" else value

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
        "attachment_min_date",
        "ldap_url",
        "ldap_bind_dn",
        "ldap_bind_password",
        "ldap_user_base",
        "ldap_ca_file",
        "default_project_for_new_users",
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
    def _video_needs_a_transcriber(self) -> "Settings":
        if self.video_transcript_enabled:
            raise ValueError(
                "video_transcriber_unavailable: VIDEO_TRANSCRIPT_ENABLED=true needs a video "
                "transcriber, and this build has none; leave it false (videos are recorded as "
                "video_disabled and can be reconverted later with the video preset)"
            )
        return self

    @model_validator(mode="after")
    def _ldap_coherent(self) -> "Settings":
        """17: a half-configured directory stops the start-up with the missing names; the
        password never appears in the message."""
        if self.ldap_url is None:
            return self
        scheme = urlsplit(self.ldap_url).scheme.lower()
        if scheme not in ("ldaps", "ldap") or not urlsplit(self.ldap_url).hostname:
            raise ValueError("ldap_url_invalid: LDAP_URL must be ldaps://host[:port]")
        if scheme == "ldap" and not self.ldap_allow_plaintext:
            raise ValueError(
                "ldap_plaintext_forbidden: LDAP_URL is ldap:// (passwords in clear text); use "
                "ldaps:// or set LDAP_ALLOW_PLAINTEXT=1 for a test directory"
            )
        missing = [
            name
            for name, value in (
                ("LDAP_BIND_DN", self.ldap_bind_dn),
                ("LDAP_BIND_PASSWORD", self.ldap_bind_password),
                ("LDAP_USER_BASE", self.ldap_user_base),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"ldap_incomplete: LDAP_URL is set but {', '.join(missing)} not")
        if "{login}" not in self.ldap_user_filter:
            raise ValueError("ldap_filter_invalid: LDAP_USER_FILTER must contain {login}")
        if self.ldap_ca_file is not None and not os.path.isfile(self.ldap_ca_file):
            raise ValueError(
                "ldap_ca_file_missing: LDAP_CA_FILE does not name a file in this container "
                "(mount the corporate CA bundle, docs/kimlik.md)"
            )
        return self

    @property
    def ldap_enabled(self) -> bool:
        return self.ldap_url is not None

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
