"""14 fixtures (star-imported like runs_fixtures, so pytest sees them in the test module)."""

import pytest

from ffcore.memory import pii
from tests.integration.memory_support import NER, SetNer

__all__ = ["memory_settings", "set_ner"]


@pytest.fixture
def set_ner(monkeypatch):
    ner = SetNer()
    monkeypatch.setattr(pii, "ner_client", lambda: ner)
    return ner


@pytest.fixture
def memory_settings(app, app_settings, settings):
    """The run fixtures' settings with fake embeddings and an NER model configured."""
    from ffcore.core.config import get_settings

    s = settings.model_copy(update={"fake_embed": True, **NER})
    app.dependency_overrides[get_settings] = lambda: s
    return s
