"""12-2 (FOLLOWUP-46): the application runs as `ffcore_app`, a least-privileged Postgres role.

The role is created by deploy/postgres/initdb/20-app-role.sh when APP_DB_PASSWORD is set
(.env.test sets a dummy one), and migration 12_0001 grants it DML and EXECUTE on the audit
partition functions, which run as the owner (SECURITY DEFINER, fixed search_path). Every test
here runs in a scratch database at the migration head, connecting as the owner and as the role.
"""

import os

import psycopg
import pytest
from sqlalchemy.engine import make_url

APP_USER = os.environ.get("APP_DB_USER", "")
APP_PASSWORD = os.environ.get("APP_DB_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not (APP_USER and APP_PASSWORD),
    reason="NOT_RUN: needs APP_DB_USER/APP_DB_PASSWORD (.env.test) and a stack from a fresh volume",
)


@pytest.fixture
def app_conn(database_url):
    url = make_url(database_url).set(
        drivername="postgresql", username=APP_USER, password=APP_PASSWORD
    )
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
        yield conn


def _denied(conn, statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


def test_12_46_role_is_not_the_owner_and_not_superuser(app_conn):
    row = app_conn.execute(
        "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles"
        " WHERE rolname = current_user"
    ).fetchone()
    assert row == (APP_USER, False, False, False)


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE probe_12 (id int)",
        "ALTER TABLE projects ADD COLUMN probe_12 int",
        "DROP TABLE projects",
        "TRUNCATE audit_events",
        "CREATE SCHEMA probe_12",
    ],
)
def test_12_46_role_has_no_ddl(app_conn, statement):
    _denied(app_conn, statement)


def test_12_46_role_reads_and_writes_application_tables(app_conn):
    assert app_conn.execute("SELECT count(*) FROM projects").fetchone()[0] >= 0
    app_conn.execute(
        "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type, outcome)"
        " VALUES (gen_random_uuid(), now(), 'system', 't', 'probe_12_46', 'probe', 'success')"
    )
    assert app_conn.execute(
        "SELECT count(*) FROM audit_events WHERE action = 'probe_12_46'"
    ).fetchone() == (1,)


def test_12_46_audit_stays_append_only_for_the_role(app_conn):
    with pytest.raises(psycopg.Error):
        app_conn.execute("DELETE FROM audit_events WHERE action = 'probe_12_46'")


def test_12_46_role_creates_audit_partitions_through_the_function(app_conn):
    name = app_conn.execute("SELECT ffcore_audit_ensure_partition(date '2031-03-01')").fetchone()
    assert name == ("audit_events_2031_03",)


def test_12_46_role_detaches_and_drops_old_partitions_only_through_functions(app_conn, pg):
    name = pg.execute("SELECT ffcore_audit_ensure_partition(date '2001-01-01')").fetchone()[0]
    _denied(app_conn, f'ALTER TABLE audit_events DETACH PARTITION "{name}"')
    app_conn.execute("SELECT ffcore_audit_detach_partition(%s)", (name,))
    assert app_conn.execute(f'SELECT count(*) FROM "{name}"').fetchone() == (0,)
    _denied(app_conn, f'DROP TABLE "{name}"')
    app_conn.execute("SELECT ffcore_audit_drop_partition(%s)", (name,))
    assert pg.execute("SELECT to_regclass(%s)", (name,)).fetchone() == (None,)


@pytest.mark.parametrize("name", ["projects", "audit_events", "audit_events_2031_3", "x; DROP"])
def test_12_46_partition_functions_refuse_other_tables(app_conn, name):
    for function in ("ffcore_audit_detach_partition", "ffcore_audit_drop_partition"):
        with pytest.raises(psycopg.errors.RaiseException):
            app_conn.execute(f"SELECT {function}(%s)", (name,))


def test_12_46_drop_refuses_a_partition_that_is_still_attached(app_conn, pg):
    name = pg.execute("SELECT ffcore_audit_ensure_partition(date '2002-02-01')").fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException):
        app_conn.execute("SELECT ffcore_audit_drop_partition(%s)", (name,))


def test_12_46_functions_are_definer_with_fixed_search_path_and_not_public(pg):
    rows = pg.execute(
        "SELECT p.proname, p.prosecdef, p.proconfig,"
        " has_function_privilege('public', p.oid, 'EXECUTE')"
        " FROM pg_proc p WHERE p.proname IN ('ffcore_audit_ensure_partition',"
        " 'ffcore_audit_detach_partition', 'ffcore_audit_drop_partition') ORDER BY 1"
    ).fetchall()
    assert [r[0] for r in rows] == [
        "ffcore_audit_detach_partition",
        "ffcore_audit_drop_partition",
        "ffcore_audit_ensure_partition",
    ]
    for _, definer, config, public in rows:
        assert definer is True
        assert "search_path=public, pg_temp" in config
        assert public is False


def test_12_46_running_backend_connects_as_the_role():
    """The stack's own database: the backend's pool is connected as the role, not the owner."""
    admin = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        users = {
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT usename FROM pg_stat_activity"
                " WHERE datname = current_database() AND client_addr IS NOT NULL"
            )
        }
    assert APP_USER in users


# --- 12-2 r1 MAJOR-1 `denetim-bolum-kapisi`: the role cannot take recent audit away ---


def _current_partition(pg):
    return pg.execute("SELECT ffcore_audit_ensure_partition(current_date)").fetchone()[0]


def test_12_r2_current_month_cannot_be_detached_or_dropped(app_conn, pg):
    name = _current_partition(pg)
    for function in ("ffcore_audit_detach_partition", "ffcore_audit_drop_partition"):
        with pytest.raises(psycopg.errors.RaiseException) as caught:
            app_conn.execute(f"SELECT {function}(%s)", (name,))
        assert "audit_partition_too_recent" in str(caught.value)


def test_12_r2_a_partition_younger_than_365_days_is_refused(app_conn, pg):
    # Ten months back: older than retention's default but inside the 365-day floor.
    name = pg.execute(
        "SELECT ffcore_audit_ensure_partition((current_date - interval '10 months')::date)"
    ).fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException) as caught:
        app_conn.execute("SELECT ffcore_audit_detach_partition(%s)", (name,))
    assert "audit_partition_too_recent" in str(caught.value)


def test_12_r2_older_than_365_days_still_detaches_and_drops(app_conn, pg):
    name = pg.execute(
        "SELECT ffcore_audit_ensure_partition((current_date - interval '14 months')::date)"
    ).fetchone()[0]
    app_conn.execute("SELECT ffcore_audit_detach_partition(%s)", (name,))
    app_conn.execute("SELECT ffcore_audit_drop_partition(%s)", (name,))
    assert pg.execute("SELECT to_regclass(%s)", (name,)).fetchone() == (None,)


def test_12_r2_role_has_only_insert_and_select_on_audit_partitions(app_conn, pg):
    current = _current_partition(pg)
    old = pg.execute("SELECT ffcore_audit_ensure_partition(date '2003-03-01')").fetchone()[0]
    app_conn.execute("SELECT ffcore_audit_detach_partition(%s)", (old,))  # detached: no trigger
    for table in (current, old):
        for privilege, has in (("INSERT", current == table), ("SELECT", True)):
            row = pg.execute(
                "SELECT has_table_privilege(%s, %s, %s)", (APP_USER, table, privilege)
            ).fetchone()
            assert row == (has,), (table, privilege)
        _denied(app_conn, f"UPDATE \"{table}\" SET actor_id = 'tampered'")
        _denied(app_conn, f'DELETE FROM "{table}"')
        _denied(app_conn, f'TRUNCATE "{table}"')
    app_conn.execute("SELECT ffcore_audit_drop_partition(%s)", (old,))


def test_12_r2_ensure_refuses_a_detached_partition(app_conn, pg):
    old = pg.execute("SELECT ffcore_audit_ensure_partition(date '2004-04-01')").fetchone()[0]
    app_conn.execute("SELECT ffcore_audit_detach_partition(%s)", (old,))
    with pytest.raises(psycopg.errors.RaiseException) as caught:
        app_conn.execute("SELECT ffcore_audit_ensure_partition(date '2004-04-01')")
    assert "audit_partition_detached" in str(caught.value)
    app_conn.execute("SELECT ffcore_audit_drop_partition(%s)", (old,))
