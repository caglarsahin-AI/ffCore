"""First-install seed of providers and models (brief 01, P1/P6): deploy/seed/models.<profile>.yaml.

The profile difference is the seed file, not code (PLAN 5): `seed-models` reads the file of
DEPLOY_PROFILE. Rows that already exist (provider key, live model key in the project) are left
unchanged; after the first install the console owns them. Secret fields are only `${VAR}`
references, resolved here and stored encrypted (core/secrets.py). Every refusal is an error with
the reason; the only skip is an optional provider with none of its variables set, and it is
reported. Upstream addresses pass the same egress rules as the reconciler, so OFFLINE=true and
the airgap seed cannot point a model, chat-fallback included, outside the network.
"""

import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2
import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.schemas import ModelCreate
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import Settings
from ffcore.core.egress import EgressDenied, EgressPolicy
from ffcore.core.errors import ApiError
from ffcore.core.secrets import encrypt_json
from ffcore.models.catalog import Model, Provider, ProviderProject
from ffcore.models.identity import Project
from ffcore.services import providers as drivers
from ffcore.services.litellm_reconcile import ReconcileProblem, _upstream

_REF = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")
SEED_DIR = Path("deploy/seed")


class SeedError(Exception):
    pass


@dataclass
class SeedReport:
    providers_created: list[str] = field(default_factory=list)
    providers_existing: list[str] = field(default_factory=list)
    models_created: list[str] = field(default_factory=list)
    models_existing: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _ProviderSpec:
    key: str
    label: str
    driver: str
    domains: list[str]
    config: dict[str, str] = field(repr=False)


@dataclass(frozen=True)
class _ModelSpec:
    provider: str
    body: dict[str, Any]


def seed_path(settings: Settings, directory: Path = SEED_DIR) -> Path:
    return directory / f"models.{settings.deploy_profile}.yaml"


def _refs(value: Any) -> list[tuple[str, str | None]]:
    return (
        [(m.group(1), m.group(2)) for m in _REF.finditer(value)] if isinstance(value, str) else []
    )


def _expand(value: Any, env: Mapping[str, str], where: str) -> Any:
    if not isinstance(value, str):
        return value

    def sub(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        if env.get(name):
            return env[name]
        if default is not None:
            return default
        raise SeedError(f"{where}: {name} is not set")

    return _REF.sub(sub, value)


def _missing(values: list[Any], env: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """(required variables that are unset, all required variables)."""
    required = [name for v in values for name, default in _refs(v) if default is None]
    return [name for name in required if not env.get(name)], required


def plan(
    doc: dict[str, Any], settings: Settings, env: Mapping[str, str]
) -> tuple[list[_ProviderSpec], list[_ModelSpec], list[str]]:
    """Validates the whole file before anything is written; returns what to write and the
    reported skips."""
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise SeedError("seed file must be a mapping with version: 1")
    policy = EgressPolicy(settings)
    providers: dict[str, _ProviderSpec] = {}
    skipped: list[str] = []
    other_backend: set[str] = set()  # serves another INFERENCE_BACKEND: not this installation's
    optional_off: set[str] = set()  # optional, none of its variables set: reported
    for raw in doc.get("providers") or []:
        key, driver = raw["key"], raw["driver"]
        where = f"provider {key}"
        if driver not in drivers.DRIVERS:
            raise SeedError(f"{where}: unknown driver {driver}")
        wanted = raw.get("inference_backend")
        if wanted is not None and wanted != settings.inference_backend:
            other_backend.add(key)
            continue
        secret = {f.name for f in drivers.DRIVERS[driver].fields if f.secret}
        config_in = raw.get("config") or {}
        for name in secret & set(config_in):
            if not _REF.fullmatch(str(config_in[name])):
                raise SeedError(f"{where}: secret field {name} must be a ${{VAR}} reference")
        unset, required = _missing(list(config_in.values()), env)
        if unset and raw.get("optional") and len(unset) == len(required):
            skipped.append(f"provider {key}: optional, {', '.join(unset)} not set")
            optional_off.add(key)
            continue
        if unset:
            raise SeedError(f"{where}: not set: {', '.join(unset)}")
        config = {name: _expand(v, env, where) for name, v in config_in.items()}
        try:
            drivers.validate_domains(driver, raw["domains"])
            clean = drivers.validate_config(driver, config)
            base, _ = _upstream(driver, clean, "seed")
            policy.check_url(httpx2.URL(base))
        except ApiError as exc:
            raise SeedError(f"{where}: {exc.code}: {exc.message}") from None
        except ReconcileProblem as exc:
            raise SeedError(f"{where}: {exc.code}") from None
        except EgressDenied as exc:
            raise SeedError(f"{where}: {exc.code} ({exc.origin})") from None
        providers[key] = _ProviderSpec(key, raw.get("label", key), driver, raw["domains"], clean)

    models: list[_ModelSpec] = []
    keys: set[str] = set()
    for raw in doc.get("models") or []:
        provider = raw["provider"]
        where = f"model {raw.get('key')}"
        if provider in other_backend:
            continue
        if provider in optional_off:
            skipped.append(f"{where}: provider {provider} skipped")
            continue
        if provider not in providers:
            raise SeedError(f"{where}: unknown provider {provider}")
        body = {k: _expand(v, env, where) for k, v in raw.items() if k != "provider"}
        body.setdefault("category", "llm")
        body.setdefault("upstream_api", "chat")
        try:
            ModelCreate(**body, provider_id=uuid.uuid4())
        except ValidationError as exc:
            fields = sorted({".".join(map(str, e["loc"])) for e in exc.errors()})
            raise SeedError(f"{where}: invalid fields {fields}") from None
        if body["key"] in keys:
            raise SeedError(f"{where}: key appears twice for this installation")
        keys.add(body["key"])
        models.append(_ModelSpec(provider, body))
    if not models:
        raise SeedError(
            f"no model for this installation (INFERENCE_BACKEND={settings.inference_backend})"
        )
    return list(providers.values()), models, skipped


async def apply(
    session: AsyncSession,
    project_key: str,
    providers: list[_ProviderSpec],
    models: list[_ModelSpec],
    settings: Settings,
) -> SeedReport:
    report = SeedReport()
    project_id = await session.scalar(
        select(Project.id).where(Project.key == project_key, Project.deleted_at.is_(None))
    )
    if project_id is None:
        raise SeedError(f"project {project_key} does not exist; create it in the console first")
    ids: dict[str, uuid.UUID] = {}
    for spec in providers:
        existing = await session.scalar(select(Provider.id).where(Provider.key == spec.key))
        if existing is not None:
            ids[spec.key] = existing
            report.providers_existing.append(spec.key)
        else:
            provider = Provider(
                key=spec.key,
                label=spec.label,
                driver=spec.driver,
                domains=spec.domains,
                config_encrypted=encrypt_json(spec.config, settings),
                supports_test=drivers.driver(spec.driver).test_call is not None,
                created_by="seed",
            )
            session.add(provider)
            await session.flush()
            ids[spec.key] = provider.id
            report.providers_created.append(spec.key)
        linked = await session.scalar(
            select(ProviderProject.provider_id).where(
                ProviderProject.provider_id == ids[spec.key],
                ProviderProject.project_id == project_id,
            )
        )
        if linked is None:
            session.add(ProviderProject(provider_id=ids[spec.key], project_id=project_id))
    for spec in models:
        body = ModelCreate(**spec.body, provider_id=ids[spec.provider])
        taken = await session.scalar(
            select(Model.id).where(
                Model.project_id == project_id, Model.key == body.key, Model.deleted_at.is_(None)
            )
        )
        if taken is not None:
            report.models_existing.append(body.key)
            continue
        session.add(
            Model(
                **body.model_dump(mode="json", exclude={"provider_id"}),
                provider_id=body.provider_id,
                project_id=project_id,
                created_by="seed",
            )
        )
        report.models_created.append(body.key)
    await session.flush()
    await write_event(
        session,
        AuditEntry(
            action="catalog.seed",
            resource_type="project",
            outcome="success",
            actor_type="system",
            actor_id="cli",
            project_id=str(project_id),
            resource_id=str(project_id),
            after={
                "profile": settings.deploy_profile,
                "providers_created": report.providers_created,
                "models_created": report.models_created,
            },
        ),
    )
    return report


async def seed(
    session: AsyncSession,
    project_key: str,
    settings: Settings,
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> SeedReport:
    path = path or seed_path(settings)
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SeedError(f"cannot read {path}: {type(exc).__name__}") from None
    providers, models, skipped = plan(doc, settings, os.environ if env is None else env)
    report = await apply(session, project_key, providers, models, settings)
    report.skipped = skipped
    return report
