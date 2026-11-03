"""08-tam-1a r1 MAJOR-2 on the facade agent path: the client's earlier turns are stored without a
run, so a placeholder kept in them could never be reversed in its own scope. They are stored as
checked before egress; the graph's egress tokenizes the history on every model call, so the
provider still sees placeholders (llmaas) and a later run never reads another scope's number."""

from tests.integration import test_06b_agent as base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue

agent = base.agent
EMAIL = "ayse.yilmaz@example.test"


def test_08t_m2_client_history_stored_before_egress(agent, harness, use_queue, pg):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, base._answer_ports()))
    history = [
        {"role": "user", "content": f"Benim adresim {EMAIL}"},
        {"role": "assistant", "content": "Not aldım."},
        {"role": "user", "content": "Fesih süresi nedir?"},
    ]
    response = client.chat(model, messages=history)
    assert response.status_code == 200, response.text
    rows = pg.execute(
        "SELECT role, content FROM messages WHERE conversation_id = %s AND run_id IS NULL"
        " ORDER BY created_at",
        (response.headers["X-Conversation-Id"],),
    ).fetchall()
    assert [tuple(r) for r in rows] == [(m["role"], m["content"]) for m in history[:2]]
    assert not any("<<PII_" in r[1] for r in rows)
