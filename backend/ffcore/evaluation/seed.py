"""`make seed-eval` (09): a sample exam set into one project's Langfuse dataset, and its suite.

The suite file (data/samples/eval/suite.json) names the set; the dataset becomes
`<project_key>.<suite_key>` (K-09-0007 S6) and each item `<dataset>-<item id>`, upserted by id
(L3), so a second run changes nothing. Items of the dataset that are no longer in the file are
archived, not deleted (L4). The local suite row is created when missing and left as it is when
present (the console owns it after the first install, like 01's seed). A suite file that asks for
`llm_judge` while EVAL_JUDGE_MODEL is empty is refused unless the scorer is left out explicitly
(`--without llm_judge`): never a silent drop.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from ffcore.core.config import Settings
from ffcore.evaluation.langfuse_api import LangfuseApi
from ffcore.models.eval import EvalSuite
from ffcore.models.identity import Project


class SeedError(RuntimeError):
    pass


@dataclass
class SeedReport:
    dataset: str
    items_upserted: int = 0
    items_archived: int = 0
    suite_created: bool = False
    notes: list[str] = field(default_factory=list)


def load_files(suite_path: Path, items_path: Path) -> tuple[dict, list[dict]]:
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    items = json.loads(items_path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise SeedError(f"{items_path}: expected a non-empty list of items")
    ids = [i.get("id") for i in items]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) for i in ids):
        raise SeedError(f"{items_path}: item ids must be unique strings")
    return suite, items


async def seed(
    session,
    settings: Settings,
    api: LangfuseApi,
    *,
    project_key: str,
    suite_path: Path,
    items_path: Path,
    without: set[str],
    created_by: str = "seed-eval",
) -> SeedReport:
    suite, items = load_files(suite_path, items_path)
    project = await session.scalar(select(Project).where(Project.key == project_key))
    if project is None:
        raise SeedError(f"project {project_key!r} not found")
    scorers = [s for s in suite["scorers"] if s not in without]
    if "llm_judge" in scorers and not settings.eval_judge_model:
        raise SeedError(
            "the suite asks for llm_judge but EVAL_JUDGE_MODEL is empty; set it, or leave the "
            "scorer out explicitly with --without llm_judge"
        )
    dataset = f"{project.key}.{suite['key']}"
    report = SeedReport(dataset=dataset)
    await api.upsert_dataset(
        dataset,
        description=suite["name"],
        metadata={"project_key": project.key, "suite": suite["key"]},
    )
    wanted = set()
    for item in items:
        item_id = f"{dataset}-{item['id']}"
        wanted.add(item_id)
        await api.upsert_item(
            dataset,
            item_id,
            input=item["input"],
            expected_output=item.get("expected_output") or {},
            metadata=item.get("metadata") or {},
        )
        report.items_upserted += 1
    for existing in await api.items(dataset):
        if existing["id"] not in wanted and existing.get("status") == "ACTIVE":
            await api.upsert_item(
                dataset,
                existing["id"],
                input=existing.get("input") or {},
                expected_output=existing.get("expectedOutput") or {},
                metadata=existing.get("metadata") or {},
                status="ARCHIVED",
            )
            report.items_archived += 1
    row = await session.scalar(
        select(EvalSuite).where(
            EvalSuite.project_id == project.id,
            EvalSuite.key == suite["key"],
            EvalSuite.deleted_at.is_(None),
        )
    )
    if row is None:
        threshold = suite.get("pass_threshold") or settings.eval_pass_threshold
        if threshold is None:
            raise SeedError("no pass_threshold in the suite file and EVAL_PASS_THRESHOLD is empty")
        session.add(
            EvalSuite(
                project_id=project.id,
                key=suite["key"],
                name=suite["name"],
                langfuse_dataset_name=dataset,
                scorers=[{"name": s} for s in scorers],
                pass_threshold=threshold,
                repeat=int(suite.get("repeat", 1)),
                created_by=created_by,
            )
        )
        await session.commit()
        report.suite_created = True
    if without:
        report.notes.append(f"left out by request: {sorted(without)}")
    return report
