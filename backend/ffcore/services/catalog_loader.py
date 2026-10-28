"""Load the static model catalog (deploy/seed/model_catalog.yaml) into `model_catalog`.

Idempotent: entries are upserted by (driver, model_id); rows not in the file are removed, so the
file stays the only source. A malformed file fails as a whole before anything is written.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, select, tuple_

from ffcore.api.schemas import (
    InputType,
    ModelCapabilities,
    ModelCategory,
    ModelPricing,
    ProviderDriver,
)
from ffcore.core import db
from ffcore.models.catalog import ModelCatalogEntry


class CatalogFileError(ValueError):
    pass


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: ProviderDriver
    model_id: str = Field(min_length=1)
    category: ModelCategory
    capabilities: ModelCapabilities
    input_types: list[InputType]
    context_window: int | None = Field(gt=0)
    max_output: int | None = Field(gt=0)
    embed_dim: int | None = Field(gt=0)
    pricing: ModelPricing
    source: str = Field(min_length=1)
    as_of: str = Field(min_length=1)


class _File(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    entries: list[_Entry]


@dataclass(frozen=True)
class LoadResult:
    upserted: int
    removed: int


def read(path: Path) -> list[_Entry]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        entries = _File.model_validate(raw).entries
    except FileNotFoundError:
        raise CatalogFileError(f"catalog file not found: {path}") from None
    except (yaml.YAMLError, ValidationError) as exc:
        raise CatalogFileError(f"catalog file {path} is invalid: {exc}") from None
    keys = [(e.driver, e.model_id) for e in entries]
    if len(set(keys)) != len(keys):
        raise CatalogFileError(f"catalog file {path} lists a driver/model_id twice")
    return entries


async def load(path: Path) -> LoadResult:
    entries = read(path)
    async with db.session_scope() as session:
        existing = {
            (row.driver, row.model_id): row
            for row in await session.scalars(select(ModelCatalogEntry))
        }
        for entry in entries:
            values = entry.model_dump(mode="json")
            row = existing.get((values["driver"], values["model_id"]))
            if row is None:
                session.add(ModelCatalogEntry(**values))
            else:
                for field, value in values.items():
                    setattr(row, field, value)
        wanted = [(e.driver.value, e.model_id) for e in entries]
        stale = [key for key in existing if key not in set(wanted)]
        if stale:
            await session.execute(
                delete(ModelCatalogEntry).where(
                    tuple_(ModelCatalogEntry.driver, ModelCatalogEntry.model_id).in_(stale)
                )
            )
        await session.commit()
    return LoadResult(upserted=len(entries), removed=len(stale))
