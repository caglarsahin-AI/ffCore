"""Reviewer probe for 08-tam-1b r2 (4567ed6; r1 probe with every case caught, plus r2 additions), backend container: built-in v3 egress with a fake NER
client, NER outage under the built-in and under a stored `on_error: allow` policy, text stages
never calling NER, NER spans touching existing placeholders, and the reveal of a NER-tokenized name.

docker exec -w /app -e PYTHONPATH=/app review08t1b-backend-1 python /tmp/probe08t1b.py
"""

import asyncio

from ffcore.guardrails import builtin, engine
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import MemoryTokenStore, reveal_text
from ffcore.guardrails.recognizers.ner import NerUnavailable
from ffcore.guardrails.schemas import PiiPolicySpec, PolicySpec, ResolvedPolicy

TEXT = "Müşteri Ayşe Demir, TC 10000000146, tel 0532 123 45 67, ayse@ornek.com"
NAMES = ("Ayşe Demir", "Mehmet Kaya")


class Fake:
    model = "acme/ner"

    def __init__(self, error=None, spans=None):
        self.error, self.spans, self.calls = error, spans, 0

    async def find(self, text, categories):
        self.calls += 1
        if self.error:
            raise self.error
        if self.spans is not None:
            return [Finding("PERSON", s, e, 0.97, "ner", text[s:e]) for s, e in self.spans(text)]
        out = []
        for n in NAMES:
            at = text.find(n)
            if at != -1:
                out.append(Finding("PERSON", at, at + len(n), 0.97, "ner", n))
        return out


async def ev_raw(text, stage, policy, ner, store=None):
    ctx = engine.EvalContext(
        source="api", run_id="probe", token_store=store or MemoryTokenStore(), egress_enabled=True, ner=ner
    )
    return await engine.evaluate(text, stage, policy, ctx=ctx)


class Raised:
    def __init__(self, exc):
        self.action = f"RAISED {type(exc).__name__} code={getattr(exc, 'code', '')}"
        self.text_out = ""
        self.events = []


async def ev(text, stage, policy, ner, store=None):
    try:
        return await ev_raw(text, stage, policy, ner, store)
    except Exception as exc:  # noqa: BLE001 - the probe reports what happens
        return Raised(exc)


def leaks(out):
    return [v for v in ("Ayşe Demir", "10000000146", "0532 123 45 67", "ayse@ornek.com") if v in out]


def stored(on_error, mode="enforce", stage="egress"):
    pii = PiiPolicySpec.model_validate(
        {
            "engine": "ner",
            "default_action": "tokenize",
            "categories": {
                c: {"enabled": True}
                for c in ("PERSON", "TR_NATIONAL_ID", "TR_PHONE", "EMAIL_ADDRESS")
            },
        }
    )
    spec = PolicySpec.model_validate(
        {"mode": mode, "on_error": on_error, "rules": [{"type": "pii", "pii_policy_key": "p", "stages": [stage]}]}
    )
    return ResolvedPolicy(key="g", spec=spec, pii_policies={"p": pii})


async def main():
    v3 = builtin.builtin_default(True)
    v2 = builtin.builtin_default(False)
    d = await ev(TEXT, "egress", v3, Fake())
    print(f"E1 v3 egress NER on: action={d.action} leaks={leaks(d.text_out)} out={d.text_out!r}")
    f = Fake()
    d = await ev(TEXT, "egress", v2, f)
    print(f"E1 v3 egress NER off: leaks={leaks(d.text_out)} ner_calls={f.calls}")
    d = await ev(TEXT, "egress", v3, Fake(error=NerUnavailable("503")))
    print(f"E2 built-in, NER down: action={d.action} out={d.text_out!r} events={[e.error for e in d.events]}")
    for st in ("input.pre", "output.pre", "tool.pre", "tool.post"):
        f = Fake(error=AssertionError("NER called"))
        try:
            d = await ev(TEXT, st, v3, f)
            print(f"E3 text stage {st}: ner_calls={f.calls} action={d.action}")
        except Exception as exc:  # noqa: BLE001
            print(f"E3 text stage {st}: {type(exc).__name__} {exc}")
    for on_error in ("block", "allow"):
        d = await ev(TEXT, "egress", stored(on_error), Fake(error=NerUnavailable("503")))
        print(f"E4 stored on_error={on_error}, NER down: action={d.action} leaks={leaks(d.text_out)}")
    d = await ev(TEXT, "egress", stored("block", mode="monitor"), Fake(error=NerUnavailable("503")))
    print(f"E5 stored monitor, NER down: action={d.action} leaks={leaks(d.text_out)}")
    # E6: a NER span over an existing placeholder (history already tokenized)
    store = MemoryTokenStore()
    first = await ev("Ayşe Demir geldi", "egress", v3, Fake(), store)
    hist = first.text_out
    print(f"E6 first turn: {hist!r}")
    span_over = lambda t: [(max(0, t.find("<<PII_") - 4), t.find(">>") + 2 + 6)] if "<<PII_" in t else []  # noqa: E731
    second = await ev(f"Bay {hist[:9]} Hanım aradı", "egress", v3, Fake(spans=span_over), store)
    print(f"E6 NER span covering a placeholder: {second.text_out!r}")
    back, _, _ = await reveal_text(second.text_out, store=store, scope="probe")
    print(f"E6 revealed: {back!r}")
    inner = lambda t: [(t.find("PII_"), t.find("PII_") + 5)] if "PII_" in t else []  # noqa: E731
    third = await ev(f"{hist[:9]} bilgi", "egress", v3, Fake(spans=inner), store)
    print(f"E6 NER span inside a placeholder: {third.text_out!r}")
    # r2 MINOR-5: a name glued to a phone number, NER span overlapping the regex finding
    glued = "Ayşe Kaya05321234567 aradı"
    over = lambda t: [(0, t.find("0532") + 4)]  # noqa: E731
    d = await ev(glued, "egress", v3, Fake(spans=over), MemoryTokenStore())
    print(f"E7 name glued to phone (partial overlap): {d.text_out!r} leaks_name={'Ayşe' in d.text_out or 'Kaya' in d.text_out}")
    # r2 MINOR-1: text stages under on_error=allow still follow on_error (not egress)
    d = await ev(TEXT, "input.pre", stored("allow", stage="input.pre"), Fake(error=NerUnavailable("503")))
    print(f"E8 text stage input.pre on_error=allow NER down: action={d.action}")
    d = await ev(TEXT, "egress", stored("allow", mode="monitor"), Fake(error=NerUnavailable("503")))
    print(f"E9 egress monitor-mode stored on_error=allow NER down: action={d.action}")
    back, _, _ = await reveal_text(third.text_out, store=store, scope="probe")
    print(f"E6 revealed: {back!r}")


asyncio.run(main())
