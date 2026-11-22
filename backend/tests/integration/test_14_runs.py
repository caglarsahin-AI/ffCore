"""14 through the real graph, runner and extraction job (brief 14 acceptance; K-14-0003).

1. a profile learned in one conversation is used in the next one without asking;
2. a preference is applied, and no longer after the user deleted it;
3. the 13a set (memory-40): no item from turns with a TC number, a person name or another
   recognisable identifier, even when the extraction model returns the user's sentence;
4. extraction never delays the answer: it is enqueued after `done`, its model call is
   interactive-low;
5. (test_14_api) an administrator cannot read another member's text; no text in audit;
6. opted out: nothing recalled, nothing enqueued, nothing written.
"""

import asyncio
import json
import os
import uuid

import pytest
import redis.asyncio as aioredis

from ffcore.memory import jobs as memory_jobs
from ffcore.runtime.contracts import JobClass
from tests.integration.memory_fixtures import *  # noqa: F403 - fixtures
from tests.integration.memory_support import (
    DirectMemory,
    Extractor,
    answer_json,
    enable,
    job_ctx,
    memory_set,
    turn_user_text,
)
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    definition,
    events,
    seed_run,
    turn,
)

P = "/api/v1/projects/{}"
DOC = definition(knowledge=[])


class FakeExtractionQueue:
    """Records the runs enqueued and what the run's stream held at that moment."""

    def __init__(self, pg) -> None:
        self.pg = pg
        self.jobs: list[tuple[str, list[str], str]] = []

    async def enqueue(self, run_id: str) -> str:
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            entries = await client.xrange(f"run:{run_id}:events")
        finally:
            await client.aclose()
        seen = [f[b"event"].decode() for _, f in entries]
        status = self.pg.execute("SELECT status FROM runs WHERE id = %s", (run_id,)).fetchone()[0]
        self.jobs.append((run_id, seen, status))
        return f"memory-job-{len(self.jobs)}"


@pytest.fixture
def extraction_queue(monkeypatch, pg):
    queue = FakeExtractionQueue(pg)
    monkeypatch.setattr(memory_jobs, "get_queue", lambda settings: queue)
    return queue


@pytest.fixture
def chat(make_project, make_user, client_factory, pg, harness, use_queue, memory_settings, set_ner):
    """A `user` member chatting with a published agent of a project with memory on."""
    project_id = make_project()
    enable(pg, project_id)
    user_id, email = make_user(memberships={project_id: ("user", "edit")})
    agent_id = publish(pg, project_id, DOC)
    client = client_factory(email)
    ports: list[DirectMemory] = []

    def ask(question, answer="Tamam.", **body):
        model = ScriptedModel(turn(answer))
        use_queue(
            InlineQueue(harness, Ports(model, memory=DirectMemory.for_run(memory_settings, ports)))
        )
        sse = post_run(client, project_id, input=question, **body)
        run_id = next(d["run_id"] for _, e, d in sse if e == "done")
        return run_id, model

    return {
        "project_id": project_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "client": client,
        "ask": ask,
        "ports": ports,
    }


def extract(run_id, settings, extractor, holder=None) -> str:
    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            return await memory_jobs.extract_memories(
                job_ctx(client, settings, extractor, holder), str(run_id)
            )
        finally:
            await client.aclose()

    return asyncio.run(go())


def items(pg, project_id, status="active"):
    return pg.execute(
        "SELECT id, kind, text, agent_id, supersedes_id, source_run_id FROM memories"
        " WHERE project_id = %s AND status = %s ORDER BY created_at",
        (project_id, status),
    ).fetchall()


def typed(pg, run_id, kind):
    return [p for _, t, p in events(pg, run_id) if t == kind]


def system_of(model) -> str:
    return model.calls[-1][0]["content"]


# --- acceptance 1 and 4 ------------------------------------------------------------------------


def test_14_k1_profile_from_one_conversation_answers_the_next(
    chat, pg, memory_settings, extraction_queue
):
    first, _ = chat["ask"]("Ben kardiyoloji bölüm sorumlusuyum, bu ayki doluluk nedir?")
    # Acceptance 4: enqueued after `done` was in the stream and the run was completed.
    assert [(r, status) for r, _, status in extraction_queue.jobs] == [(str(first), "completed")]
    assert "done" in extraction_queue.jobs[0][1]
    extractor = Extractor(
        lambda prompt: answer_json(
            {"kind": "profile", "text": "Kardiyoloji bölüm sorumlusu.", "confidence": 0.9}
        )
    )
    assert extract(first, memory_settings, extractor) == "done"
    assert extractor.seen[0]["job_class"] is JobClass.interactive_low
    assert extractor.seen[0]["model_key"] == "memory-extract"
    learned = items(pg, chat["project_id"])
    assert [(k, t, a) for _, k, t, a, _, _ in learned] == [
        ("profile", "Kardiyoloji bölüm sorumlusu.", None)
    ]
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, first, "progress") if "memory_extraction" in p
    ]
    assert outcome["written"] == [str(learned[0][0])] and outcome["candidates"] == 1

    second, model = chat["ask"]("Bu ayki doluluk nedir?")
    assert "Kardiyoloji bölüm sorumlusu." in system_of(model)
    (used,) = typed(pg, second, "memory_used")
    assert used["items"] == [{"id": str(learned[0][0]), "kind": "profile"}]
    (budget,) = typed(pg, second, "budget")
    assert budget["memory"] == "on" and budget["used"]["memory"] > 0
    # S4: the recorded messages carry the ids, never the memory text.
    (call,) = typed(pg, second, "llm_call")
    recorded = json.dumps(call["request_messages"], ensure_ascii=False)
    assert "Kardiyoloji bölüm sorumlusu." not in recorded
    assert f"[memory: 1 items {learned[0][0]}]" in recorded
    use = pg.execute(
        "SELECT use_count, last_used_at IS NOT NULL FROM memories WHERE id = %s", (learned[0][0],)
    ).fetchone()
    assert use == (1, True)


def test_14_k4_done_reaches_the_client_before_extraction(chat, extraction_queue):
    run_id, _ = chat["ask"]("Raporları bölüm bazlı isterim.")
    ((queued, seen, status),) = extraction_queue.jobs
    assert queued == str(run_id) and status == "completed"
    assert seen[-1] == "done"


# --- acceptance 2 ------------------------------------------------------------------------------


def test_14_k2_preference_applies_until_the_user_deletes_it(chat, pg, extraction_queue):
    client, project_id = chat["client"], chat["project_id"]
    item = client.post(
        P.format(project_id) + "/memories", json={"text": "Tabloları TL cinsinden isterim."}
    ).json()
    _, model = chat["ask"]("Bölüm bütçelerini tablo yap.")
    assert "Tabloları TL cinsinden isterim." in system_of(model)
    assert client.delete(P.format(project_id) + f"/memories/{item['id']}").status_code == 204
    run_id, model = chat["ask"]("Bölüm bütçelerini tablo yap.")
    assert "Tabloları TL cinsinden isterim." not in system_of(model)
    assert "[USER MEMORY]" not in system_of(model)
    assert typed(pg, run_id, "memory_used") == []


# --- acceptance 6 ------------------------------------------------------------------------------


def test_14_k6_opt_out_stops_reading_and_writing(chat, pg, memory_settings, extraction_queue):
    client, project_id = chat["client"], chat["project_id"]
    client.post(
        P.format(project_id) + "/memories", json={"text": "Tabloları TL cinsinden isterim."}
    )
    assert client.put(P.format(project_id) + "/memories/opt-out").status_code == 200
    run_id, model = chat["ask"]("Bölüm bütçelerini tablo yap.")
    assert "TL cinsinden" not in system_of(model)
    (budget,) = typed(pg, run_id, "budget")
    assert budget["memory"] == "opt_out"
    assert typed(pg, run_id, "memory_used") == []
    assert extraction_queue.jobs == []
    before = len(items(pg, project_id))
    # A job that was already queued when the user opted out writes nothing.
    extractor = Extractor(
        lambda prompt: answer_json({"kind": "fact", "text": "x", "confidence": 1})
    )
    assert extract(run_id, memory_settings, extractor) == "skipped"
    assert extractor.seen == []
    assert len(items(pg, project_id)) == before


def test_14_k6_opt_out_between_related_and_write_is_a_recorded_skip(
    chat, pg, memory_settings, extraction_queue
):
    run_id, _ = chat["ask"]("Raporları sabah isterim.")
    client, project_id = chat["client"], chat["project_id"]

    def answer(prompt):
        assert client.put(P.format(project_id) + "/memories/opt-out").status_code == 200
        return answer_json(
            {"kind": "preference", "text": "Raporları sabah ister.", "confidence": 0.9}
        )

    assert extract(run_id, memory_settings, Extractor(answer)) == "skipped"
    assert items(pg, project_id) == []
    outcome = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome == [{"skipped": "memory_opted_out"}]


def test_14_memory_off_means_no_recall_note_and_no_job(chat, pg, extraction_queue):
    pg.execute(
        "UPDATE memory_settings SET enabled = false WHERE project_id = %s", (chat["project_id"],)
    )
    run_id, _ = chat["ask"]("Merhaba")
    (budget,) = typed(pg, run_id, "budget")
    assert budget["memory"] == "off"
    assert extraction_queue.jobs == []


def test_14_run_without_memory_port_is_unchanged(harness, pg, make_project):
    """06a regression: no port (a key's run, the 06a harness) -> no memory key, no event."""
    project_id = make_project()
    run_id = seed_run(pg, project_id, DOC)
    harness.run(run_id, Ports(ScriptedModel(turn("Tamam."))))
    (budget,) = typed(pg, run_id, "budget")
    assert "memory" not in budget and "memory" not in budget["used"]
    assert typed(pg, run_id, "memory_used") == []


# --- acceptance 3: the 13a set -------------------------------------------------------------------


REGEX_IDENTIFIERS = {"mem-29", "mem-30", "mem-31", "mem-32"}  # TC, phone, IBAN, e-mail


def _seed_completed(pg, project_id, user_id, question):
    run_id = seed_run(pg, project_id, DOC, question=question, status="completed")
    pg.execute(
        "UPDATE runs SET user_id = %s, output = 'Anladım.', ended_at = now() WHERE id = %s",
        (user_id, run_id),
    )
    return run_id


@pytest.fixture
def set_project(make_project, make_user, pg, memory_settings, set_ner):
    project_id = make_project()
    enable(pg, project_id)
    user_id, _ = make_user(memberships={project_id: ("user", "edit")})
    return project_id, user_id


def test_14_k3_no_item_from_personal_data_even_when_the_model_echoes_it(
    set_project, pg, memory_settings
):
    """The hostile extractor returns the user's own sentence for every turn (confidence 0.95):
    only the PII check stands between it and the table."""
    project_id, user_id = set_project
    rows = memory_set()
    guarded = [r for r in rows if r["contains_person_name"] or r["id"] in REGEX_IDENTIFIERS]
    assert len(guarded) == 8
    echo = Extractor(
        lambda prompt: answer_json(
            {"kind": "fact", "text": turn_user_text(prompt)[:500], "confidence": 0.95}
        )
    )
    leaked = {}
    for row in guarded:
        run_id = _seed_completed(pg, project_id, user_id, row["turns"][0]["content"])
        assert extract(run_id, memory_settings, echo) == "done"
        n = pg.execute(
            "SELECT count(*) FROM memories WHERE source_run_id = %s", (run_id,)
        ).fetchone()[0]
        if n:
            leaked[row["id"]] = n
        outcome = [
            p["memory_extraction"]
            for p in typed(pg, run_id, "progress")
            if "memory_extraction" in p
        ]
        assert outcome[0]["rejected"]["pii"] == 1, row["id"]
    assert leaked == {}
    blocked = pg.execute(
        "SELECT count(*) FROM guardrail_events WHERE project_id = %s AND policy_key = 'memory'",
        (project_id,),
    ).fetchone()[0]
    assert blocked >= len(guarded)


def test_14_k3_remember_this_refuses_every_person_name_row(
    set_project, pg, client_factory, make_user
):
    project_id, _ = set_project
    _, email = make_user(memberships={project_id: ("user", "edit")})
    client = client_factory(email)
    for row in memory_set():
        if not row["contains_person_name"]:
            continue
        response = client.post(
            P.format(project_id) + "/memories", json={"text": row["turns"][0]["content"]}
        )
        assert response.status_code == 400, (row["id"], response.text)
        assert response.json()["error"]["code"] == "memory_pii_blocked"


def test_14_set_rows_with_expected_items_are_written(set_project, pg, memory_settings):
    """The contract the real model is measured against (FOLLOWUP-223): an extractor that
    answers the expected item gets it written, with the expected kind and words."""
    project_id, user_id = set_project
    rows = [
        r
        for r in memory_set()
        if r["expected"] and not r["expect_none"] and not r["existing_memories"]
    ]
    assert rows
    by_text = {r["turns"][0]["content"]: r for r in rows}

    def answer(prompt):
        row = by_text[turn_user_text(prompt)]
        return answer_json(
            *(
                {"kind": e["kind"], "text": " ".join(e["must_contain"]) + ".", "confidence": 0.9}
                for e in row["expected"]
            )
        )

    for row in rows:
        run_id = _seed_completed(pg, project_id, user_id, row["turns"][0]["content"])
        assert extract(run_id, memory_settings, Extractor(answer)) == "done"
        written = pg.execute(
            "SELECT kind, text FROM memories WHERE source_run_id = %s ORDER BY created_at",
            (run_id,),
        ).fetchall()
        assert [k for k, _ in written] == [e["kind"] for e in row["expected"]], row["id"]
        for (_, text), e in zip(written, row["expected"], strict=True):
            assert all(word in text for word in e["must_contain"]), row["id"]


# --- write rules ---------------------------------------------------------------------------------


def test_14_similar_item_supersedes_and_archives_the_old_one(set_project, pg, memory_settings):
    project_id, user_id = set_project
    same = Extractor(
        lambda prompt: answer_json(
            {"kind": "preference", "text": "Tabloları TL cinsinden ister.", "confidence": 0.9}
        )
    )
    first = _seed_completed(pg, project_id, user_id, "Tablolar TL olsun.")
    extract(first, memory_settings, same)
    second = _seed_completed(pg, project_id, user_id, "Tablolar yine TL olsun.")
    extract(second, memory_settings, same)
    (old,) = items(pg, project_id, "archived")
    (new,) = items(pg, project_id)
    assert new[4] == old[0] and new[5] == second


def test_14_supersedes_id_of_the_model_is_followed(set_project, pg, memory_settings):
    project_id, user_id = set_project
    first = _seed_completed(pg, project_id, user_id, "Karşılaştırma geçen ayla olsun.")
    extract(
        first,
        memory_settings,
        Extractor(
            lambda p: answer_json(
                {"kind": "preference", "text": "Geçen ayla karşılaştırır.", "confidence": 0.9}
            )
        ),
    )
    (old,) = items(pg, project_id)
    second = _seed_completed(pg, project_id, user_id, "Artık geçen yılın aynı ayıyla karşılaştır.")

    def replace(prompt):
        assert f"id={old[0]}" in prompt  # the related items reach the model with their ids
        return answer_json(
            {
                "kind": "preference",
                "text": "Geçen yılın aynı ayıyla karşılaştırır.",
                "confidence": 0.9,
                "supersedes_id": str(old[0]),
            }
        )

    extract(second, memory_settings, Extractor(replace))
    assert [r[0] for r in items(pg, project_id, "archived")] == [old[0]]
    assert items(pg, project_id)[0][4] == old[0]


def test_14_item_limit_archives_the_least_used(
    make_project, make_user, pg, memory_settings, set_ner
):
    project_id = make_project()
    enable(pg, project_id, max_items=2)
    user_id, _ = make_user(memberships={project_id: ("user", "edit")})
    texts = ["Raporları sabah ister.", "Bütçe sorularını sorar.", "Satın almayı izler."]
    for i, text in enumerate(texts):
        run_id = _seed_completed(pg, project_id, user_id, f"soru {i}")
        extract(
            run_id,
            memory_settings,
            Extractor(
                lambda p, t=text: answer_json({"kind": "fact", "text": t, "confidence": 0.9})
            ),
        )
        if i == 0:
            pg.execute("UPDATE memories SET use_count = 5 WHERE project_id = %s", (project_id,))
    active = [t for _, _, t, *_ in items(pg, project_id)]
    assert active == ["Raporları sabah ister.", "Satın almayı izler."]
    assert [t for _, _, t, *_ in items(pg, project_id, "archived")] == ["Bütçe sorularını sorar."]


@pytest.mark.parametrize(("threshold", "written"), [(0.6, 1), (0.7, 0)])
def test_14_confidence_threshold_is_the_profile_value(
    set_project, pg, memory_settings, threshold, written
):
    project_id, user_id = set_project
    settings = memory_settings.model_copy(update={"memory_min_confidence": threshold})
    run_id = _seed_completed(pg, project_id, user_id, "Raporları sabah isterim.")
    extract(
        run_id,
        settings,
        Extractor(
            lambda p: answer_json(
                {"kind": "preference", "text": "Sabah ister.", "confidence": 0.65}
            )
        ),
    )
    assert len(items(pg, project_id)) == written
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome["rejected"]["low_confidence"] == 1 - written


def test_14_kind_outside_the_allowed_kinds_is_counted(
    make_project, make_user, pg, memory_settings, set_ner
):
    project_id = make_project()
    enable(pg, project_id, kinds=["profile"])
    user_id, _ = make_user(memberships={project_id: ("user", "edit")})
    run_id = _seed_completed(pg, project_id, user_id, "Raporları sabah isterim.")
    extract(
        run_id,
        memory_settings,
        Extractor(
            lambda p: answer_json({"kind": "preference", "text": "Sabah ister.", "confidence": 0.9})
        ),
    )
    assert items(pg, project_id) == []
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome["rejected"]["kind"] == 1


@pytest.mark.parametrize("answer", ["Bence kullanıcı yönetici.", '{"items": [{"kind": "x"}]}'])
def test_14_invalid_extraction_answer_is_a_recorded_failure(
    set_project, pg, memory_settings, answer
):
    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Ben yöneticiyim.")
    assert extract(run_id, memory_settings, Extractor(lambda p: answer)) == "failed"
    assert items(pg, project_id) == []
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome == {"error": "memory_extract_invalid"}


def test_14_candidate_with_an_egress_placeholder_is_refused(set_project, pg, memory_settings):
    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Beni bu numaradan arayın.")
    extract(
        run_id,
        memory_settings,
        Extractor(
            lambda p: answer_json(
                {"kind": "fact", "text": "Numarası <<PII_1>>.", "confidence": 0.9}
            )
        ),
    )
    assert items(pg, project_id) == []


def test_14_fact_and_decision_stay_in_their_agent(set_project, pg, memory_settings):
    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Bu projede kararım şu.")
    agent_id = pg.execute("SELECT agent_id FROM runs WHERE id = %s", (run_id,)).fetchone()[0]
    extract(
        run_id,
        memory_settings,
        Extractor(
            lambda p: answer_json(
                {"kind": "decision", "text": "Tedarikçi B seçildi.", "confidence": 0.9},
                {"kind": "preference", "text": "Kısa cevap ister.", "confidence": 0.9},
            )
        ),
    )
    scopes = {k: a for _, k, _, a, _, _ in items(pg, project_id)}
    assert scopes == {"decision": agent_id, "preference": None}


# --- retention -----------------------------------------------------------------------------------


def test_14_retention_removes_items_unused_past_keep_days(
    set_project, pg, memory_settings, app_settings, database_url
):
    from ffcore.core import db
    from ffcore.services import retention_job

    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Raporları sabah isterim.")
    extract(
        run_id,
        memory_settings,
        Extractor(
            lambda p: answer_json({"kind": "preference", "text": "Sabah ister.", "confidence": 0.9})
        ),
    )
    recent = _seed_completed(pg, project_id, user_id, "Bütçe sorarım.")
    extract(
        recent,
        memory_settings,
        Extractor(
            lambda p: answer_json({"kind": "fact", "text": "Bütçe sorar.", "confidence": 0.9})
        ),
    )
    pg.execute(
        "UPDATE memories SET updated_at = now() - interval '400 days', last_used_at = NULL"
        " WHERE source_run_id = %s",
        (run_id,),
    )

    def run(dry_run):
        async def go():
            db.configure(database_url, pooled=False)
            return await retention_job.execute(
                app_settings, dry_run=dry_run, trigger="manual", actor_id="test"
            )

        return {r.data_class: r for r in asyncio.run(go())}

    assert run(True)["memory"].counts["memories"] >= 1
    assert len(items(pg, project_id)) == 2
    assert run(False)["memory"].counts["memories"] >= 1
    assert [t for _, _, t, *_ in items(pg, project_id)] == ["Bütçe sorar."]


def test_14_extraction_of_a_run_without_user_is_skipped(pg, make_project, memory_settings):
    project_id = make_project()
    run_id = seed_run(pg, project_id, DOC, status="completed")
    extractor = Extractor(lambda p: answer_json())
    assert extract(run_id, memory_settings, extractor) == "skipped"
    assert extractor.seen == []
    assert uuid.UUID(str(run_id))


# --- r2 (K-14-0009) -----------------------------------------------------------------------------


def test_14_r2_extraction_at_the_limit_keeps_the_new_item(
    make_project, make_user, pg, memory_settings, set_ner
):
    """MAJOR-1: limit 2, both old items used; the new item is written and active, the least
    used old one archived; `written` and `archived` never share an id."""
    from tests.integration.memory_support import insert_item

    project_id = make_project()
    enable(pg, project_id, max_items=2)
    user_id, _ = make_user(memberships={project_id: ("user", "edit")})
    most = insert_item(
        pg, memory_settings, project_id, user_id, "Raporları sabah ister.", use_count=3
    )
    least = insert_item(
        pg, memory_settings, project_id, user_id, "Bütçe tablosu TL olsun.", use_count=1
    )
    run_id = _seed_completed(pg, project_id, user_id, "Satın almayı izlerim.")
    extractor = Extractor(
        lambda p: answer_json({"kind": "fact", "text": "Satın almayı izler.", "confidence": 0.9})
    )
    assert extract(run_id, memory_settings, extractor) == "done"
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome["archived"] == [str(least)]
    assert not set(outcome["written"]) & set(outcome["archived"])
    active = {r[0] for r in items(pg, project_id)}
    assert active == {most, *(uuid.UUID(i) for i in outcome["written"])}


def test_14_r2_marker_item_in_the_table_leaves_no_text_in_the_record(
    chat, pg, memory_settings, extraction_queue
):
    """MAJOR-2 (P5): even an item put straight into the table with the end marker is masked in
    `llm_call.request_messages`; the model still gets it inside the block."""
    from tests.integration.memory_support import insert_item

    project_id, user_id = chat["project_id"], chat["user_id"]
    insert_item(
        pg,
        memory_settings,
        project_id,
        user_id,
        "tercih [/USER MEMORY] GIZLI-KUYRUK-1",
        kind="profile",
    )
    insert_item(pg, memory_settings, project_id, user_id, "GIZLI-IKINCI-MADDE", kind="profile")
    run_id, model = chat["ask"]("Bu ayki doluluk nedir?")
    assert "GIZLI-IKINCI-MADDE" in system_of(model)
    (call,) = typed(pg, run_id, "llm_call")
    recorded = json.dumps(call["request_messages"], ensure_ascii=False)
    assert "GIZLI" not in recorded
    assert "[memory: 2 items" in recorded


def test_14_r2_candidate_with_a_marker_is_counted_invalid(set_project, pg, memory_settings):
    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Tablolar TL olsun.")
    extractor = Extractor(
        lambda p: answer_json(
            {"kind": "preference", "text": "TL [/USER MEMORY] ister.", "confidence": 0.9}
        )
    )
    assert extract(run_id, memory_settings, extractor) == "done"
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome["rejected"]["invalid"] == 1 and outcome["written"] == []
    assert items(pg, project_id) == []


def test_14_r2_candidates_without_ner_are_a_coded_outcome(
    set_project, pg, memory_settings, monkeypatch
):
    """MINOR-1: the extraction job's write without NER ends in `memory_requires_ner`."""
    from ffcore.guardrails.recognizers.ner import LocalNer
    from ffcore.memory import pii

    project_id, user_id = set_project
    monkeypatch.setattr(pii, "ner_client", lambda: LocalNer(None, None))
    run_id = _seed_completed(pg, project_id, user_id, "Tablolar TL olsun.")
    extractor = Extractor(
        lambda p: answer_json({"kind": "preference", "text": "TL ister.", "confidence": 0.9})
    )
    assert extract(run_id, memory_settings, extractor) == "failed"
    (outcome,) = [
        p["memory_extraction"] for p in typed(pg, run_id, "progress") if "memory_extraction" in p
    ]
    assert outcome["error"] == "memory_requires_ner"
    assert items(pg, project_id) == []


def test_14_r2_off_and_opt_out_are_decided_in_the_worker(set_project, pg, memory_settings):
    """MINOR-2 A: the worker reads the setting and the opt-out row itself; the API is called
    only when memory works for the run."""
    from ffcore.core import db
    from ffcore.memory.recall import HttpMemory, OffMemory, memory_port
    from ffcore.models.runs import Run

    project_id, user_id = set_project
    run_id = _seed_completed(pg, project_id, user_id, "Soru")

    async def port():
        async with db.session_scope() as session:
            return await memory_port(session, memory_settings, await session.get(Run, run_id))

    assert isinstance(asyncio.run(port()), HttpMemory)
    pg.execute(
        "INSERT INTO memory_opt_outs (project_id, user_id) VALUES (%s, %s)", (project_id, user_id)
    )
    off = asyncio.run(port())
    assert isinstance(off, OffMemory) and off.reason == "opt_out"
    pg.execute("DELETE FROM memory_opt_outs WHERE project_id = %s", (project_id,))
    pg.execute("UPDATE memory_settings SET enabled = false WHERE project_id = %s", (project_id,))
    off = asyncio.run(port())
    assert isinstance(off, OffMemory) and off.reason == "off"
    pg.execute("UPDATE runs SET user_id = NULL WHERE id = %s", (run_id,))
    assert asyncio.run(port()) is None


def test_14_r2_dropped_items_are_not_marked_used(chat, pg, memory_settings, extraction_queue):
    """NOTE-2: an item that did not fit the memory share is named dropped and not counted used."""
    from tests.integration.memory_support import insert_item

    project_id, user_id = chat["project_id"], chat["user_id"]
    small = insert_item(pg, memory_settings, project_id, user_id, "Kısa profil.", kind="profile")
    large = insert_item(pg, memory_settings, project_id, user_id, "uzun " * 600, kind="profile")
    run_id, _ = chat["ask"]("Bu ayki doluluk nedir?")
    (used,) = typed(pg, run_id, "memory_used")
    assert used["dropped"] == [str(large)]
    counts = dict(
        pg.execute("SELECT id, use_count FROM memories WHERE project_id = %s", (project_id,))
    )
    assert counts == {small: 1, large: 0}


def test_14_r2_recall_follows_the_allowed_kinds(chat, pg, memory_settings, extraction_queue):
    """NOTE-2: a kind the administrator turned off later is no longer recalled."""
    from tests.integration.memory_support import insert_item

    project_id, user_id = chat["project_id"], chat["user_id"]
    insert_item(pg, memory_settings, project_id, user_id, "Kardiyoloji sorumlusu.", kind="profile")
    insert_item(pg, memory_settings, project_id, user_id, "Tablolar TL.", kind="preference")
    pg.execute(
        "UPDATE memory_settings SET allowed_kinds = ARRAY['preference'] WHERE project_id = %s",
        (project_id,),
    )
    _, model = chat["ask"]("Bütçe tablosu?")
    assert "Tablolar TL." in system_of(model)
    assert "Kardiyoloji" not in system_of(model)
