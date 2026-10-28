"""03b: audit_events (append-only, monthly partitions)

Revision ID: 03b_0001
Revises: 0001
Create Date: 2026-10-28
"""

from alembic import op

revision = "03b_0001"
down_revision = "0001"
branch_labels = ("03b",)
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_events (
            id uuid NOT NULL,
            ts timestamptz NOT NULL DEFAULT now(),
            actor_type text NOT NULL,
            actor_id text NOT NULL,
            project_id uuid NULL,
            action text NOT NULL,
            resource_type text NOT NULL,
            resource_id text NULL,
            outcome text NOT NULL,
            before jsonb NULL,
            after jsonb NULL,
            request_id text NULL,
            ip inet NULL,
            CONSTRAINT pk_audit_events PRIMARY KEY (id, ts),
            CONSTRAINT ck_audit_events_actor_type
                CHECK (actor_type IN ('user', 'api_key', 'system')),
            CONSTRAINT ck_audit_events_outcome CHECK (outcome IN ('success', 'denied', 'error'))
        ) PARTITION BY RANGE (ts)
        """
    )
    op.execute("CREATE INDEX ix_audit_events_project_ts ON audit_events (project_id, ts)")
    op.execute(
        "CREATE INDEX ix_audit_events_resource ON audit_events (resource_type, resource_id, ts)"
    )
    # Append-only for every role, including the database owner the app connects as today
    # (REVOKE alone does not stop a superuser). Row triggers are cloned to partitions; the
    # TRUNCATE trigger is statement-level, so the partition helper adds it to each partition.
    # Retention (03c) removes whole months with DETACH/DROP PARTITION, which these do not block.
    op.execute(
        """
        CREATE FUNCTION ffcore_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (% refused)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events"
        " FOR EACH ROW EXECUTE FUNCTION ffcore_audit_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events"
        " FOR EACH STATEMENT EXECUTE FUNCTION ffcore_audit_append_only()"
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM PUBLIC")
    # One partition per calendar month in UTC. No DEFAULT partition: a write into a month
    # without a partition fails loudly instead of piling up unnoticed.
    op.execute(
        """
        CREATE FUNCTION ffcore_audit_ensure_partition(month date) RETURNS text
        LANGUAGE plpgsql AS $$
        DECLARE
            first_day date := date_trunc('month', month)::date;
            name text := format('audit_events_%s', to_char(first_day, 'YYYY_MM'));
        BEGIN
            IF to_regclass(name) IS NULL THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF audit_events FOR VALUES FROM (%L) TO (%L)',
                    name,
                    first_day::timestamp AT TIME ZONE 'UTC',
                    (first_day + interval '1 month')::timestamp AT TIME ZONE 'UTC'
                );
                EXECUTE format(
                    'CREATE TRIGGER %I BEFORE TRUNCATE ON %I'
                    ' FOR EACH STATEMENT EXECUTE FUNCTION ffcore_audit_append_only()',
                    name || '_no_truncate',
                    name
                );
                EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %I FROM PUBLIC', name);
            END IF;
            RETURN name;
        END
        $$
        """
    )
    op.execute("SELECT ffcore_audit_ensure_partition((now() AT TIME ZONE 'UTC')::date)")
    op.execute(
        "SELECT ffcore_audit_ensure_partition("
        "((now() AT TIME ZONE 'UTC') + interval '1 month')::date)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_events")
    op.execute("DROP FUNCTION ffcore_audit_ensure_partition(date)")
    op.execute("DROP FUNCTION ffcore_audit_append_only()")
