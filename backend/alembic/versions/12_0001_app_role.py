"""12: audit partition functions run as the owner; grants for the ffcore_app role

Revision ID: 12_0001
Revises: 04b_0001
Create Date: 2026-11-20

FOLLOWUP-46 (K-12-0013): the application connects as `ffcore_app`, a role without DDL. Audit
partitions are DDL, so the three partition steps become owner functions (SECURITY DEFINER, with
a fixed search_path so a caller cannot swap the objects they name):

- `ffcore_audit_ensure_partition(date)` (03b) becomes SECURITY DEFINER; behaviour unchanged.
- `ffcore_audit_detach_partition(text)` and `ffcore_audit_drop_partition(text)` are new; they
  accept only `audit_events_YYYY_MM` names, detach only an attached partition of audit_events
  and drop only a detached one, and raise otherwise. Retention calls them (retention_job.py).

None of the three is executable by PUBLIC. When the role exists (created by initdb from
APP_DB_PASSWORD, or by deploy/postgres/app-role.sql on an existing volume) it gets EXECUTE and
the same grants as app-role.sql, so a fresh install needs nothing else. Additive: no table
changes; a database without the role keeps working as the owner.
"""

from alembic import op

revision = "12_0001"
down_revision = "04b_0001"
branch_labels = ("12",)
depends_on = None

NAME_PATTERN = "^audit_events_[0-9]{4}_[0-9]{2}$"

DETACH = f"""
CREATE FUNCTION ffcore_audit_detach_partition(name text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF name IS NULL OR name !~ '{NAME_PATTERN}' THEN
        RAISE EXCEPTION 'not an audit partition name: %', name;
    END IF;
    IF NOT EXISTS (
        SELECT FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE p.relname = 'audit_events' AND c.relname = name AND n.nspname = 'public'
    ) THEN
        RAISE EXCEPTION 'not an attached partition of audit_events: %', name;
    END IF;
    EXECUTE format('ALTER TABLE public.audit_events DETACH PARTITION public.%I', name);
    RETURN name;
END
$$
"""

DROP = f"""
CREATE FUNCTION ffcore_audit_drop_partition(name text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF name IS NULL OR name !~ '{NAME_PATTERN}' THEN
        RAISE EXCEPTION 'not an audit partition name: %', name;
    END IF;
    IF to_regclass(format('public.%I', name)) IS NULL THEN
        RAISE EXCEPTION 'no such table: %', name;
    END IF;
    IF EXISTS (
        SELECT FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
        WHERE c.oid = to_regclass(format('public.%I', name))
    ) THEN
        RAISE EXCEPTION 'still attached, detach first: %', name;
    END IF;
    EXECUTE format('DROP TABLE public.%I', name);
    RETURN name;
END
$$
"""

# Same statements as deploy/postgres/app-role.sql, applied only when the role exists.
GRANTS = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ffcore_app') THEN
        RETURN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO ffcore_app', current_database());
    GRANT USAGE ON SCHEMA public TO ffcore_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ffcore_app;
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ffcore_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ffcore_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ffcore_app;
    REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM ffcore_app;
    REVOKE UPDATE, DELETE, TRUNCATE ON retention_runs FROM ffcore_app;
    IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'checkpoints') THEN
        GRANT USAGE ON SCHEMA checkpoints TO ffcore_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA checkpoints TO ffcore_app;
        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA checkpoints TO ffcore_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA checkpoints
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ffcore_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA checkpoints
            GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ffcore_app;
    END IF;
    GRANT EXECUTE ON FUNCTION ffcore_audit_ensure_partition(date) TO ffcore_app;
    GRANT EXECUTE ON FUNCTION ffcore_audit_detach_partition(text) TO ffcore_app;
    GRANT EXECUTE ON FUNCTION ffcore_audit_drop_partition(text) TO ffcore_app;
END
$$
"""

FUNCTIONS = (
    "ffcore_audit_ensure_partition(date)",
    "ffcore_audit_detach_partition(text)",
    "ffcore_audit_drop_partition(text)",
)


def upgrade() -> None:
    op.execute(
        "ALTER FUNCTION ffcore_audit_ensure_partition(date)"
        " SECURITY DEFINER SET search_path = public, pg_temp"
    )
    op.execute(DETACH)
    op.execute(DROP)
    for function in FUNCTIONS:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {function} FROM PUBLIC")
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP FUNCTION ffcore_audit_drop_partition(text)")
    op.execute("DROP FUNCTION ffcore_audit_detach_partition(text)")
    op.execute("ALTER FUNCTION ffcore_audit_ensure_partition(date) RESET search_path")
    op.execute("ALTER FUNCTION ffcore_audit_ensure_partition(date) SECURITY INVOKER")
    op.execute("GRANT EXECUTE ON FUNCTION ffcore_audit_ensure_partition(date) TO PUBLIC")
    # Table grants to ffcore_app stay: they are harmless without the functions, and the role
    # (with its grants) is the installation's, not this revision's.
