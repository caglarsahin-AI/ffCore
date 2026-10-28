"""Reconciler: the `providers` and `models` tables are the only source of LiteLLM's model list
(P1, R1.4, C1). `make render-litellm` and every catalog change run it; there is no config file
model_list and no restart.

The desired state is computed from the tables, compared with LiteLLM's `/model/info`, and the
difference applied with `/model/new|update|delete`. Each deployment carries `model_info.id` =
`models.id` (the client recognises fallbacks by it, U3) and `ffcore_hash`, a digest of the
desired parameters including the decrypted key, because `/model/info` never returns the key
(U2). A row that cannot be written is not skipped silently: it is reported as a problem with a
code and logged. LiteLLM's `/config/update` is never called; it stores the master key in plain
text (K-01-0004).
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.core.egress import EgressDenied, EgressPolicy, EgressTimeout, SafeOutboundClient
from ffcore.core.secrets import decrypt_json
from ffcore.models.catalog import Model, Provider, ProviderProject, litellm_name
from ffcore.models.identity import Project
from ffcore.services.litellm_client import LiteLLMError, LiteLLMSettings, litellm_settings

log = logging.getLogger("ffcore.litellm_reconcile")

ADMIN_TIMEOUT = EgressTimeout(connect=5, read=30, total=60)
NUM_RETRIES = 2

# Driver -> (LiteLLM model prefix, upstream base URL used for the egress check and api_base).
_PUBLIC_BASE = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
}


class ReconcileProblem(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DesiredModel:
    name: str
    litellm_params: dict[str, Any] = field(repr=False)
    model_info: dict[str, Any]

    @property
    def id(self) -> str:
        return self.model_info["id"]


@dataclass
class ReconcileReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    problems: list[dict[str, str]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


def _upstream(driver: str, config: dict[str, str], model_id: str) -> tuple[str, dict[str, Any]]:
    """LiteLLM params that locate the model, without retries, timeouts or policy."""
    if driver in ("anthropic", "openai"):
        base = (config.get("base_url") or _PUBLIC_BASE[driver]).rstrip("/")
        params = {"model": f"{driver}/{model_id}", "api_key": config["api_key"]}
        if config.get("base_url"):
            params["api_base"] = base
        return base, params
    if driver == "azure_openai":
        base = config["api_base"].rstrip("/")
        return base, {
            "model": f"azure/{model_id}",
            "api_key": config["api_key"],
            "api_base": base,
            "api_version": config["api_version"],
        }
    if driver == "bedrock":
        region = config["region"]
        return f"https://bedrock-runtime.{region}.amazonaws.com", {
            "model": f"bedrock/{model_id}",
            "aws_access_key_id": config["aws_access_key_id"],
            "aws_secret_access_key": config["aws_secret_access_key"],
            "aws_region_name": region,
        }
    if driver == "openai_compatible":
        base = config["base_url"].rstrip("/")
        params = {"model": f"openai/{model_id}", "api_base": base}
        # LiteLLM's openai client needs some key; a keyless server ignores it.
        params["api_key"] = config.get("api_key") or "none"
        return base, params
    if driver == "ollama":
        # Ollama's OpenAI endpoint: the one that reads reasoning_effort (D6, PayCore llm.py).
        base = config["base_url"].rstrip("/") + "/v1"
        return base, {"model": f"openai/{model_id}", "api_base": base, "api_key": "ollama"}
    if driver == "vllm":
        base = config["base_url"].rstrip("/") + "/v1"
        params = {"model": f"hosted_vllm/{model_id}", "api_base": base}
        if config.get("api_key"):
            params["api_key"] = config["api_key"]
        return base, params
    raise ReconcileProblem("driver_not_servable", f"driver {driver} does not serve chat models")


def _per_token(pricing: dict[str, Any], key: str) -> float | None:
    value = pricing.get(key)
    return None if value is None else float(value) / 1_000_000


def desired_model(project_key: str, model: Any, provider: Any, settings: Settings) -> DesiredModel:
    """One `models` row (with its provider and decrypted config) as a LiteLLM deployment."""
    if model.upstream_api != "chat":
        raise ReconcileProblem(
            "upstream_api_unsupported", f"upstream_api={model.upstream_api} is not wired yet"
        )
    policy = model.request_policy or {}
    if policy.get("forward_unknown_params"):
        raise ReconcileProblem(
            "forward_unknown_params_unsupported",
            "LiteLLM has no per-model switch for forwarding unknown parameters",
        )
    base, params = _upstream(provider.driver, provider.config, model.model_id)
    try:
        EgressPolicy(settings).check_url(httpx2.URL(base))
    except EgressDenied as exc:
        raise ReconcileProblem(exc.code, f"upstream {exc.origin} refused") from None

    params["timeout"] = settings.llm_call_timeout_s
    params["num_retries"] = NUM_RETRIES
    if policy.get("drop_unsupported_params"):
        params["drop_params"] = True
    if policy.get("reject_params"):
        params["additional_drop_params"] = list(policy["reject_params"])
    if policy.get("extra_body"):
        # Through extra_body, not as a direct parameter: LiteLLM validates direct parameters
        # per model and refuses reasoning_effort for unknown ones (measured, v1.80.0).
        params["extra_body"] = dict(policy["extra_body"])
    limits = model.limits or {}
    for key in ("temperature", "max_tokens"):
        if limits.get(key) is not None:
            params[key] = limits[key]

    caps = model.capabilities or {}
    pricing = model.pricing or {}
    info: dict[str, Any] = {
        "id": str(model.id),
        "ffcore_managed": True,
        "ffcore_model_key": model.key,
        "supports_function_calling": bool(caps.get("tool_calls")),
        "supports_reasoning": bool(caps.get("reasoning")),
        "supports_response_schema": bool(caps.get("structured_outputs")),
        "supports_vision": "image" in (model.input_types or []),
        "max_input_tokens": limits.get("context_window"),
        "max_output_tokens": limits.get("max_output"),
        "input_cost_per_token": _per_token(pricing, "input_per_1m"),
        "output_cost_per_token": _per_token(pricing, "output_per_1m"),
        "cache_read_input_token_cost": _per_token(pricing, "cached_per_1m"),
    }
    info = {k: v for k, v in info.items() if v is not None}
    digest = json.dumps([params, info], sort_keys=True, default=str).encode()
    info["ffcore_hash"] = hashlib.sha256(digest).hexdigest()
    name = litellm_name(project_key, model.key)
    return DesiredModel(name=name, litellm_params=params, model_info=info)


async def desired_state(
    session: AsyncSession, settings: Settings
) -> tuple[list[DesiredModel], list[dict[str, str]]]:
    """Live chat models of active providers assigned to the model's project. Embedding and other
    categories never reach LiteLLM (C10 reversed)."""
    rows = await session.execute(
        select(Model, Provider, Project.key)
        .join(Provider, Provider.id == Model.provider_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            Model.deleted_at.is_(None),
            Model.is_active.is_(True),
            Model.category == "llm",
            Provider.is_active.is_(True),
        )
        .order_by(Project.key, Model.key)
    )
    links = await session.execute(select(ProviderProject.provider_id, ProviderProject.project_id))
    assigned = {(provider_id, project_id) for provider_id, project_id in links}
    desired: list[DesiredModel] = []
    problems: list[dict[str, str]] = []
    for model, provider, project_key in rows.all():
        name = litellm_name(project_key, model.key)
        try:
            if (provider.id, model.project_id) not in assigned:
                raise ReconcileProblem(
                    "provider_not_assigned", "provider is not assigned to the project"
                )
            config = decrypt_json(provider.config_encrypted, settings)
            view = _ProviderView(provider.driver, config)
            desired.append(desired_model(project_key, model, view, settings))
            pricing = model.pricing or {}
            if pricing.get("input_per_1m") is None or pricing.get("output_per_1m") is None:
                # Served, but costs read 0 until a price is entered (S3, FOLLOWUP-69).
                log.warning("pricing_missing model=%s", name)
        except ReconcileProblem as exc:
            problems.append({"model": name, "code": exc.code, "detail": exc.detail})
    return desired, problems


@dataclass(frozen=True)
class _ProviderView:
    driver: str
    config: dict[str, str] = field(repr=False)


class LiteLLMAdmin:
    """LiteLLM management API with the master key, through SafeOutboundClient (C5)."""

    def __init__(self, conf: LiteLLMSettings, settings: Settings, **client_options) -> None:
        self._conf = conf
        self._client = SafeOutboundClient(
            timeout=ADMIN_TIMEOUT, settings=settings, **client_options
        )

    async def __aenter__(self) -> "LiteLLMAdmin":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, body: Any = None, params=None) -> Any:
        if path.startswith("/config/"):
            # Stores general_settings (master key, database URL) in plain text (K-01-0004).
            raise RuntimeError("LiteLLM /config/* is never called by FFCore")
        response = await self._client.request(
            method,
            f"{self._conf.url}{path}",
            headers={"Authorization": f"Bearer {self._conf.master_key}"},
            json=body,
            params=params,
        )
        if response.status_code >= 400:
            raise LiteLLMError(response.status_code, path, _error_text(response))
        return response.json() if response.content else None

    async def model_info(self) -> list[dict[str, Any]]:
        return (await self._call("GET", "/model/info"))["data"]

    async def model_new(self, d: DesiredModel) -> None:
        await self._call("POST", "/model/new", _deployment(d))

    async def model_update(self, d: DesiredModel) -> None:
        await self._call("POST", "/model/update", _deployment(d))

    async def model_delete(self, model_id: str) -> None:
        await self._call("POST", "/model/delete", {"id": model_id})

    async def ensure_internal_key(self) -> bool:
        """Registers LITELLM_INTERNAL_KEY once (A4: the backend's only key). True if created."""
        key = self._conf.internal_key
        try:
            await self._call("GET", "/key/info", params={"key": key})
            return False
        except LiteLLMError as exc:
            if exc.status not in (400, 404):
                raise
        body = {"key": key, "key_alias": "ffcore-backend", "metadata": {"ffcore": True}}
        await self._call("POST", "/key/generate", body)
        return True


def _deployment(d: DesiredModel) -> dict[str, Any]:
    return {"model_name": d.name, "litellm_params": d.litellm_params, "model_info": d.model_info}


def _error_text(response: httpx2.Response) -> str:
    try:
        error = response.json().get("error") or response.json().get("detail")
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(error, dict):
        return str(error.get("message", ""))[:300]
    return str(error)[:300]


async def apply(
    admin: LiteLLMAdmin, desired: list[DesiredModel], dry_run: bool = False
) -> ReconcileReport:
    """Makes /model/info equal to `desired`. Order: create and update first, delete last, so a
    replaced model never leaves a gap. `dry_run` only reports the difference."""
    report = ReconcileReport()
    current = {m["model_info"]["id"]: m for m in await admin.model_info()}
    wanted = {d.id: d for d in desired}
    for model_id, d in wanted.items():
        existing = current.get(model_id)
        if existing is None:
            if not dry_run:
                await admin.model_new(d)
            report.created.append(d.name)
        elif (
            existing["model_info"].get("ffcore_hash") != d.model_info["ffcore_hash"]
            or existing["model_name"] != d.name
        ):
            if not dry_run:
                await admin.model_update(d)
            report.updated.append(d.name)
    for model_id, existing in current.items():
        if model_id not in wanted:
            if not existing["model_info"].get("ffcore_managed"):
                log.warning("litellm_unmanaged_model_removed name=%s", existing["model_name"])
            if not dry_run:
                await admin.model_delete(model_id)
            report.deleted.append(existing["model_name"])
    return report


async def reconcile(
    session: AsyncSession, settings: Settings, dry_run: bool = False, **client_options
) -> ReconcileReport:
    desired, problems = await desired_state(session, settings)
    async with LiteLLMAdmin(litellm_settings(settings), settings, **client_options) as admin:
        if not dry_run:
            await admin.ensure_internal_key()
        report = await apply(admin, desired, dry_run)
    report.problems = problems
    for problem in problems:
        log.error("litellm_model_not_written model=%s code=%s", problem["model"], problem["code"])
    log.info(
        "litellm_reconciled created=%d updated=%d deleted=%d problems=%d",
        len(report.created),
        len(report.updated),
        len(report.deleted),
        len(problems),
    )
    return report
