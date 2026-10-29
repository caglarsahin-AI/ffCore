"""What get_schema returns (05a, K-05a-0002 S6): business descriptions of the demo tables,
narrowed to the question, and the project's nearest approved question-SQL examples.

The data lives in the backend database (schema_descriptions, few_shots); the embedding model
is loaded only by the API process (PLAN: in-process bge-m3), so mcp-sql asks the backend
(POST .../tools/sql-context, on behalf of the caller). Few-shot similarity is pgvector cosine
on few_shots.embedding.
"""

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select

from ffcore.core.config import Settings
from ffcore.knowledge.embed import embed
from ffcore.models.tools import FewShot, SchemaDescription

EXAMPLES = 5
_WORD = re.compile(r"\w{3,}", re.UNICODE)


def _fold(text: str) -> str:
    return text.casefold().replace("i̇", "i")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(_fold(text)))


@dataclass
class Column:
    name: str
    description: str
    sample_values: list
    is_metric: bool
    formula: str | None


@dataclass
class Table:
    name: str
    description: str
    columns: list[Column]


@dataclass
class Context:
    tables: list[Table]
    # False: no table matched the question, so every table is listed (said, not hidden).
    matched: bool
    examples: list[tuple[str, str]]


async def load(
    session, project_id: uuid.UUID, directory: Path, settings: Settings, *, created_by: str
) -> tuple[int, int]:
    """Replaces the project's descriptions and examples with 13a's JSON files (first install
    or a reload). Returns (descriptions, examples)."""
    rows = json.loads((directory / "schema_descriptions.json").read_text(encoding="utf-8"))
    shots = json.loads((directory / "few_shots.json").read_text(encoding="utf-8"))
    await session.execute(
        SchemaDescription.__table__.update()
        .where(SchemaDescription.project_id == project_id, SchemaDescription.deleted_at.is_(None))
        .values(deleted_at=func.now())
    )
    await session.execute(delete(FewShot).where(FewShot.project_id == project_id))
    for row in rows:
        session.add(
            SchemaDescription(
                project_id=project_id,
                table_name=row["table_name"],
                column_name=row["column_name"],
                description=row["description_tr"],
                sample_values=row.get("sample_values") or [],
                is_metric=bool(row.get("is_metric")),
                formula=row.get("formula"),
                created_by=created_by,
            )
        )
    vectors = (await embed(settings, [s["question"] for s in shots])).dense if shots else []
    for shot, vector in zip(shots, vectors, strict=True):
        session.add(
            FewShot(
                project_id=project_id,
                question=shot["question"],
                sql=shot["sql"],
                embedding=vector,
                approved_by=created_by,
            )
        )
    await session.flush()
    return len(rows), len(shots)


def _tables(rows: list[SchemaDescription]) -> dict[str, Table]:
    tables: dict[str, Table] = {}
    for row in rows:
        table = tables.setdefault(row.table_name, Table(row.table_name, "", []))
        if row.column_name is None:
            table.description = row.description
        else:
            table.columns.append(
                Column(
                    row.column_name, row.description, row.sample_values, row.is_metric, row.formula
                )
            )
    return tables


def _hits(table: Table, words: set[str]) -> bool:
    text = " ".join(
        [table.name, table.description]
        + [f"{c.name} {c.description} {' '.join(map(str, c.sample_values))}" for c in table.columns]
    )
    return bool(words & _words(text.replace("_", " ")))


async def context(
    session, project_id: uuid.UUID, question: str | None, settings: Settings
) -> Context:
    rows = list(
        await session.scalars(
            select(SchemaDescription)
            .where(
                SchemaDescription.project_id == project_id, SchemaDescription.deleted_at.is_(None)
            )
            .order_by(SchemaDescription.table_name, SchemaDescription.column_name.nulls_first())
        )
    )
    tables = _tables(rows)
    chosen, matched = list(tables.values()), True
    examples: list[tuple[str, str]] = []
    if question:
        words = _words(question)
        narrowed = [t for t in tables.values() if _hits(t, words)]
        chosen, matched = (narrowed, True) if narrowed else (chosen, False)
        vector = (await embed(settings, [question])).dense[0]
        shots = await session.scalars(
            select(FewShot)
            .where(FewShot.project_id == project_id)
            .order_by(FewShot.embedding.cosine_distance(vector))
            .limit(EXAMPLES)
        )
        examples = [(s.question, s.sql) for s in shots]
    return Context(chosen, matched, examples)
