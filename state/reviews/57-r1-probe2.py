"""Reviewer probe 2 (57 r1): can ONE package revision be rolled back alone with a multi-target
downgrade? Tests the PR's "Kapsam daralması" claim (it cannot be expressed)."""
import os
import subprocess
import uuid

import psycopg
from sqlalchemy.engine import make_url

URL = os.environ["DATABASE_URL"]


def conn(db):
    return psycopg.connect(make_url(URL).set(drivername="postgresql", database=db).render_as_string(hide_password=False), autocommit=True)


def alembic(db, *args):
    env = {**os.environ, "DATABASE_URL": make_url(URL).set(database=db).render_as_string(hide_password=False)}
    return subprocess.run(["alembic", *args], cwd="/new/backend", env=env, capture_output=True, text=True)


name = "rev57b_" + uuid.uuid4().hex[:8]
with conn("postgres") as c:
    c.execute(f'CREATE DATABASE "{name}"')
print(alembic(name, "upgrade", "head").returncode)


def state():
    with conn(name) as c:
        v = sorted(r[0] for r in c.execute("SELECT version_num FROM alembic_version"))
        t = c.execute("SELECT to_regclass('approvals'), to_regclass('knowledge_bases'), to_regclass('retention_runs'), to_regclass('api_keys')").fetchone()
    return v, t


print("start", state())
for target in ("07_0001@-1", "07@-1", "57_0001,03c_0002,04a_0001,05a_0001,08_0001", "03a_0001+0", "57_0002-1"):
    r = alembic(name, "downgrade", target)
    print("TARGET", target, "rc", r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1][:140] if (r.stdout + r.stderr).strip() else "", state())
    if r.returncode == 0:
        print("UP", alembic(name, "upgrade", "head").returncode, state())
with conn("postgres") as c:
    c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
