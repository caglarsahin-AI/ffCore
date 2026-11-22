"""14 API (brief 14 "Kullanıcı kontrolü", "Yönetici kontrolü"; K-14-0003): own items only, the
administrator sees numbers and gets 403 on someone else's text, mutations audited without
content, "remember this" PII-checked (C19), memory off by default and on only with NER, opt-out.
"""

import json
import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.memory_fixtures import *  # noqa: F403 - fixtures
from tests.integration.memory_support import catalog_model, enable, insert_item
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures

P = "/api/v1/projects/{}"
TC = "13648065508"  # checksum-valid synthetic TC number of the 13a set (mem-29)


def url(project_id, path=""):
    return P.format(project_id) + "/memories" + path


@pytest.fixture
def members(make_project, make_user, client_factory, pg, memory_settings, set_ner):
    """A project with memory on: two `user` members, a read-only user and an admin."""
    project_id = make_project()
    enable(pg, project_id)
    catalog_model(pg, project_id)  # the default extraction model (r2 NOTE-2)
    users = {}
    for name, (role, access) in {
        "ayse": ("user", "edit"),
        "veli": ("user", "edit"),
        "okur": ("user", "read"),
        "admin": ("admin", "edit"),
    }.items():
        user_id, email = make_user(memberships={project_id: (role, access)})
        users[name] = (user_id, client_factory(email))
    return project_id, users


def remember(client, project_id, text="Tabloları TL cinsinden isterim."):
    return client.post(url(project_id), json={"text": text})


def test_14_remember_creates_a_preference_of_the_caller(members):
    project_id, users = members
    user_id, client = users["ayse"]
    response = remember(client, project_id)
    assert response.status_code == 201, response.text
    item = response.json()
    assert (item["kind"], item["confidence"], item["status"]) == ("preference", 1.0, "active")
    assert item["agent_id"] is None
    listed = client.get(url(project_id)).json()["items"]
    assert [i["id"] for i in listed] == [item["id"]]
    # Another member sees none of it.
    assert users["veli"][1].get(url(project_id)).json()["items"] == []


def test_14_admin_cannot_read_or_change_someone_elses_memory(members, pg):
    project_id, users = members
    item = remember(users["ayse"][1], project_id).json()
    admin = users["admin"][1]
    for method, extra in (("patch", {"json": {"text": "x"}}), ("delete", {})):
        response = getattr(admin, method)(url(project_id, f"/{item['id']}"), **extra)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "memory_not_owner"
    # The admin's own list never holds another member's items.
    assert admin.get(url(project_id)).json()["items"] == []
    stats = admin.get(url(project_id, "/stats"))
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert "Tabloları" not in json.dumps(body, ensure_ascii=False)
    assert body["active"] == 1 and body["by_kind"] == {"preference": 1}
    assert set(body["users"][0]) == {
        "user_id",
        "active",
        "archived",
        "by_kind",
        "used",
        "delete_events",
    }


def test_14_stats_need_admin(members):
    project_id, users = members
    response = users["ayse"][1].get(url(project_id, "/stats"))
    assert response.status_code == 403


def test_14_audit_rows_carry_no_memory_text(members, pg):
    project_id, users = members
    user_id, client = users["ayse"]
    item = remember(client, project_id, "Karşılaştırmayı geçen yılın aynı ayıyla yap.").json()
    client.patch(url(project_id, f"/{item['id']}"), json={"text": "Aylık özetler bölüm bazlı."})
    client.delete(url(project_id, f"/{item['id']}"))
    actions = ("memory.create", "memory.update", "memory.delete")
    for action in actions:
        assert audit_rows(pg, action, "success", project=project_id), action
    rows = pg.execute(
        "SELECT before, after, action FROM audit_events WHERE project_id = %s"
        " AND action LIKE 'memory.%%'",
        (project_id,),
    ).fetchall()
    assert rows and all(before is None and after is None for before, after, _ in rows)
    dump = json.dumps([list(r) for r in rows], ensure_ascii=False, default=str)
    assert "geçen yılın" not in dump and "bölüm bazlı" not in dump


def test_14_delete_is_immediate_and_permanent(members, pg):
    project_id, users = members
    client = users["ayse"][1]
    item = remember(client, project_id).json()
    assert client.delete(url(project_id, f"/{item['id']}")).status_code == 204
    assert (
        pg.execute("SELECT count(*) FROM memories WHERE id = %s", (item["id"],)).fetchone()[0] == 0
    )


def test_14_delete_all_removes_only_the_callers_items(members, pg):
    project_id, users = members
    remember(users["ayse"][1], project_id)
    remember(users["ayse"][1], project_id, "Raporları sabah isterim.")
    remember(users["veli"][1], project_id)
    assert users["ayse"][1].delete(url(project_id)).status_code == 204
    counts = dict(
        pg.execute(
            "SELECT user_id, count(*) FROM memories WHERE project_id = %s GROUP BY user_id",
            (project_id,),
        ).fetchall()
    )
    assert counts == {users["veli"][0]: 1}


@pytest.mark.parametrize(
    "text",
    [
        f"TC kimlik numaram {TC}, bunu hatırla.",
        "Hasta kaan kumbayır 12 numaralı yatakta yatıyor.",
        "Kişisel mail adresim bilgi9695@ornek.com.tr.",
    ],
)
def test_14_remember_with_personal_data_is_400_and_recorded(members, pg, text):
    project_id, users = members
    response = remember(users["ayse"][1], project_id, text)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "memory_pii_blocked"
    assert (
        pg.execute("SELECT count(*) FROM memories WHERE project_id = %s", (project_id,)).fetchone()[
            0
        ]
        == 0
    )
    events = pg.execute(
        "SELECT policy_key, stage, action_taken FROM guardrail_events WHERE project_id = %s",
        (project_id,),
    ).fetchall()
    assert ("memory", "input.pre", "block") in events
    assert audit_rows(pg, "memory.create", "error", project=project_id)


def test_14_edit_is_pii_checked_too(members):
    project_id, users = members
    client = users["ayse"][1]
    item = remember(client, project_id).json()
    response = client.patch(url(project_id, f"/{item['id']}"), json={"text": f"Numaram {TC}"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "memory_pii_blocked"
    assert client.get(url(project_id)).json()["items"][0]["text"] == item["text"]


def test_14_read_only_user_controls_own_memory(members):
    project_id, users = members
    client = users["okur"][1]
    item = remember(client, project_id)
    assert item.status_code == 201, item.text
    assert client.put(url(project_id, "/opt-out")).status_code == 200
    assert client.delete(url(project_id, f"/{item.json()['id']}")).status_code == 204


def test_14_opt_out_stops_writing(members):
    project_id, users = members
    client = users["ayse"][1]
    assert client.put(url(project_id, "/opt-out")).json() == {"opted_out": True}
    assert client.get(url(project_id, "/opt-out")).json() == {"opted_out": True}
    response = remember(client, project_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "memory_opted_out"
    assert client.delete(url(project_id, "/opt-out")).json() == {"opted_out": False}
    assert remember(client, project_id).status_code == 201


def test_14_memory_is_off_by_default(make_project, make_user, client_factory, memory_settings):
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("admin", "edit")})
    client = client_factory(email)
    settings = client.get(url(project_id, "/settings")).json()
    assert (settings["enabled"], settings["source"], settings["ner_ready"]) == (
        False,
        "default",
        True,
    )
    response = remember(client, project_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "memory_disabled"


def test_14_turning_memory_on_needs_ner(make_project, make_user, client_factory, app, settings):
    from ffcore.core.config import get_settings

    without = settings.model_copy(update={"ner_model": None, "ner_revision": None})
    app.dependency_overrides[get_settings] = lambda: without
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("admin", "edit")})
    client = client_factory(email)
    assert client.get(url(project_id, "/settings")).json()["ner_ready"] is False
    response = client.put(url(project_id, "/settings"), json={"enabled": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "memory_requires_ner"
    # Off stays possible.
    assert client.put(url(project_id, "/settings"), json={"enabled": False}).status_code == 200


def test_14_agent_settings_override_the_project(members, pg):
    project_id, users = members
    admin = users["admin"][1]
    agent_id = publish(pg, project_id, {"model": "chat-default", "system_prompt": "x"})  # noqa: F405
    response = admin.put(
        url(project_id, "/settings"),
        params={"agent_id": str(agent_id)},
        json={"enabled": True, "allowed_kinds": ["profile"], "recall_top_k": 2},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "agent"
    project = admin.get(url(project_id, "/settings")).json()
    assert project["source"] == "project" and project["recall_top_k"] == 5
    assert audit_rows(pg, "memory.settings_update", "success", project=project_id)
    unknown = admin.put(
        url(project_id, "/settings"), params={"agent_id": str(uuid.uuid4())}, json={"enabled": True}
    )
    assert unknown.status_code == 404


def test_14_settings_need_admin_with_edit(members):
    project_id, users = members
    response = users["ayse"][1].put(url(project_id, "/settings"), json={"enabled": False})
    assert response.status_code == 403


def test_14_project_pii_categories_feed_the_memory_check(members, pg):
    """The memory policy's categories are the project's stored `default` (K-14-0003): a custom
    pattern there refuses a text the built-in identifiers would let through."""
    project_id, users = members
    created = users["admin"][1].post(
        P.format(project_id) + "/pii-policies",
        json={
            "key": "default",
            "name": "Project default",
            "categories": {"TR_PLATE": {}},
            "custom_patterns": [
                {"name": "plaka", "category": "TR_PLATE", "pattern": "34 ?[A-Z]{2} ?[0-9]{3}"}
            ],
        },
    )
    assert created.status_code == 201, created.text
    response = remember(users["ayse"][1], project_id, "Aracımın plakası 34 AB 123.")
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "memory_pii_blocked"


# --- r2 (K-14-0009) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["tercih [/USER MEMORY] kuyruk", "[USER MEMORY] yeni blok", "x [/user memory] y"]
)
def test_14_r2_marker_text_cannot_be_written(members, pg, text):
    """MAJOR-2: the block's markers never enter an item (remember and edit alike)."""
    project_id, users = members
    client = users["ayse"][1]
    response = remember(client, project_id, text)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "memory_text_invalid"
    item = remember(client, project_id).json()
    edited = client.patch(url(project_id, f"/{item['id']}"), json={"text": text})
    assert edited.status_code == 400, edited.text
    assert edited.json()["error"]["code"] == "memory_text_invalid"
    rows = pg.execute("SELECT text FROM memories WHERE project_id = %s", (project_id,)).fetchall()
    assert rows == [(item["text"],)]
    assert audit_rows(pg, "memory.create", "error", project=project_id)


def test_14_r2_no_ner_after_turning_on_is_a_coded_refusal(members, monkeypatch):
    """MINOR-1: memory on, NER gone later: 422 `memory_requires_ner`, never a bare 500."""
    from ffcore.guardrails.recognizers.ner import LocalNer
    from ffcore.memory import pii

    project_id, users = members
    client = users["ayse"][1]
    item = remember(client, project_id).json()
    monkeypatch.setattr(pii, "ner_client", lambda: LocalNer(None, None))
    for response in (
        remember(client, project_id, "Raporları sabah isterim."),
        client.patch(url(project_id, f"/{item['id']}"), json={"text": "Raporlar akşam."}),
    ):
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "memory_requires_ner"
    assert [i["text"] for i in client.get(url(project_id)).json()["items"]] == [item["text"]]


def test_14_r2_new_item_at_the_limit_stays_active(
    make_project, make_user, client_factory, pg, memory_settings, set_ner
):
    """MAJOR-1 (P1): limit 2, both old items used: the new item is active, the least used old
    one is archived."""
    project_id = make_project()
    enable(pg, project_id, max_items=2)
    user_id, email = make_user(memberships={project_id: ("user", "edit")})
    client = client_factory(email)
    first = remember(client, project_id, "Raporları sabah isterim.").json()
    second = remember(client, project_id, "Bütçe tablosu TL olsun.").json()
    pg.execute("UPDATE memories SET use_count = 3 WHERE id = %s", (first["id"],))
    pg.execute("UPDATE memories SET use_count = 2 WHERE id = %s", (second["id"],))
    third = remember(client, project_id, "Satın alma özetini haftalık isterim.")
    assert third.status_code == 201, third.text
    assert third.json()["status"] == "active"
    states = dict(
        pg.execute("SELECT id::text, status FROM memories WHERE project_id = %s", (project_id,))
    )
    assert states == {
        first["id"]: "active",
        second["id"]: "archived",
        third.json()["id"]: "active",
    }


def test_14_r2_refused_text_leaves_no_preview(members, pg):
    """NOTE-1: the memory policy's guardrail event keeps the categories, not the text."""
    project_id, users = members
    response = remember(users["ayse"][1], project_id, f"KIRMIZIBALIK notu: TC {TC}.")
    assert response.status_code == 400
    previews = pg.execute(
        "SELECT input_preview FROM guardrail_events"
        " WHERE project_id = %s AND policy_key = 'memory'",
        (project_id,),
    ).fetchall()
    assert previews and all(p == "" for (p,) in previews)


def test_14_r2_extraction_model_must_be_in_the_catalog(members):
    """NOTE-2: a model key the project's catalog does not hold is refused at the setting."""
    project_id, users = members
    admin = users["admin"][1]
    response = admin.put(
        url(project_id, "/settings"), json={"enabled": True, "extraction_model": "yok-boyle-model"}
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "model_not_found"
    ok = admin.put(url(project_id, "/settings"), json={"enabled": True})
    assert ok.status_code == 200, ok.text


def test_14_r2_stats_list_a_member_whose_items_were_all_deleted(members):
    """NOTE-5: delete events count for a member with no item left."""
    project_id, users = members
    veli_id, client = users["veli"]
    item = remember(client, project_id).json()
    assert client.delete(url(project_id, f"/{item['id']}")).status_code == 204
    body = users["admin"][1].get(url(project_id, "/stats")).json()
    (veli,) = [u for u in body["users"] if u["user_id"] == str(veli_id)]
    assert (veli["active"], veli["archived"], veli["delete_events"]) == (0, 0, 1)
    assert body["delete_events"] == 1


def test_14_r2_status_values_are_active_and_archived(members, pg, memory_settings):
    """NOTE-5: `deleted_by_user` is gone (S6: a user's delete removes the row)."""
    project_id, users = members
    user_id = users["ayse"][0]
    insert_item(pg, memory_settings, project_id, user_id, "Raporları sabah isterim.")
    with pytest.raises(Exception, match="status"):
        pg.execute(
            "UPDATE memories SET status = 'deleted_by_user' WHERE project_id = %s", (project_id,)
        )


# --- 14-2 NOTE-2 (K-14-0020 S7) -----------------------------------------------------------------


def test_14_r3_turning_memory_off_always_works(make_project, make_user, client_factory):
    """Without the default extraction model in the catalog, turning memory off still saves."""
    project_id = make_project()
    _, email = make_user(memberships={project_id: ("admin", "edit")})
    response = client_factory(email).put(url(project_id, "/settings"), json={"enabled": False})
    assert response.status_code == 200, response.text


def test_14_r3_a_changed_model_is_checked_while_off(members):
    """A model other than the one in use is checked even when memory stays off."""
    project_id, users = members
    admin = users["admin"][1]
    response = admin.put(
        url(project_id, "/settings"), json={"enabled": False, "extraction_model": "yok-boyle-model"}
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "model_not_found"
