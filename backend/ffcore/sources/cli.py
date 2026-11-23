"""`make sync`: queue one run of a data source from the command line (16, D3).

python -m ffcore.sources.cli sync --project <key> --source <key> --layer raw|silver|gold
    --mode full|delta [--force-prune]

The run goes to the sync worker (raw) or the ingest worker (silver, gold), exactly like the
API's "Sync now"; the command prints the run id and exits. `--force-prune` (full raw only) is an
audit event of the system actor `cli`. Exit codes: 0 queued, 2 refused (unknown project or
source, a run already active, a paused source, force-prune outside a full raw run).
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from ffcore.core import db
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import get_settings
from ffcore.core.logging import configure_logging
from ffcore.knowledge.jobs import get_queue
from ffcore.models.identity import Project
from ffcore.models.sources import DataSource
from ffcore.sources import engine, scheduler
from ffcore.sources.base import SourceError

ACTOR = "cli"


class CliRefused(Exception):
    pass


async def queue_sync(
    project_key: str, source_key: str, layer: str, mode: str, force_prune: bool, *, settings=None
) -> str:
    settings = settings or get_settings()
    if force_prune and (layer != "raw" or mode != "full"):
        raise CliRefused("force_prune_requires_full: --force-prune applies to a full raw run")
    async with db.session_scope() as session:
        source = await session.scalar(
            select(DataSource)
            .join(Project, Project.id == DataSource.project_id)
            .where(
                Project.key == project_key,
                DataSource.key == source_key,
                DataSource.deleted_at.is_(None),
            )
        )
        if source is None:
            raise CliRefused(f"data_source_not_found: {project_key}/{source_key}")
        if source.status != "active":
            raise CliRefused(f"data_source_paused: {project_key}/{source_key}")
        try:
            run = await engine.create_run(
                session,
                source,
                layer=layer,
                mode=mode,
                trigger="cli",
                requested_by=ACTOR,
                force_prune=force_prune,
            )
        except SourceError as exc:
            raise CliRefused(f"{exc.code}: {exc.detail}") from None
        if force_prune:
            await write_event(
                session,
                AuditEntry(
                    action="sync_force_prune",
                    resource_type="data_source",
                    outcome="success",
                    actor_type="system",
                    actor_id=ACTOR,
                    project_id=str(source.project_id),
                    resource_id=str(source.id),
                    after={"run_id": str(run.id), "layer": layer, "mode": mode},
                ),
            )
        await session.commit()
    try:
        await engine.enqueue_run(
            run, sync_queue=scheduler.get_sync_queue(settings), ingest_queue=get_queue(settings)
        )
    except Exception:
        await engine.fail_queued(run.id, "enqueue_failed")
        raise
    return str(run.id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ffcore.sources.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="queue one sync run of a data source")
    sync.add_argument("--project", required=True, help="project key")
    sync.add_argument("--source", required=True, help="data source key")
    sync.add_argument("--layer", choices=("raw", "silver", "gold"), required=True)
    sync.add_argument("--mode", choices=("full", "delta"), required=True)
    sync.add_argument(
        "--force-prune",
        action="store_true",
        help="full raw run only: delete even over PRUNE_MAX_RATIO (never over a count mismatch)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(get_settings())
    try:
        run_id = asyncio.run(
            queue_sync(args.project, args.source, args.layer, args.mode, args.force_prune)
        )
    except CliRefused as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"queued run {run_id} ({args.layer} {args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
