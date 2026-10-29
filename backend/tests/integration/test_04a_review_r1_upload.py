"""Review 04a r1 MAJOR-5 through the API: an oversized request is refused before its body is
parsed, a file over Kapı 0's limit is recorded as skipped and never stored, and the next normal
upload goes through."""

from pathlib import Path

import pytest

from ffcore.api.knowledge import queue_dependency
from ffcore.knowledge import scope

API = "/api/v1"
PROSE = "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir. " * 20


class FakeQueue:
    async def enqueue(self, function, *args):
        return "job"


@pytest.fixture
def world(app, app_settings, tmp_path, make_user, make_project, client_factory):
    from ffcore.core.config import get_settings

    storage = tmp_path / "storage"
    settings = app_settings.model_copy(
        update={
            "fake_embed": True,
            "knowledge_storage_dir": str(storage),
            "upload_max_request_bytes": 64 * 1024,
        }
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[queue_dependency] = FakeQueue
    project = make_project()
    _, admin = make_user(memberships={project: ("admin", "edit")})
    client = client_factory(admin)
    base = f"{API}/projects/{project}/knowledge-bases"
    kb = client.post(base, json={"key": "limitler", "name": "Limitler"}).json()["id"]
    return {"client": client, "url": f"{base}/{kb}/documents", "storage": storage, "kb": kb}


def files_in(storage: Path) -> list[Path]:
    return [p for p in storage.rglob("*") if p.is_file()] if storage.exists() else []


def test_04a_r1_5_request_over_the_limit_is_refused_unparsed(world, pg):
    body = b"x" * (64 * 1024 + 1)
    response = world["client"].post(
        world["url"], files={"files": ("big.md", body, "text/markdown")}
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "request_too_large"
    assert "big.md" not in response.text
    (count,) = pg.execute(
        "SELECT count(*) FROM documents WHERE kb_id = %s", (world["kb"],)
    ).fetchone()
    assert count == 0 and files_in(world["storage"]) == []
    ok = world["client"].post(
        world["url"], files={"files": ("ok.md", PROSE.encode(), "text/markdown")}
    )
    assert ok.status_code == 202, ok.text  # the next upload goes on


def test_04a_r1_5_file_over_gate0_limit_is_recorded_and_never_stored(world, pg, monkeypatch):
    monkeypatch.setattr(scope, "PLAINTEXT_MAX_BYTES", 1000)
    response = world["client"].post(
        world["url"], files={"files": ("notlar.txt", b"a" * 1001, "text/plain")}
    )
    assert response.status_code == 202, response.text
    document = response.json()["data"][0]["document"]
    assert document["status"] == "skipped" and document["gate0"]["reason"] == "too_large"
    assert document["size"] == 1001 and document["sha256"]
    (raw_path,) = pg.execute(
        "SELECT raw_path FROM documents WHERE id = %s", (document["id"],)
    ).fetchone()
    assert raw_path == "" and files_in(world["storage"]) == []  # no raw, no staging leftover
    ok = world["client"].post(
        world["url"], files={"files": ("ok.md", PROSE.encode(), "text/markdown")}
    )
    assert ok.status_code == 202 and ok.json()["data"][0]["document"]["status"] == "pending"
    stored = files_in(world["storage"])
    assert len(stored) == 1 and stored[0].name == "original.md"  # raw layout: original.<ext>
