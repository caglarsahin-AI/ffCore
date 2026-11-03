"""08-tam-1a, C17 at the agent path's exit, on the real Postgres and Redis token store.

The stored answer stays tokenized; the console stream (live and replay) and the facade agent
path turn placeholders back into values only for the run's own user (S8) and only when the
run's policy enforces no `pii` rule on the output; another reader sees the placeholders; a
placeholder the run never issued stays and is logged (S9)."""

import asyncio
import json
import logging
import os
import uuid

import redis.asyncio as aioredis

from ffcore.api.runs import (
    _replay_rows,
    detokenizer,
    exit_hook,
    exit_mode,
    is_run_owner,
    live_transform,
    policy_allows_reveal,
)
from ffcore.core import db
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.models.runs import Run
from tests.integration.runtime_support import definition, seed_run

NAME = "Ayşe Kaya"
STORED = "Sayın <<PII_1>>, başvurunuz alındı."


def _seed(pg, make_project, policy_key="default"):
    project_id = make_project()
    owner = uuid.uuid4()
    run_id = seed_run(
        pg,
        project_id,
        definition(knowledge=[], guardrail_policy_key=policy_key),
        status="completed",
    )
    pg.execute("UPDATE runs SET user_id = %s WHERE id = %s", (owner, run_id))
    pg.execute(
        "INSERT INTO run_events (run_id, seq, type, payload) VALUES (%s, 1, 'answer', %s)",
        (run_id, json.dumps({"text": STORED})),
    )
    return project_id, run_id, str(owner)


def _enforce_output_pii(pg, project_id, key):
    rules = [
        {"type": "pii", "action": "redact", "stages": ["output.pre"], "pii_policy_key": "default"}
    ]
    pg.execute(
        "INSERT INTO guardrail_policies (id, project_id, key, name, rules, mode, short_circuit,"
        " on_error, block_message, created_by) VALUES (%s, %s, %s, 'out', %s, 'enforce', true,"
        " 'block', '{}'::jsonb, 't')",
        (uuid.uuid4(), project_id, key, json.dumps(rules)),
    )


def _with(database_url, run_id, body):
    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 60)
            assert await store.token_for(str(run_id), "PERSON:" + NAME, NAME) == "<<PII_1>>"
            async with db.session_scope() as session:
                run = await session.get(Run, run_id)
                return await body(session, client, run)
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


async def _replayed(project_id, run_id, reveal):
    return [m.data async for m in _replay_rows(project_id, run_id, reveal)(0)]


def test_08t_7_console_owner_gets_values_others_placeholders(database_url, pg, make_project):
    project_id, run_id, owner = _seed(pg, make_project)

    async def body(session, client, run):
        assert await exit_mode(session, run, owner) == "reveal"
        assert await exit_mode(session, run, str(uuid.uuid4())) == "keep"  # another reader
        assert not is_run_owner(run, None)
        reveal = detokenizer(client, run_id)
        live = await live_transform(reveal)("token", {"text": STORED})
        return (
            live,
            await _replayed(project_id, run_id, reveal),
            await _replayed(project_id, run_id, None),
        )

    live, owner_replay, other_replay = _with(database_url, run_id, body)
    assert live == {"text": f"Sayın {NAME}, başvurunuz alındı."}
    assert owner_replay[0] == {"text": f"Sayın {NAME}, başvurunuz alındı."}
    assert other_replay[0] == {"text": STORED}
    stored = pg.execute("SELECT payload FROM run_events WHERE run_id = %s", (run_id,)).fetchone()
    assert stored[0]["text"] == STORED  # Postgres keeps the placeholders


def test_08t_9_enforced_output_pii_keeps_placeholders(database_url, pg, make_project, caplog):
    project_id, run_id, owner = _seed(pg, make_project, policy_key="out-pii")
    _enforce_output_pii(pg, project_id, "out-pii")

    async def body(session, client, run):
        mode = await exit_mode(session, run, owner)
        hook = exit_hook(client, run_id, mode)
        return mode, await policy_allows_reveal(session, run), await hook({"text": STORED})

    with caplog.at_level(logging.INFO, logger="ffcore.guardrails.masking"):
        mode, allowed, data = _with(database_url, run_id, body)
    assert (mode, allowed, data) == ("policy", False, {"text": STORED})
    assert f"detokenize_skipped_policy scope={run_id} count=1" in caplog.text
    assert NAME not in caplog.text


def test_08t_9_other_scope_placeholder_stays_and_is_logged(database_url, pg, make_project, caplog):
    _, run_id, _ = _seed(pg, make_project)

    async def body(session, client, run):
        return await detokenizer(client, run_id)({"text": "<<PII_1>> ve <<PII_7>>"})

    with caplog.at_level(logging.WARNING, logger="ffcore.guardrails.masking"):
        out = _with(database_url, run_id, body)
    assert out == {"text": f"{NAME} ve <<PII_7>>"}
    assert f"detokenize_unresolved scope={run_id} count=1" in caplog.text
    assert NAME not in caplog.text
