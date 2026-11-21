"""11-2: the end user's vote on an answer (K-11-0005 S1) and an agent's chat portal settings
(S2, S3): `messages.user_feedback` beside the expert's `messages.feedback`, and
`agents.portal_config`."""

import uuid

import pytest

from ffcore.core import tracing
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


def _url(project_id, path):
    return P.format(project_id) + path


class FakeScores:
    def __init__(self):
        self.scores = []

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


@pytest.fixture
def scores(monkeypatch):
    fake = FakeScores()
    monkeypatch.setattr(tracing, "get_client", lambda: fake)
    return fake


@pytest.fixture
def answered(make_project, make_user, client_factory, pg, harness, use_queue):
    """A `user` member's completed chat run with a Langfuse trace id."""
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("user", "edit")})
    publish(pg, project_id, definition())
    use_queue(
        InlineQueue(
            harness, Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([source()]))
        )
    )
    client = client_factory(email)
    run_id = post_run(client, project_id, channel="chat")[0][2]["run_id"]
    pg.execute("UPDATE runs SET langfuse_trace_id = 'trace-11-2' WHERE id = %s", (run_id,))
    return project_id, client, run_id


def _columns(pg, run_id):
    return pg.execute(
        "SELECT feedback, user_feedback FROM messages WHERE run_id = %s AND role = 'assistant'",
        (run_id,),
    ).fetchone()


# --- the end user's vote (S1) ------------------------------------------------------------------


def test_11_2_chat_vote_goes_to_user_feedback_and_its_own_score(answered, pg, scores):
    project_id, client, run_id = answered
    response = client.post(
        _url(project_id, f"/runs/{run_id}/feedback"),
        json={"vote": "wrong", "note": "Madde yanlış.", "source": "chat"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["score_sent"] is True
    expert, user = _columns(pg, run_id)
    assert expert is None
    assert (user["vote"], user["note"]) == ("wrong", "Madde yanlış.")
    assert user["by"] and user["at"]
    assert [(s["name"], s["value"], s["trace_id"]) for s in scores.scores] == [
        ("user_feedback", "wrong", "trace-11-2")
    ]
    assert audit_rows(pg, "give_feedback", "success")


def test_11_2_chat_vote_leaves_the_expert_review_queue_alone(
    answered, pg, scores, make_user, client_factory
):
    # S1: a chat vote does not take the run out of F9's pending list, and the expert's later
    # vote does not overwrite it.
    project_id, client, run_id = answered
    client.post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "chat"}
    )
    _, email = make_user(memberships={project_id: ("analyst", "edit")})
    expert = client_factory(email)
    pending = expert.get(_url(project_id, "/runs"), params={"feedback": "pending"}).json()["items"]
    assert [r["id"] for r in pending] == [run_id]
    assert (
        expert.post(
            _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "partial"}
        ).status_code
        == 200
    )
    stored_expert, stored_user = _columns(pg, run_id)
    assert (stored_expert["vote"], stored_user["vote"]) == ("partial", "correct")
    assert [s["name"] for s in scores.scores] == ["user_feedback", "expert_feedback"]


def test_11_2_review_is_still_the_default_source(answered, pg, scores, make_user, client_factory):
    project_id, _, run_id = answered
    _, email = make_user(memberships={project_id: ("analyst", "edit")})
    response = client_factory(email).post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct"}
    )
    assert response.status_code == 200, response.text
    expert, user = _columns(pg, run_id)
    assert (expert["vote"], user) == ("correct", None)
    assert [s["name"] for s in scores.scores] == ["expert_feedback"]


@pytest.mark.parametrize("body", [{"vote": "correct"}, {"vote": "correct", "source": "review"}])
def test_11_2_r2_user_member_cannot_write_the_expert_review(
    answered, pg, scores, make_user, client_factory, body
):
    # 11-2 r1 MINOR-1 (A): a `user` member's default (review) vote is refused, so it can neither
    # take the run out of F9's pending list nor show as an expert score; the chat vote stays open.
    project_id, client, run_id = answered
    response = client.post(_url(project_id, f"/runs/{run_id}/feedback"), json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_reviewer"
    assert _columns(pg, run_id) == (None, None)
    assert scores.scores == []
    _, email = make_user(memberships={project_id: ("analyst", "edit")})
    pending = client_factory(email).get(_url(project_id, "/runs"), params={"feedback": "pending"})
    assert [r["id"] for r in pending.json()["items"]] == [run_id]
    chat = client.post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "chat"}
    )
    assert chat.status_code == 200


def test_11_2_chat_vote_only_by_the_runs_user(answered, make_user, client_factory):
    project_id, _, run_id = answered
    _, email = make_user(memberships={project_id: ("admin", "edit")})
    response = client_factory(email).post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "chat"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_run_user"


def test_11_2_chat_vote_needs_edit_access(
    make_project, make_user, client_factory, pg, harness, use_queue
):
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("analyst", "read")})
    publish(pg, project_id, definition())
    use_queue(InlineQueue(harness, Ports(ScriptedModel(turn("Tamam.")), ScriptedRetriever([]))))
    reader = client_factory(email)
    run_id = post_run(reader, project_id, channel="chat")[0][2]["run_id"]
    response = reader.post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "chat"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"


def test_11_2_chat_vote_source_is_a_closed_list(answered):
    project_id, client, run_id = answered
    response = client.post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "slack"}
    )
    assert response.status_code == 422


def test_11_2_messages_carry_the_user_vote(answered, scores):
    project_id, client, run_id = answered
    client.post(
        _url(project_id, f"/runs/{run_id}/feedback"), json={"vote": "correct", "source": "chat"}
    )
    (conversation,) = client.get(_url(project_id, "/conversations")).json()["items"]
    items = client.get(_url(project_id, f"/conversations/{conversation['id']}/messages")).json()[
        "items"
    ]
    answer = next(m for m in items if m["role"] == "assistant")
    assert answer["user_feedback"]["vote"] == "correct"
    assert answer["feedback"] is None
    question = next(m for m in items if m["role"] == "user")
    assert question["user_feedback"] is None


# --- portal settings (S2, S3) ------------------------------------------------------------------

PORTAL = {
    "welcome": "Sözleşmeler hakkında sorun.",
    "examples": ["Fesih süresi nedir?", "Cezai şart var mı?"],
    "accent": "#0F766E",
}


@pytest.fixture
def portal(make_project, make_user, client_factory, pg):
    project_id = make_project()
    _, editor = make_user(memberships={project_id: ("analyst", "edit")})
    publish(pg, project_id, definition())
    agent_id = pg.execute(
        "SELECT id FROM agents WHERE project_id = %s AND key = 'asistan'", (project_id,)
    ).fetchone()[0]
    return project_id, str(agent_id), client_factory(editor)


def test_11_2_portal_config_saved_audited_and_shown_in_chat(portal, pg, make_user, client_factory):
    project_id, agent_id, editor = portal
    response = editor.patch(_url(project_id, f"/agents/{agent_id}"), json={"portal_config": PORTAL})
    assert response.status_code == 200, response.text
    assert response.json()["portal_config"] == PORTAL
    assert editor.get(_url(project_id, f"/agents/{agent_id}")).json()["portal_config"] == PORTAL
    assert audit_rows(pg, "update_agent", "success")
    _, email = make_user(memberships={project_id: ("user", "edit")})
    (agent,) = client_factory(email).get(_url(project_id, "/chat/agents")).json()["items"]
    assert agent["portal_config"] == PORTAL


def test_11_2_portal_config_is_empty_until_set_and_null_clears_it(portal):
    project_id, agent_id, editor = portal
    assert editor.get(_url(project_id, f"/agents/{agent_id}")).json()["portal_config"] is None
    editor.patch(_url(project_id, f"/agents/{agent_id}"), json={"portal_config": PORTAL})
    response = editor.patch(_url(project_id, f"/agents/{agent_id}"), json={"portal_config": None})
    assert response.status_code == 200 and response.json()["portal_config"] is None


def test_11_2_portal_config_fields_are_optional(portal):
    project_id, agent_id, editor = portal
    response = editor.patch(
        _url(project_id, f"/agents/{agent_id}"), json={"portal_config": {"welcome": "Merhaba."}}
    )
    assert response.status_code == 200, response.text
    assert response.json()["portal_config"] == {
        "welcome": "Merhaba.",
        "examples": [],
        "accent": None,
    }


@pytest.mark.parametrize(
    "config",
    [
        {"welcome": "x" * 501},
        {"examples": ["a", "b", "c", "d"]},
        {"examples": ["x" * 201]},
        {"examples": [""]},
        {"examples": ["   "]},
        {"accent": "teal"},
        {"accent": "#0F766"},
        {"accent": "0F766E"},
        {"theme": "dark"},
    ],
)
def test_11_2_portal_config_is_validated(portal, config):
    project_id, agent_id, editor = portal
    response = editor.patch(_url(project_id, f"/agents/{agent_id}"), json={"portal_config": config})
    assert response.status_code == 422, (config, response.text)


def test_11_2_portal_config_needs_edit_access(portal, make_user, client_factory):
    project_id, agent_id, _ = portal
    _, email = make_user(memberships={project_id: ("analyst", "read")})
    response = client_factory(email).patch(
        _url(project_id, f"/agents/{agent_id}"), json={"portal_config": PORTAL}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "read_only_access"


def test_11_2_portal_config_of_a_missing_agent(portal):
    project_id, _, editor = portal
    response = editor.patch(
        _url(project_id, f"/agents/{uuid.uuid4()}"), json={"portal_config": PORTAL}
    )
    assert response.status_code == 404
