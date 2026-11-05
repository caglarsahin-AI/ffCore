"""08 tam 1b r1 MINOR-2: a transport failure of the internal NER (connection refused, DNS,
timeout) is `NerUnavailable`, so `ingest-raw` with a PRSIM source refuses with its code and
exit 2 instead of a traceback; the engine treats it like any NER outage."""

import asyncio

import pytest

from ffcore import cli
from ffcore.core import egress
from ffcore.guardrails.recognizers import ner
from ffcore.knowledge import ingest_mask


def _settings():
    from ffcore.core.config import get_settings

    return get_settings().model_copy(
        update={
            "internal_api_url": "http://backend:8000",
            "ner_model": "acme/turkish-ner",
            "ner_revision": "0123456789abcdef",
        }
    )


def _refusing(error):
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, *args, **kwargs):
            raise error

    return Client


ERRORS = [
    egress.EgressRequestFailed("request_failed", "http://backend:8000", "connection refused"),
    egress.EgressTimeoutError("timeout", "http://backend:8000", "read"),
]


@pytest.mark.parametrize("error", ERRORS)
def test_08t_24_transport_error_is_ner_unavailable(monkeypatch, error):
    monkeypatch.setattr(egress, "SafeOutboundClient", _refusing(error))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    with pytest.raises(ner.NerUnavailable):
        asyncio.run(ner.HttpNer(_settings()).find("Bay Ayşe Demir", ["PERSON"]))


def test_08t_24b_cli_prsim_exits_2_with_code(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(egress, "SafeOutboundClient", _refusing(ERRORS[0]))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: ner.HttpNer(_settings()))
    raw = tmp_path / "raw"
    raw.mkdir()
    code = cli.main(
        [
            "ingest-raw",
            "--project",
            "p",
            "--kb",
            "k",
            "--raw-dir",
            str(raw),
            "--acl",
            "analyst",
            "--sources",
            "jira:PRSIM",
        ]
    )
    assert code == 2
    assert "prsim_requires_ner" in capsys.readouterr().err
