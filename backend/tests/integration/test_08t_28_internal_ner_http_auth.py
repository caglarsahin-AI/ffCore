"""08 tam 1b r1 NOTE-9: the internal NER endpoint over HTTP: anonymous 401, a project member
(admin) 403 `service_account_required`, the service account 200 with spans and no values.

The unit test 08t_6d calls the function with `actor=None`; this is the authorization itself."""

from ffcore.guardrails.findings import Finding
from tests.integration.test_08_api import SERVICE, admin, project  # noqa: F401  (fixtures)

URL = "/api/v1/internal/guardrails/ner"
BODY = {"text": "Bay Ayşe Demir geldi", "categories": ["PERSON"]}


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    async def find(self, text, categories):
        start = text.find("Ayşe Demir")
        return [Finding("PERSON", start, start + 10, 0.97, "ner acme@0123456 score 0.97", "x")]


def test_08t_28_internal_ner_service_account_only(admin, client_factory, monkeypatch):  # noqa: F811
    from ffcore.api import guardrails as api

    monkeypatch.setattr(api, "local_ner", lambda: FakeNer())
    assert client_factory().post(URL, json=BODY).status_code == 401
    as_member = admin.post(URL, json=BODY)
    assert (as_member.status_code, as_member.json()["error"]["code"]) == (
        403,
        "service_account_required",
    )
    ok = client_factory().post(URL, json=BODY, headers=SERVICE)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert [(f["category"], f["start"], f["end"]) for f in body["findings"]] == [("PERSON", 4, 14)]
    assert "Ayşe" not in ok.text
