"""Operator commands, run explicitly (never at startup):

    docker compose run --rm -T backend python -m ffcore.cli create-superadmin \
        --email admin@example.org --full-name "Admin" --password-stdin < password.txt
    docker compose run --rm tools make seed-models PROJECT=hastane   (01, first install)
    docker compose run --rm tools make render-litellm                 (01, reconcile LiteLLM)
    docker compose run --rm tools make seed-sql-demo                  (05a, mcp-sql demo DB)
    docker compose run --rm tools make seed-sql-context PROJECT=hastane (05a, get_schema data)

The password is read from stdin, never from the command line (shell history, process list).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

from ffcore.core import db, prompts, tracing
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import get_settings
from ffcore.core.logging import configure_logging
from ffcore.core.passwords import MIN_LENGTH, hash_password
from ffcore.models.identity import Project, User
from ffcore.services import (
    catalog_loader,
    litellm_reconcile,
    mcp_sql_context,
    mcp_sql_demo,
    seed_models,
)


class CliError(Exception):
    pass


async def create_superadmin(email: str, full_name: str, password: str, access: str) -> str:
    if len(password) < MIN_LENGTH:
        raise CliError(f"password must be at least {MIN_LENGTH} characters")
    async with db.session_scope() as session:
        taken = await session.scalar(
            select(User.id).where(
                func.lower(User.email) == email.lower(), User.deleted_at.is_(None)
            )
        )
        if taken is not None:
            raise CliError("a user with this email already exists")
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            is_superadmin=True,
            superadmin_access=access,
        )
        session.add(user)
        await session.flush()
        await write_event(
            session,
            AuditEntry(
                action="user.create_superadmin",
                resource_type="user",
                outcome="success",
                actor_type="system",
                actor_id="cli",
                resource_id=str(user.id),
                after={"id": str(user.id), "is_superadmin": True, "superadmin_access": access},
            ),
        )
        await session.commit()
        return str(user.id)


async def enqueue_reindex(project_key: str, kb_key: str, layer: str, full: bool) -> str:
    """04a: `make reindex`. Enqueues the worker job; the API process embeds (C10)."""
    from sqlalchemy import select

    from ffcore.core import db
    from ffcore.core.config import get_settings
    from ffcore.knowledge.jobs import get_queue
    from ffcore.models.identity import Project
    from ffcore.models.knowledge import KnowledgeBase

    async with db.session_scope() as session:
        kb_id = await session.scalar(
            select(KnowledgeBase.id)
            .join(Project, Project.id == KnowledgeBase.project_id)
            .where(
                Project.key == project_key,
                KnowledgeBase.key == kb_key,
                KnowledgeBase.deleted_at.is_(None),
            )
        )
    if kb_id is None:
        raise CliError(f"knowledge base {project_key}/{kb_key} not found")
    return await get_queue(get_settings()).enqueue("reindex_job", str(kb_id), layer, full)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ffcore.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-superadmin", help="create the first superadmin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--full-name", required=True)
    admin.add_argument("--access", choices=("edit", "read"), default="edit")
    admin.add_argument(
        "--password-stdin", action="store_true", required=True, help="read the password from stdin"
    )
    catalog = commands.add_parser("load-model-catalog", help="load the static model catalog")
    catalog.add_argument("--path", required=True, type=Path)
    seed = commands.add_parser(
        "seed-models", help="first-install providers and models from deploy/seed (01)"
    )
    seed.add_argument("--project", required=True, help="existing project key")
    seed.add_argument("--path", type=Path, help="seed file (default: models.<profile>.yaml)")
    render = commands.add_parser(
        "render-litellm", help="reconcile LiteLLM's models with the tables (01)"
    )
    render.add_argument(
        "--check", action="store_true", help="only report the difference; exit 1 if any"
    )
    reindex = commands.add_parser("reindex", help="re-run silver or gold for a knowledge base")
    reindex.add_argument("--project", required=True, help="project key")
    reindex.add_argument("--kb", required=True, help="knowledge base key")
    reindex.add_argument("--layer", choices=("silver", "gold"), required=True)
    reindex.add_argument("--full", action="store_true", help="every document, not only changed")
    seed_prompts = commands.add_parser(
        "seed-prompts", help="first-install prompts from backend/prompts into Langfuse (02)"
    )
    seed_prompts.add_argument("--path", required=True, type=Path)
    sql_demo = commands.add_parser(
        "seed-sql-demo", help="create or refresh mcp-sql's demo database and login user (05a)"
    )
    sql_demo.add_argument("--path", required=True, type=Path, help="data/samples/schema")
    sql_context = commands.add_parser(
        "seed-sql-context", help="load table descriptions and SQL examples into a project (05a)"
    )
    sql_context.add_argument("--project", required=True, help="existing project key")
    sql_context.add_argument("--path", required=True, type=Path, help="data/samples/schema")
    args = parser.parse_args(argv)
    configure_logging(get_settings())

    try:
        if args.command == "create-superadmin":
            password = sys.stdin.readline().rstrip("\r\n")
            user_id = asyncio.run(
                create_superadmin(args.email, args.full_name, password, args.access)
            )
            print(f"superadmin created: {user_id}")
        elif args.command == "load-model-catalog":
            result = asyncio.run(catalog_loader.load(args.path))
            print(f"model catalog: {result.upserted} entries, {result.removed} removed")
        elif args.command == "seed-models":
            report = asyncio.run(_seed(args.project, args.path))
            print(f"providers created: {report.providers_created or '-'}")
            print(f"providers already present: {report.providers_existing or '-'}")
            print(f"models created: {report.models_created or '-'}")
            print(f"models already present: {report.models_existing or '-'}")
            for line in report.skipped:
                print(f"skipped: {line}")
            print("next: make render-litellm (the backend also reconciles on start)")
        elif args.command == "render-litellm":
            result = asyncio.run(_render(args.check))
            for verb in ("created", "updated", "deleted"):
                print(f"{verb}: {getattr(result, verb) or '-'}")
            for problem in result.problems:
                print(f"not written: {problem['model']} ({problem['code']}: {problem['detail']})")
            if result.problems or (args.check and result.changed):
                return 1
        elif args.command == "reindex":
            job = asyncio.run(enqueue_reindex(args.project, args.kb, args.layer, args.full))
            print(f"reindex queued: job {job} (worker log shows reused=N embedded=M)")
        elif args.command == "seed-prompts":
            client = tracing.init_tracing(get_settings())
            try:
                report = prompts.seed_prompts(client, args.path)
            finally:
                tracing.shutdown_tracing()
            print(f"prompts created: {report.created or '-'}")
            print(f"prompts already present: {report.existing or '-'}")
        elif args.command == "seed-sql-demo":
            database, user = _seed_sql_demo(get_settings(), args.path)
            print(f"demo database ready: {database} (read-only login user {user})")
            print("SQL_DEMO_DATABASE_URL uses this user and AGENT_DEMO_DB_PASSWORD (.env)")
        elif args.command == "seed-sql-context":
            descriptions, examples = asyncio.run(_seed_sql_context(args.project, args.path))
            print(f"table descriptions loaded: {descriptions}; SQL examples loaded: {examples}")
    except (
        CliError,
        catalog_loader.CatalogFileError,
        seed_models.SeedError,
        tracing.TracingConfigError,
        prompts.PromptUnavailable,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


async def _seed(project: str, path: Path | None) -> seed_models.SeedReport:
    settings = get_settings()
    async with db.session_scope() as session:
        report = await seed_models.seed(session, project, settings, path)
        await session.commit()
    return report


DEMO_DATABASE = "agent_demo"
DEMO_LOGIN_USER = "mcp_sql"


def _seed_sql_demo(settings, path: Path) -> tuple[str, str]:
    """13a's demo database in the existing Postgres, with a read-only login user (05a S5)."""
    if settings.agent_demo_db_password is None:
        raise CliError("AGENT_DEMO_DB_PASSWORD is not set (.env)")
    if settings.database_url is None:
        raise CliError("DATABASE_URL is not set")
    from sqlalchemy.engine import make_url

    admin = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql")
    mcp_sql_demo.seed_demo(
        admin.render_as_string(hide_password=False),
        database=DEMO_DATABASE,
        login_user=DEMO_LOGIN_USER,
        password=settings.agent_demo_db_password.get_secret_value(),
        schema_dir=path,
        statement_timeout_s=settings.sql_timeout_s,
    )
    return DEMO_DATABASE, DEMO_LOGIN_USER


async def _seed_sql_context(project_key: str, path: Path) -> tuple[int, int]:
    settings = get_settings()
    async with db.session_scope() as session:
        project_id = await session.scalar(
            select(Project.id).where(Project.key == project_key, Project.deleted_at.is_(None))
        )
        if project_id is None:
            raise CliError(f"no project with key {project_key}")
        report = await mcp_sql_context.load(session, project_id, path, settings, created_by="cli")
        await session.commit()
    return report


async def _render(check: bool) -> litellm_reconcile.ReconcileReport:
    async with db.session_scope() as session:
        return await litellm_reconcile.reconcile(session, get_settings(), dry_run=check)


if __name__ == "__main__":
    sys.exit(main())
