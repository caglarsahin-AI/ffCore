"""08 full 1b acceptance 3 on the target machine: P95 < 300 ms for 1,000 characters, local
rules and NER together (the int8 model the API loads).

Its own marker, not `models` (K-08T1C-0021): the result depends on the machine, and a developer
laptop gave 158-840 ms for the same code (ENV-177, docs/guardrail.md), so `make test-models`
does not run it. Run on the installation's machine, offline, before GUARDRAIL_EGRESS_NER=true:
`make test-ner-latency` (RUN_MODEL_TESTS=1 and RUN_NER_LATENCY=1; prints the P95).
"""

import pytest

from ffcore.guardrails import quality
from ffcore.guardrails.recognizers.ner import LocalNer
from tests.models.test_08t_ner_models import _winner

pytestmark = pytest.mark.ner_latency


def test_08t_3_ner_latency_p95():
    model, revision = _winner()
    client = LocalNer(model, revision)
    client.load()
    p95_ms = quality.ner_latency_sample(client._recognize, chars=1000, runs=100)
    print(f"NER P95, 1000 characters, local rules + NER: {p95_ms:.0f} ms")
    assert p95_ms < 300, p95_ms
