"""Scratch: int8 dynamic quantization, quality + latency, akdeniz27 'first' (not committed)."""
import json, os, statistics, time
import torch
from transformers import pipeline
from ffcore.knowledge.models import hf_path
from ffcore.guardrails.recognizers.ner import NerRecognizer, STRIDE

model, rev = "akdeniz27/bert-base-turkish-cased-ner", "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571"
CATS = ("PERSON", "ORGANIZATION", "LOCATION")
recs = [json.loads(l) for l in open("/work/data/samples/pii/pii-100.jsonl", encoding="utf-8")]
text = (" ".join(x["text"] for x in recs))[:1000]
path = str(hf_path(model, rev))
print("loadavg", open("/proc/loadavg").read().strip(), "threads", torch.get_num_threads(), "engine", torch.backends.quantized.engine)
def p(ts): return f"P95 {statistics.quantiles(ts, n=100)[94]:.0f} median {statistics.median(ts):.0f} min {min(ts):.0f} ms"
for quant in (False, True):
    pipe = pipeline("token-classification", model=path, tokenizer=path, aggregation_strategy="first", stride=STRIDE, device=-1)
    if quant:
        pipe.model = torch.quantization.quantize_dynamic(pipe.model, {torch.nn.Linear}, dtype=torch.qint8)
    r = NerRecognizer(model, rev, pipeline=pipe, labels=pipe.model.config.id2label)
    stats = {c: [0, 0, 0] for c in CATS}
    for rec in recs:
        gold = [e for e in rec["entities"] if e["category"] in CATS]
        for e in gold: stats[e["category"]][0] += 1
        used = set()
        for f in r.recognize(rec["text"], CATS):
            stats[f.category][1] += 1
            for i, e in enumerate(gold):
                if i not in used and e["category"] == f.category and f.start < e["end"] and e["start"] < f.end:
                    used.add(i); stats[f.category][2] += 1; break
        for i, e in enumerate(gold):
            if i not in used: print(f"  FN {rec['id']} {e['category']} {rec['text'][e['start']:e['end']]!r}")
    print(f"== int8={quant}", {c: f"r {t/s:.2f} p {t/q if q else 0:.2f} ({q})" for c, (s, q, t) in stats.items()})
    r.recognize(text, CATS)
    ts = []
    for _ in range(60):
        a = time.perf_counter(); r.recognize(text, CATS); ts.append((time.perf_counter() - a) * 1000)
    print("   latency 1000 chars", p(ts))
