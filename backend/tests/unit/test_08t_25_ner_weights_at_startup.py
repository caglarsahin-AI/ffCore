"""08 tam 1b r1 MINOR-3 (KARARLAR "Egress kişi adı (NER)": weights missing fails at start-up,
not per call): with egress on and GUARDRAIL_EGRESS_NER=true the API checks that the NER weights
are in the offline cache (`hf_path`, presence only, nothing loaded) and stops when they are not.
The agent worker holds no model cache (it asks the API), so the check is the API's."""

import inspect
from pathlib import Path

import pytest

from ffcore import main
from ffcore.guardrails import settings as guard_settings
from ffcore.guardrails.settings import GuardrailSettings
from ffcore.knowledge import models


class _Core:
    ner_model, ner_revision = "acme/turkish-ner", "0123456789abcdef"


def test_08t_25_missing_weights_stop_the_api(monkeypatch):
    seen = []

    def missing(repo, revision="main"):
        seen.append((repo, revision))
        raise models.ModelMissing(repo, Path("/models/hf"))

    monkeypatch.setattr(models, "hf_path", missing)
    on = GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=True)
    with pytest.raises(RuntimeError) as raised:
        guard_settings.check_ner_weights(on, _Core())
    assert "model_missing" in str(raised.value)
    assert seen == [("acme/turkish-ner", "0123456789abcdef")]


def test_08t_25b_present_weights_or_ner_off_pass(monkeypatch):
    calls = []
    monkeypatch.setattr(models, "hf_path", lambda repo, revision="main": calls.append(repo))
    on = GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=True)
    guard_settings.check_ner_weights(on, _Core())
    assert calls == ["acme/turkish-ner"]
    for egress, flag in ((False, True), (True, False)):
        guard_settings.check_ner_weights(
            GuardrailSettings(guardrail_egress_enabled=egress, guardrail_egress_ner=flag), _Core()
        )
    assert calls == ["acme/turkish-ner"]


def test_08t_25c_api_lifespan_runs_the_check():
    assert "check_ner_weights(" in inspect.getsource(main.lifespan)
