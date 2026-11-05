"""Scratch exploration: both NER candidates on pii-100 (not committed)."""

import json
import statistics
import time

from ffcore.guardrails.recognizers.ner import NerRecognizer

CANDS = {
    "savasy/bert-base-turkish-ner-cased": "7678083d645af39967e0ebe8213a6049deb6e2cc",
    "akdeniz27/bert-base-turkish-cased-ner": "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571",
}
CATS = ("PERSON", "ORGANIZATION", "LOCATION")
recs = [json.loads(line) for line in open("/work/data/samples/pii/pii-100.jsonl", encoding="utf-8")]

for model, rev in CANDS.items():
    t0 = time.perf_counter()
    r = NerRecognizer.load(model, rev)
    print(f"== {model} load {time.perf_counter() - t0:.1f}s ignored={r.ignored_labels}")
    stats = {c: [0, 0, 0] for c in CATS}
    for rec in recs:
        gold = [e for e in rec["entities"] if e["category"] in CATS]
        for e in gold:
            stats[e["category"]][0] += 1
        found = r.recognize(rec["text"], CATS)
        used = set()
        for f in found:
            stats[f.category][1] += 1
            hit = False
            for i, e in enumerate(gold):
                if i not in used and e["category"] == f.category and f.start < e["end"] and e["start"] < f.end:
                    used.add(i)
                    stats[f.category][2] += 1
                    hit = True
                    break
            if not hit:
                print(f"  FP {rec['id']} {f.category} {f.value!r} {f.score:.2f}")
        for i, e in enumerate(gold):
            if i not in used:
                print(f"  FN {rec['id']} {e['category']} {rec['text'][e['start']:e['end']]!r}")
    for c, (s, p, t) in stats.items():
        print(f"  {c}: support {s} predicted {p} tp {t} recall {t / s if s else 0:.2f} precision {t / p if p else 0:.2f}")
    text = (" ".join(r_["text"] for r_ in recs))[:1000]
    r.recognize(text, CATS)
    ts = []
    for _ in range(50):
        a = time.perf_counter()
        r.recognize(text, CATS)
        ts.append((time.perf_counter() - a) * 1000)
    print(f"  P95 1000 chars {statistics.quantiles(ts, n=100)[94]:.1f} ms median {statistics.median(ts):.1f}")
