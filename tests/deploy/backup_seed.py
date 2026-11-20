"""Small data for the backup/restore prova (12-2), run inside the tools container.

Reuses the 13b seed's API helpers (tests/e2e/scenarios/seed.py): a superadmin, one project
with an analyst member, the fake-llm models, one knowledge base with a Markdown document
(no Docling weights; FAKE_EMBED=1 from tests/e2e/scenarios/e2e.env), one published agent and
one chat run by the analyst. Prints one JSON line: ids, the document's sha256 and filename.

    docker compose ... --env-file tests/e2e/scenarios/e2e.env run --rm \
      -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD -e E2E_PASSWORD tools python tests/deploy/backup_seed.py

Passwords come from the environment the host test generates per run; nothing is written.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.e2e.scenarios import seed  # noqa: E402

PROJECT = {"key": "yedek-a", "name": "Backup prova A"}
ANALYST = "yedek-a-analyst@example.test"
KB = "yedek-belgeler"
AGENT = "yedek-asistan"
DOCUMENT = (
    "# Backup prova\n\nThe service contract renews every year on 1 March.\n"
    "Notice of termination is due three months before renewal.\n"
)


def main() -> None:
    email, password = seed.env("E2E_ADMIN_EMAIL"), seed.env("E2E_ADMIN_PASSWORD")
    member_password = seed.env("E2E_PASSWORD")
    admin = seed.ensure_superadmin(email, password)
    ids = seed.seed_projects(admin, {"projects": [PROJECT]})
    pid = ids[PROJECT["key"]]
    members = [{"email": ANALYST, "role": "analyst", "access": "edit"}]
    seed.seed_members(admin, {"projects": [{**PROJECT, "members": members}]}, ids, member_password)
    seed.seed_models(admin, ids)

    base = f"/projects/{pid}/knowledge-bases"
    kb = admin.create(base, {"key": KB, "name": KB}, lambda: admin.find(base, KB))
    data = DOCUMENT.encode()
    response = admin.call(
        "POST",
        f"{base}/{kb['id']}/documents",
        files={"files": ("prova.md", data)},
        data={"acl_open": "true"},
    )
    doc_id = response.json()["data"][0]["document"]["id"]
    seed.wait_indexed(admin, f"{base}/{kb['id']}", [doc_id])

    template = json.loads(
        (seed.SAMPLES / "agents" / "sozlesme-asistani.json").read_text(encoding="utf-8")
    )
    definition = {
        **template["definition"],
        "model": "chat-default",
        "knowledge": [{"kb_key": KB, "mode": "always", "top_k": 4, "min_score": None}],
    }
    seed._publish(admin, pid, AGENT, "Backup prova", "12-2 prova", definition)

    analyst = seed.Client(ANALYST, member_password)
    with analyst.http.stream(
        "POST", f"/projects/{pid}/agents/{AGENT}/runs", json={"input": "When does it renew?"}
    ) as stream:
        if stream.status_code != 200:
            raise seed.SeedError(f"run: {stream.status_code} {stream.read()[:300]!r}")
        events = "".join(stream.iter_text())
    if "error" in events and '"status": "completed"' not in events:
        raise seed.SeedError(f"run did not complete: {events[-300:]}")

    print(
        json.dumps(
            {
                "project_id": pid,
                "knowledge_base_id": kb["id"],
                "document_id": doc_id,
                "document_sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
