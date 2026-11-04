"""Exam API shapes (09)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ffcore.api.schemas import Strict
from ffcore.evaluation.scorers import SCORERS
from ffcore.models.eval import SUITE_KEY_REGEX

ScorerName = Literal[
    "contains",
    "regex",
    "json_schema",
    "cites_source",
    "semantic",
    "llm_judge",
    "sql_result",
    "latency_cost",
]
assert set(ScorerName.__args__) == set(SCORERS)


class ScorerConfig(Strict):
    name: ScorerName
    # llm_judge: lowest passing score 1-5 (default 4); semantic: cosine threshold (default 0.8);
    # latency_cost: limits (at least one).
    pass_min: int | None = Field(default=None, ge=1, le=5)
    threshold: float | None = Field(default=None, gt=0, le=1)
    max_ms: int | None = Field(default=None, gt=0)
    max_usd: float | None = Field(default=None, gt=0)


class SuiteCreate(Strict):
    key: str = Field(pattern=SUITE_KEY_REGEX)
    name: str = Field(min_length=1, max_length=200)
    agent_id: UUID | None = Field(
        default=None, description="The agent whose publish this suite gates (none: no gate)."
    )
    langfuse_dataset_name: str | None = Field(
        default=None,
        description="Default `<project_key>.<key>`; must start with `<project_key>.`.",
    )
    scorers: list[ScorerConfig] = Field(min_length=1)
    pass_threshold: float | None = Field(
        default=None, gt=0, le=1, description="Default EVAL_PASS_THRESHOLD (profile value)."
    )
    repeat: int = Field(default=1, ge=1, le=10)
    approve_tools: bool = Field(
        default=False,
        description="false: item runs waiting for an approval are not_run; true: they wait in "
        "the approval queue for a person (never approved by the exam).",
    )

    @field_validator("scorers")
    @classmethod
    def _unique(cls, value: list[ScorerConfig]) -> list[ScorerConfig]:
        names = [s.name for s in value]
        if len(names) != len(set(names)):
            raise ValueError("each scorer once")
        for s in value:
            if s.name == "latency_cost" and s.max_ms is None and s.max_usd is None:
                raise ValueError("latency_cost needs max_ms or max_usd")
        return value


class SuiteUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    agent_id: UUID | None = None
    scorers: list[ScorerConfig] | None = Field(default=None, min_length=1)
    pass_threshold: float | None = Field(default=None, gt=0, le=1)
    repeat: int | None = Field(default=None, ge=1, le=10)
    approve_tools: bool | None = None


class SuiteOut(BaseModel):
    id: UUID
    project_id: UUID
    key: str
    name: str
    agent_id: UUID | None
    langfuse_dataset_name: str
    scorers: list[dict[str, Any]]
    pass_threshold: float
    repeat: int
    approve_tools: bool
    created_at: datetime
    updated_at: datetime


class SuiteList(BaseModel):
    items: list[SuiteOut]


class EvalRunOut(BaseModel):
    id: UUID
    project_id: UUID
    suite_id: UUID
    agent_version_id: UUID
    langfuse_run_name: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    error_code: str | None
    items: int
    scored: int
    summary: dict[str, Any] | None
    cost_usd: float | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class EvalRunList(BaseModel):
    items: list[EvalRunOut]
