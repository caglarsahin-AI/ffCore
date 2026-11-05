"""Scratch: aggregation strategy x candidate, quality + latency (not committed)."""
import json, os, statistics, sys, time
import torch
from transformers import pipeline
from ffcore.knowledge.models import hf_path
from ffcore.guardrails.recognizers.ner import NerRecognizer, STRIDE

CANDS = {
    "savasy/bert-base-turkish-ner-cased": "7678083d645af39967e0ebe8213a6049deb6e2cc",
    "akdeniz27/bert-base-turkish-cased-ner": "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571",
}
CATS = ("PERSON", "ORGANIZATION", "LOCATION")
recs = [json.loads(l) for l in open("/work/data/samples/pii/pii-100.jsonl", encoding="utf-8")]
print("nproc", os.cpu_count(), "torch threads", torch.get_num_threads(), "loadavg", open("/proc/loadavg").read().strip())
strategies = sys.argv[1].split(",")
verbose = len(sys.argv) > 2
for model, rev in CANDS.items():
    path = str(hf_path(model, rev))
    for strat in strategies:
        pipe = pipeline("token-classification", model=path, tokenizer=path, aggregation_strategy=strat, stride=STRIDE, device=-1)
        r = NerRecognizer(model, rev, pipeline=pipe, labels=pipe.model.config.id2label)
        print(f"== {model} {strat} fast={pipe.tokenizer.is_fast}")
        stats = {c: [0, 0, 0] for c in CATS}
        for rec in recs:
            gold = [e for e in rec["entities"] if e["category"] in CATS]
            for e in gold:
                stats[e["category"]][0] += 1
            used = set()
            for f in r.recognize(rec["text"], CATS):
                stats[f.category][1] += 1
                hit = False
                for i, e in enumerate(gold):
                    if i not in used and e["category"] == f.category and f.start < e["end"] and e["start"] < f.end:
                        used.add(i); stats[f.category][2] += 1; hit = True; break
                if not hit and verbose:
                    print(f"  FP {rec['id']} {f.category} {f.value!r} {f.score:.2f}")
            for i, e in enumerate(gold):
                if i not in used:
                    print(f"  FN {rec['id']} {e['category']} {rec['text'][e['start']:e['end']]!r}")
        for c, (s, p, t) in stats.items():
            print(f"  {c}: support {s} predicted {p} tp {t} recall {t/s:.2f} precision {t/p if p else 0:.2f}")
        text = (" ".join(x["text"] for x in recs))[:1000]
        r.recognize(text, CATS)
        ts = []
        for _ in range(60):
            a = time.perf_counter(); r.recognize(text, CATS); ts.append((time.perf_counter() - a) * 1000)
        print(f"  latency 1000 chars P95 {statistics.quantiles(ts, n=100)[94]:.1f} ms median {statistics.median(ts):.1f} min {min(ts):.1f}")
