"""Reviewer probe for fix/57-alembic-merge r1 (run in the tools container).

/new = the PR worktree, /base = main before the merge (148eadd). Each scenario uses its own
database on the review stack's Postgres. Prints PASS/FAIL lines; exit 1 on any FAIL.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import uuid

import psycopg
from sqlalchemy.engine import make_url

URL = os.environ["DATABASE_URL"]
FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def admin():
    u = make_url(URL).set(drivername="postgresql", database="postgres")
    return psycopg.connect(u.render_as_string(hide_password=False), autocommit=True)


def newdb():
    name = "rev57_" + uuid.uuid4().hex[:10]
    with admin() as c:
        c.execute(f'CREATE DATABASE "{name}"')
    return name


def conn(name):
    u = make_url(URL).set(drivername="postgresql", database=name)
    return psycopg.connect(u.render_as_string(hide_password=False), autocommit=True)


def alembic(root, name, *args):
    env = {**os.environ, "DATABASE_URL": make_url(URL).set(database=name).render_as_string(hide_password=False)}
    return subprocess.run(["alembic", *args], cwd=f"{root}/backend", env=env, capture_output=True, text=True)


def ok(root, name, *args):
    r = alembic(root, name, *args)
    check(r.returncode == 0, f"{root} alembic {' '.join(args)} exit 0" + ("" if r.returncode == 0 else "\n" + r.stderr[-600:]))
    return r


def versions(name):
    with conn(name) as c:
        return {r[0] for r in c.execute("SELECT version_num FROM alembic_version")}


def schema_hash(name):
    with conn(name) as c:
        cols = c.execute(
            "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns"
            " WHERE table_schema='public' AND table_name NOT LIKE 'audit_events_2%%' ORDER BY 1,2"
        ).fetchall()
        idx = c.execute(
            "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public'"
            " AND tablename NOT LIKE 'audit_events_2%%' ORDER BY 1,2"
        ).fetchall()
        cons = c.execute(
            "SELECT conrelid::regclass::text, conname FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace"
            " WHERE n.nspname='public' AND conrelid::regclass::text NOT LIKE 'audit_events_2%%' ORDER BY 1,2"
        ).fetchall()
    return hashlib.sha256(repr((cols, idx, cons)).encode()).hexdigest()[:16], len(cols)


MAIN_ROWS = {"03c_0002", "04a_0001", "05a_0001", "08_0001"}

# S1 empty db, new code
d1 = newdb()
ok("/new", d1, "upgrade", "head")
check(versions(d1) == {"57_0002"}, f"S1 empty upgrade head -> {versions(d1)}")
heads = [x for x in alembic("/new", d1, "heads").stdout.splitlines() if x.strip()]
check(len(heads) == 1, f"S1 alembic heads one line: {heads}")
ok("/new", d1, "upgrade", "heads")
ok("/new", d1, "upgrade", "heads")
check(versions(d1) == {"57_0002"}, "S1 idempotent upgrade heads x2")
h1 = schema_hash(d1)

# S1b empty db, new code, `upgrade heads` (migrate service)
d1b = newdb()
ok("/new", d1b, "upgrade", "heads")
check(versions(d1b) == {"57_0002"} and schema_hash(d1b) == h1, "S1b empty upgrade heads == head, same schema")

# S2 main-shaped db built by the REAL pre-merge code
d2 = newdb()
ok("/base", d2, "upgrade", "heads")
check(versions(d2) == MAIN_ROWS, f"S2 pre-merge main rows: {versions(d2)}")
hmain = schema_hash(d2)
pid = uuid.uuid4()
with conn(d2) as c:
    c.execute("INSERT INTO projects (id, key, name, created_by) VALUES (%s,%s,'Keep me','t')", (pid, "k-" + pid.hex[:8]))
    c.execute("INSERT INTO retention_runs (id, data_class, trigger, dry_run, counts, actor_id) VALUES (gen_random_uuid(),'content','manual',true,'{}','t')")
ok("/new", d2, "upgrade", "head")
check(versions(d2) == {"57_0002"}, f"S2 main-shaped upgrade head -> {versions(d2)}")
with conn(d2) as c:
    check(c.execute("SELECT name FROM projects WHERE id=%s", (pid,)).fetchone() == ("Keep me",), "S2 data kept (projects)")
    check(c.execute("SELECT count(*) FROM retention_runs").fetchone()[0] == 1, "S2 data kept (retention_runs)")
check(schema_hash(d2) == hmain == h1, f"S2 schema identical: main {hmain} new-empty {h1} upgraded {schema_hash(d2)}")
ok("/new", d2, "upgrade", "heads")
check(versions(d2) == {"57_0002"}, "S2 migrate-service idempotent")

# S2b main-shaped, migrate service path (`upgrade heads`)
d2b = newdb()
ok("/base", d2b, "upgrade", "heads")
ok("/new", d2b, "upgrade", "heads")
check(versions(d2b) == {"57_0002"}, "S2b main-shaped upgrade heads -> 57_0002")

# S3 explicit downgrades on S2 db (has data)
ok("/new", d2, "downgrade", "57_0001")
check(versions(d2) == MAIN_ROWS | {"57_0001"}, f"S3 downgrade 57_0001 -> {versions(d2)}")
ok("/new", d2, "upgrade", "head")
r = ok("/new", d2, "downgrade", "06a_0001")
with conn(d2) as c:
    cols = {x[0] for x in c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='runs'")}
    check("checkpoint_deleted_at" not in cols, "S3 downgrade 06a_0001 removed 06a_0002 column")
    check(c.execute("SELECT to_regclass('retention_runs')").fetchone()[0] is None, "S3 03c_0002 (dependant) rolled back too")
    check(c.execute("SELECT name FROM projects WHERE id=%s", (pid,)).fetchone() == ("Keep me",), "S3 projects data kept")
print("S3 versions after 06a_0001:", sorted(versions(d2)))
ok("/new", d2, "upgrade", "head")
check(versions(d2) == {"57_0002"} and schema_hash(d2) == h1, "S3 re-upgrade restores schema")
ok("/new", d2, "downgrade", "0001")
check(versions(d2) == {"0001"}, "S3 downgrade 0001")
ok("/new", d2, "upgrade", "head")
check(versions(d2) == {"57_0002"} and schema_hash(d2) == h1, "S3 round trip from 0001 restores schema")

# S4 relative downgrades fail loudly, nothing moves
before = versions(d2)
for target in ("-1", "06a@-1", "03a@-1", "03c@-1"):
    r = alembic("/new", d2, "downgrade", target)
    check(r.returncode != 0 and versions(d2) == before, f"S4 downgrade {target} refused (rc={r.returncode}) and nothing moved: {(r.stdout + r.stderr).strip().splitlines()[-1][:110]}")

# S5 a new package revision on top of the single head
tmp = "/tmp/newcopy"
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree("/new/backend", tmp + "/backend")
os.makedirs(tmp + "/backend/alembic/versions", exist_ok=True)
open(tmp + "/backend/alembic/versions/zz_0001_probe.py", "w").write(
    'revision = "zz_0001"\ndown_revision = "57_0002"\nbranch_labels = ("zz",)\ndepends_on = None\n'
    'from alembic import op\n\ndef upgrade():\n    op.execute("CREATE TABLE zz_probe (id int)")\n\n'
    'def downgrade():\n    op.execute("DROP TABLE zz_probe")\n'
)
d5 = newdb()
ok(tmp, d5, "upgrade", "head")
check(versions(d5) == {"zz_0001"}, f"S5 new revision on single head: {versions(d5)}")
heads5 = [x for x in alembic(tmp, d5, "heads").stdout.splitlines() if x.strip()]
check(len(heads5) == 1, f"S5 still one head: {heads5}")
ok(tmp, d5, "downgrade", "-1")
check(versions(d5) == {"57_0002"}, f"S5 downgrade -1 on non-merge revision: {versions(d5)}")
ok(tmp, d5, "upgrade", "heads")
ok(tmp, d5, "downgrade", "zz@-1")
check(versions(d5) == {"57_0002"}, "S5 downgrade zz@-1")

# S6 older install (only some branches upgraded), then upgrade head
d6 = newdb()
ok("/base", d6, "upgrade", "04a_0001")
ok("/base", d6, "upgrade", "05a_0001")
print("S6 versions before:", sorted(versions(d6)))
ok("/new", d6, "upgrade", "head")
check(versions(d6) == {"57_0002"} and schema_hash(d6) == h1, f"S6 partial install -> head, same schema: {versions(d6)}")

# S7 ruff-ish sanity: no schema ops in merge files
for f in ("57_0001_join_dependency_heads.py", "57_0002_merge_heads.py"):
    src = open(f"/new/backend/alembic/versions/{f}").read()
    check("op." not in src and "execute" not in src, f"S7 {f} has no operations")

with admin() as c:
    for n in (d1, d1b, d2, d2b, d5, d6):
        c.execute(f'DROP DATABASE IF EXISTS "{n}" WITH (FORCE)')
print("FAILS:", FAILS)
sys.exit(1 if FAILS else 0)
