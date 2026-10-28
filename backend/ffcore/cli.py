"""Operator commands, run explicitly (never at startup):

    docker compose run --rm -T backend python -m ffcore.cli create-superadmin \
        --email admin@example.org --full-name "Admin" --password-stdin < password.txt

The password is read from stdin, never from the command line (shell history, process list).
"""

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from ffcore.core import db
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.passwords import MIN_LENGTH, hash_password
from ffcore.models.identity import User


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
    args = parser.parse_args(argv)

    try:
        if args.command == "create-superadmin":
            password = sys.stdin.readline().rstrip("\r\n")
            user_id = asyncio.run(
                create_superadmin(args.email, args.full_name, password, args.access)
            )
            print(f"superadmin created: {user_id}")
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
