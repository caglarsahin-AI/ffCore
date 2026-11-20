-- FFCore least-privileged application role `ffcore_app` (package 12, FOLLOWUP-46).
-- Run as the database owner in the FFCore database; idempotent, safe to repeat. No password
-- in this file: initdb sets it from APP_DB_PASSWORD (initdb/20-app-role.sh); on an existing
-- volume the operator runs this file once and then `\password ffcore_app` (docs/kurulum.md).
-- The role reads and writes application rows; it owns nothing and has no DDL. Audit
-- partitions are created, detached and dropped only through the owner's functions
-- (migration 12_0001, SECURITY DEFINER).

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ffcore_app') THEN
        CREATE ROLE ffcore_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO ffcore_app', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO ffcore_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ffcore_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ffcore_app;
-- Tables and sequences later migrations create (as this owner) get the same grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ffcore_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ffcore_app;

DO $$
BEGIN
    -- Append-only tables: insert and read only (their triggers refuse the rest anyway).
    IF to_regclass('public.audit_events') IS NOT NULL THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM ffcore_app;
    END IF;
    IF to_regclass('public.retention_runs') IS NOT NULL THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON retention_runs FROM ffcore_app;
    END IF;
    -- The LangGraph checkpointer's schema (06a) and its tables (setup-checkpointer).
    IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'checkpoints') THEN
        GRANT USAGE ON SCHEMA checkpoints TO ffcore_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA checkpoints TO ffcore_app;
        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA checkpoints TO ffcore_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA checkpoints
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ffcore_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA checkpoints
            GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ffcore_app;
    END IF;
    -- The audit partition functions (migration 12_0001).
    IF to_regprocedure('ffcore_audit_detach_partition(text)') IS NOT NULL THEN
        GRANT EXECUTE ON FUNCTION ffcore_audit_ensure_partition(date) TO ffcore_app;
        GRANT EXECUTE ON FUNCTION ffcore_audit_detach_partition(text) TO ffcore_app;
        GRANT EXECUTE ON FUNCTION ffcore_audit_drop_partition(text) TO ffcore_app;
    END IF;
END
$$;
