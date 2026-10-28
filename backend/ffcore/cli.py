"""Operator commands, run explicitly (never at startup):

    docker compose run --rm -T backend python -m ffcore.cli create-superadmin \
        --email admin@example.org --full-name "Admin" --password-stdin < password.txt
    docker compose run --rm tools make seed-models PROJECT=hastane   (01, first install)
    docker compose run --rm tools make render-litellm                 (01, reconcile LiteLLM)

The password is read from stdin, never from the command line (shell history, process list).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

from ffcore.core import db
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import get_settings
from ffcore.core.passwords import MIN_LENGTH, hash_password
from ffcore.models.identity import User
from ffcore.services import catalog_loader, litellm_reconcile, seed_models


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
    args = parser.parse_args(argv)

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
    except (CliError, catalog_loader.CatalogFileError, seed_models.SeedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


async def _seed(project: str, path: Path | None) -> seed_models.SeedReport:
    settings = get_settings()
    async with db.session_scope() as session:
        report = await seed_models.seed(session, project, settings, path)
        await session.commit()
    return report


async def _render(check: bool) -> litellm_reconcile.ReconcileReport:
    async with db.session_scope() as session:
        return await litellm_reconcile.reconcile(session, get_settings(), dry_run=check)


if __name__ == "__main__":
    sys.exit(main())
