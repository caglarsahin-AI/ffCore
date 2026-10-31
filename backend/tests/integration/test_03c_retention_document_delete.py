"""03c FOLLOWUP-119 through the 04a API: deleting a document (or its knowledge base) clears the
text of the finished runs that showed it, in the same transaction as 116's run marking."""

from tests.integration import test_116_checkpoint_sources as t116
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    seed_run,
    turn,
)
from tests.integration.test_116_checkpoint_sources import (
    CHUNK_TEXT,
    _delete,
    _document,
    _hit,
    _kb_url,
)

# 116's world: a project, an admin client, a knowledge base and the run harness.
world = t116.world


def _answered_run(world, pg, doc_id):
    run_id = seed_run(pg, world["project"], definition())
    model = ScriptedModel(turn(f"Fesih: {CHUNK_TEXT} [1]."))
    assert world["harness"].run(run_id, Ports(model, ScriptedRetriever([_hit(doc_id)]))) == (
        "completed"
    )
    return run_id


def _texts(pg, run_id):
    answer = pg.execute(
        "SELECT payload->>'text' FROM run_events WHERE run_id = %s AND type = 'answer'", (run_id,)
    ).fetchone()[0]
    llm = pg.execute(
        "SELECT payload->'request_messages' FROM run_events WHERE run_id = %s"
        " AND type = 'llm_call'",
        (run_id,),
    ).fetchone()[0]
    output = pg.execute("SELECT output FROM runs WHERE id = %s", (run_id,)).fetchone()[0]
    return answer, llm, output


def test_03c_13_document_delete_clears_run_text(world, pg):
    doc_id = _document(world)
    run_id = _answered_run(world, pg, doc_id)
    before = _texts(pg, run_id)
    assert CHUNK_TEXT in before[0] and CHUNK_TEXT in str(before[1])
    _delete(world, doc_id)
    assert _texts(pg, run_id) == ("[cleared]", "[cleared]", "[cleared]")


def test_03c_13_knowledge_base_delete_clears_run_text(world, pg):
    doc_id = _document(world)
    run_id = _answered_run(world, pg, doc_id)
    response = world["admin"].delete(_kb_url(world, f"/{world['kb']}"))
    assert response.status_code == 204, response.text
    assert _texts(pg, run_id)[0] == "[cleared]"
