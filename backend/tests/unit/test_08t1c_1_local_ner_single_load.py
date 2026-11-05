"""08 tam 1c, FOLLOWUP-168 NOTE-2: the process-wide `local_ner()` registry is built once.

The warm-up thread and the first request can reach `local_ner()` together; without a lock both
saw an empty registry and each built a `LocalNer`, so the model could be loaded twice (memory).
"""

import threading
import time
from types import SimpleNamespace

from ffcore.core import config
from ffcore.guardrails.recognizers import ner


def test_08t1c_1_local_ner_single_load(monkeypatch):
    built = []

    class SlowLocalNer:
        def __init__(self, model, revision):
            built.append((model, revision))
            time.sleep(0.2)  # the window in which a second caller also sees an empty registry

    settings = SimpleNamespace(ner_model="acme/turkish-ner", ner_revision="0123456789abcdef")
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(ner, "LocalNer", SlowLocalNer)
    monkeypatch.setattr(ner, "_local", {})

    start = threading.Barrier(4)
    got = []

    def call():
        start.wait()
        got.append(ner.local_ner())

    threads = [threading.Thread(target=call) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(got) == 4
    assert len(built) == 1, built
    assert all(client is got[0] for client in got)
