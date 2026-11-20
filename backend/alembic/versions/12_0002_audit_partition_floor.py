"""12: audit partitions stay out of the application role's reach for 365 days

Revision ID: 12_0002
Revises: 12_0001
Create Date: 2026-11-20

Review 12-2 r1 MAJOR-1 (K-12-0022): with only the ffcore_app credentials, 12_0001's functions
could detach and drop the current month's audit partition; audit writes then failed and the
detached table (no append-only trigger) took UPDATE/DELETE through the default privileges.

- `ffcore_audit_detach_partition` / `ffcore_audit_drop_partition` refuse a partition whose month
  ends later than now() - 365 days (`audit_partition_too_recent`): the floor is fixed here, not a
  parameter, and equals retention's own floor (AUDIT_FLOOR_DAYS), so retention never hits it.
- The role keeps only INSERT and SELECT on audit partitions: `ensure_partition` revokes the rest
  on each partition it creates, detach revokes INSERT too (a detached partition is read only),
  and this revision does both for the partitions that already exist.
- `ffcore_audit_ensure_partition` raises `audit_partition_detached` for a month whose table
  exists but is no longer attached, instead of returning its name as if writes could go there.

Function bodies are replaced (CREATE OR REPLACE keeps their EXECUTE grants); SECURITY DEFINER
and the fixed search_path are restated. Additive: no table changes.
"""

import importlib.util
from pathlib import Path

from alembic import op

revision = "12_0002"
down_revision = "12_0001"
branch_labels = None
depends_on = None

FLOOR = "365 days"
NAME_PATTERN = "^audit_events_[0-9]{4}_[0-9]{2}$"

TOO_RECENT = f"""
    IF (to_date(substring(name from 14), 'YYYY_MM') + interval '1 month')::timestamp
            AT TIME ZONE 'UTC' > now() - interval '{FLOOR}' THEN
        RAISE EXCEPTION 'audit_partition_too_recent: % is inside the {FLOOR} floor', name;
    END IF;
"""

ENSURE = """
CREATE OR REPLACE FUNCTION ffcore_audit_ensure_partition(month date) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    first_day date := date_trunc('month', month)::date;
    name text := format('audit_events_%s', to_char(first_day, 'YYYY_MM'));
BEGIN
    IF to_regclass(format('public.%I', name)) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE public.%I PARTITION OF public.audit_events FOR VALUES FROM (%L) TO (%L)',
            name,
            first_day::timestamp AT TIME ZONE 'UTC',
            (first_day + interval '1 month')::timestamp AT TIME ZONE 'UTC'
        );
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE TRUNCATE ON public.%I'
            ' FOR EACH STATEMENT EXECUTE FUNCTION ffcore_audit_append_only()',
            name || '_no_truncate',
            name
        );
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON public.%I FROM PUBLIC', name);
    ELSIF NOT EXISTS (
        SELECT FROM pg_inherits WHERE inhrelid = to_regclass(format('public.%I', name))
    ) THEN
        RAISE EXCEPTION 'audit_partition_detached: % exists but is not attached to audit_events',
            name;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ffcore_app') THEN
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON public.%I FROM ffcore_app', name);
    END IF;
    RETURN name;
END
$$
"""

DETACH = f"""
CREATE OR REPLACE FUNCTION ffcore_audit_detach_partition(name text) RETURNS text
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
{TOO_RECENT}
    EXECUTE format('ALTER TABLE public.audit_events DETACH PARTITION public.%I', name);
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ffcore_app') THEN
        EXECUTE format(
            'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.%I FROM ffcore_app', name
        );
    END IF;
    RETURN name;
END
$$
"""

DROP = f"""
CREATE OR REPLACE FUNCTION ffcore_audit_drop_partition(name text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF name IS NULL OR name !~ '{NAME_PATTERN}' THEN
        RAISE EXCEPTION 'not an audit partition name: %', name;
    END IF;
    IF to_regclass(format('public.%I', name)) IS NULL THEN
        RAISE EXCEPTION 'no such table: %', name;
    END IF;
{TOO_RECENT}
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

# The partitions that exist already: INSERT and SELECT only (attached), SELECT only (detached).
EXISTING = """
DO $$
DECLARE
    t record;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ffcore_app') THEN
        RETURN;
    END IF;
    FOR t IN
        SELECT c.relname, EXISTS (SELECT FROM pg_inherits i WHERE i.inhrelid = c.oid) AS attached
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname ~ '^audit_events_[0-9]{4}_[0-9]{2}$'
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON public.%I FROM ffcore_app', t.relname);
        IF NOT t.attached THEN
            EXECUTE format('REVOKE INSERT ON public.%I FROM ffcore_app', t.relname);
        END IF;
    END LOOP;
END
$$
"""


def upgrade() -> None:
    op.execute(ENSURE)
    op.execute(DETACH)
    op.execute(DROP)
    op.execute(EXISTING)


def _previous():
    path = Path(__file__).with_name("12_0001_app_role.py")
    spec = importlib.util.spec_from_file_location("ffcore_migration_12_0001", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def downgrade() -> None:
    previous = _previous()
    # 12_0001's detach/drop bodies (CREATE -> CREATE OR REPLACE keeps the grants).
    op.execute(previous.DETACH.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    op.execute(previous.DROP.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    # 03b's ensure body under 12_0001's SECURITY DEFINER; the per-partition revokes stay.
    op.execute(
        ENSURE.replace(
            """    ELSIF NOT EXISTS (
        SELECT FROM pg_inherits WHERE inhrelid = to_regclass(format('public.%I', name))
    ) THEN
        RAISE EXCEPTION 'audit_partition_detached: % exists but is not attached to audit_events',
            name;
""",
            "",
        )
    )
