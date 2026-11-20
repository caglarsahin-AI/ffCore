"""11-1: the end user chat's read side (K-11-0002): published agents a member may chat with,
their own conversations and messages, soft delete, and the text of a cited source chunk."""

import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    source,
    turn,
)

P = "/api/v1/projects/{}"
QUESTION = "Hizmet sözleşmesinde fesih bildirim süresi kaç gündür ve hangi şartlarla uygulanır?"


def _url(project_id, path):
    return P.format(project_id) + path


def _insert_agent(pg, project_id, key, *, status="draft", kind="internal", deleted=False):
    agent_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, kind, status, created_by, deleted_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, 't', CASE WHEN %s THEN now() END)",
        (agent_id, project_id, key, key.upper(), kind, status, deleted),
    )
    return agent_id


@pytest.fixture
def chatting(make_project, make_user, client_factory, pg, harness, use_queue):
    """A project with one published agent and a `user` member who chats with it."""
    project_id = make_project()
    user_id, email = make_user(memberships={project_id: ("user", "edit")})
    publish(pg, project_id, definition())
    model = ScriptedModel(turn("30 gün [1]."), turn("Evet [1]."), turn("Tamam."))
    use_queue(InlineQueue(harness, Ports(model, ScriptedRetriever([source()]))))
    return project_id, user_id, client_factory(email), model


# --- chat agents ---------------------------------------------------------------------------


def test_11_1_chat_agents_lists_published_only(chatting, pg):
    project_id, _, client, _ = chatting
    _insert_agent(pg, project_id, "taslak")
    _insert_agent(pg, project_id, "silinmis", deleted=True)
    _insert_agent(pg, project_id, "dis", kind="external", status="published")
    response = client.get(_url(project_id, "/chat/agents"))
    assert response.status_code == 200, response.text
    assert [a["key"] for a in response.json()["items"]] == ["asistan"]


def test_11_1_chat_agents_carry_no_definition(chatting):
    # K-11-0002 S5: no definition, prompt, model or tool list reaches the chat.
    project_id, _, client, _ = chatting
    (agent,) = client.get(_url(project_id, "/chat/agents")).json()["items"]
    assert set(agent) == {"id", "key", "name", "description"}


def test_11_1_chat_agents_open_to_read_access(chatting, make_user, client_factory):
    project_id, *_ = chatting
    _, reader = make_user(memberships={project_id: ("analyst", "read")})
    response = client_factory(reader).get(_url(project_id, "/chat/agents"))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_11_1_chat_agents_hidden_from_non_members(chatting, make_user, client_factory):
    project_id, *_ = chatting
    _, outsider = make_user()
    assert client_factory(outsider).get(_url(project_id, "/chat/agents")).status_code == 404


# --- conversations ---------------------------------------------------------------------------


def test_11_2_title_is_first_60_characters_without_a_model_call(chatting, pg):
    project_id, _, client, model = chatting
    post_run(client, project_id, input=QUESTION)
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    assert conversation["title"] == QUESTION[:60].strip()
    # One model call: the answer. The title costs none (brief 11, PayCore D6).
    assert len(model.calls) == 1


def test_11_2_conversations_are_own_and_newest_first(chatting, make_user, client_factory):
    project_id, _, client, _ = chatting
    first = post_run(client, project_id, input="Birinci soru")[-1][2]
    second = post_run(client, project_id, input="İkinci soru")[-1][2]
    del first, second
    items = client.get(_url(project_id, "/conversations")).json()["items"]
    assert [c["title"] for c in items] == ["İkinci soru", "Birinci soru"]
    assert {c["agent_key"] for c in items} == {"asistan"}
    _, other = make_user(memberships={project_id: ("user", "edit")})
    assert client_factory(other).get(_url(project_id, "/conversations")).json()["items"] == []


def test_11_2_messages_in_order_with_sources_and_run_state(chatting, pg):
    project_id, _, client, _ = chatting
    events = post_run(client, project_id, input="Fesih süresi?")
    run_id = events[0][2]["run_id"]
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    response = client.get(_url(project_id, f"/conversations/{conversation['id']}/messages"))
    assert response.status_code == 200, response.text
    user, assistant = response.json()["items"]
    assert (user["role"], user["content"], user["run_id"]) == ("user", "Fesih süresi?", run_id)
    assert (assistant["role"], assistant["content"]) == ("assistant", "30 gün [1].")
    assert assistant["run_status"] == "completed" and user["run_status"] == "completed"
    (cited,) = assistant["sources"]
    assert cited["document_name"] == "hizmet-sozlesmesi.pdf" and "text" not in cited
    assert cited["updated_at_source"].startswith("2024-05-01")
    # Confidence badge off by default (brief 11, K3): no low-confidence flag is computed.
    assert assistant["low_confidence"] is None


def test_11_2_continuing_a_conversation_appends(chatting):
    project_id, _, client, _ = chatting
    post_run(client, project_id, input="Fesih süresi?")
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    post_run(client, project_id, input="Emin misin?", conversation_id=conversation["id"])
    items = client.get(_url(project_id, f"/conversations/{conversation['id']}/messages")).json()
    assert [m["content"] for m in items["items"]] == [
        "Fesih süresi?",
        "30 gün [1].",
        "Emin misin?",
        "Evet [1].",
    ]
    assert len(client.get(_url(project_id, "/conversations")).json()["items"]) == 1


def test_11_2_another_users_conversation_is_not_found(chatting, make_user, client_factory):
    project_id, _, client, _ = chatting
    post_run(client, project_id)
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    _, other = make_user(memberships={project_id: ("analyst", "edit")})
    stranger = client_factory(other)
    path = _url(project_id, f"/conversations/{conversation['id']}")
    assert stranger.get(path + "/messages").status_code == 404
    response = stranger.delete(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_11_2_delete_is_soft_audited_and_final(chatting, pg):
    project_id, _, client, _ = chatting
    post_run(client, project_id)
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    path = _url(project_id, f"/conversations/{conversation['id']}")
    assert client.delete(path).status_code == 204
    assert client.get(_url(project_id, "/conversations")).json()["items"] == []
    assert client.get(path + "/messages").status_code == 404
    assert client.delete(path).status_code == 404
    deleted_at = pg.execute(
        "SELECT deleted_at FROM conversations WHERE id = %s", (conversation["id"],)
    ).fetchone()[0]
    assert deleted_at is not None
    (row,) = audit_rows(pg, "delete_conversation", "success", project=project_id)
    # The title is the user's own words: never in the audit payload.
    assert conversation["title"] not in str(row)
    response = client.post(
        _url(project_id, "/agents/asistan/runs"),
        json={"input": "devam", "conversation_id": conversation["id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_11_2_read_access_member_deletes_own_conversation(
    chatting, make_user, client_factory, pg
):
    # brief 11: read-only users chat and delete their own conversations.
    project_id, *_ = chatting
    _, email = make_user(memberships={project_id: ("analyst", "read")})
    reader = client_factory(email)
    post_run(reader, project_id)
    (conversation,) = reader.get(_url(project_id, "/conversations")).json()["items"]
    assert reader.delete(_url(project_id, f"/conversations/{conversation['id']}")).status_code == 204


def test_11_2_conversations_filter_by_agent(chatting, pg):
    project_id, _, client, _ = chatting
    post_run(client, project_id)
    agent_id = client.get(_url(project_id, "/chat/agents")).json()["items"][0]["id"]
    assert len(client.get(_url(project_id, f"/conversations?agent_id={agent_id}")).json()["items"]) == 1
    other = uuid.uuid4()
    assert client.get(_url(project_id, f"/conversations?agent_id={other}")).json()["items"] == []


# --- source chunk ----------------------------------------------------------------------------


def _kb_document(pg, project_id, *, acl_roles=(), text="Madde 9 > Fesih\nFesih bildirimi 30 gün."):
    kb_id, document_id, chunk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, 'sozlesmeler', 'KB', 'BAAI/bge-m3',"
        " 8, 400, 0, true, true, 'BAAI/bge-reranker-v2-m3', 5, 'format-v1', 'test')",
        (kb_id, project_id),
    )
    pg.execute(
        "INSERT INTO documents (id, project_id, kb_id, filename, size, sha256, raw_path, status,"
        " acl_roles, updated_at_source, created_by) VALUES (%s, %s, %s, 'hizmet-sozlesmesi.pdf',"
        " 10, 'sha', 'raw/x', 'indexed', %s, '2024-05-01T00:00:00+00:00', 'test')",
        (document_id, project_id, kb_id, list(acl_roles)),
    )
    pg.execute(
        "INSERT INTO chunks (id, document_id, kb_id, ordinal, text, token_count, char_count, page,"
        " breadcrumb, text_hash) VALUES (%s, %s, %s, 0, %s, 5, %s, 3, 'Madde 9 > Fesih', 'h')",
        (chunk_id, document_id, kb_id, text, len(text)),
    )
    return document_id, chunk_id


@pytest.fixture
def cited(make_project, make_user, client_factory, pg, harness, use_queue):
    """A completed run of a `user` member that cited one real chunk (and one never cited)."""

    def make(*, acl_roles=()):
        project_id = make_project()
        _, email = make_user(memberships={project_id: ("user", "edit")})
        document_id, chunk_id = _kb_document(pg, project_id, acl_roles=acl_roles)
        hit = source()
        hit.chunk_id, hit.document_id = str(chunk_id), str(document_id)
        publish(pg, project_id, definition())
        use_queue(InlineQueue(harness, Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([hit]))))
        client = client_factory(email)
        run_id = post_run(client, project_id)[0][2]["run_id"]
        return project_id, client, run_id, document_id, chunk_id

    return make


def test_11_3_source_chunk_text_page_and_date(cited):
    project_id, client, run_id, document_id, chunk_id = cited()
    response = client.get(_url(project_id, f"/runs/{run_id}/sources/{chunk_id}"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "Madde 9 > Fesih\nFesih bildirimi 30 gün."
    assert (body["page"], body["document_name"]) == (3, "hizmet-sozlesmesi.pdf")
    assert body["document_id"] == str(document_id)
    assert body["updated_at_source"].startswith("2024-05-01")


def test_11_3_source_chunk_must_be_cited_by_the_run(cited, pg):
    project_id, client, run_id, _, _ = cited()
    other_document, other_chunk = uuid.uuid4(), uuid.uuid4()
    del other_document
    response = client.get(_url(project_id, f"/runs/{run_id}/sources/{other_chunk}"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"


def test_11_3_source_chunk_of_deleted_document(cited, pg):
    project_id, client, run_id, document_id, chunk_id = cited()
    pg.execute("UPDATE documents SET deleted_at = now() WHERE id = %s", (document_id,))
    response = client.get(_url(project_id, f"/runs/{run_id}/sources/{chunk_id}"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_deleted"


def test_11_3_source_chunk_acl_applies_to_the_caller(cited, pg, make_user, client_factory):
    # K-11-0002 S3: the caller's ACL, not the run owner's; a closed document says so.
    project_id, client, run_id, document_id, chunk_id = cited()
    pg.execute("UPDATE documents SET acl_roles = %s WHERE id = %s", (["admin"], document_id))
    response = client.get(_url(project_id, f"/runs/{run_id}/sources/{chunk_id}"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "source_not_visible"
    _, admin = make_user(memberships={project_id: ("admin", "edit")})
    allowed = client_factory(admin).get(_url(project_id, f"/runs/{run_id}/sources/{chunk_id}"))
    assert allowed.status_code == 200


def test_11_3_source_chunk_of_another_users_run_is_not_found(cited, make_user, client_factory):
    project_id, _, run_id, _, chunk_id = cited()
    _, other = make_user(memberships={project_id: ("user", "edit")})
    response = client_factory(other).get(_url(project_id, f"/runs/{run_id}/sources/{chunk_id}"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"
