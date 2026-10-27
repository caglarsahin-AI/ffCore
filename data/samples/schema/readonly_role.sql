-- Read-only role template for mcp-sql (plan/05 B). No password here: the login
-- user and its secret are created by the installer from .env, then granted this role.
CREATE ROLE agent_readonly NOLOGIN;
GRANT USAGE ON SCHEMA public TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;
ALTER ROLE agent_readonly SET statement_timeout = '20s';
ALTER ROLE agent_readonly SET default_transaction_read_only = on;
