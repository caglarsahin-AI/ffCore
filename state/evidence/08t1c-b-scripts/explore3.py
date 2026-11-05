"""Scratch: latency breakdown for akdeniz27 'first' (not committed)."""
import json, os, statistics, time
import torch
from transformers import pipeline
from ffcore.knowledge.models import hf_path
from ffcore.guardrails.recognizers.ner import STRIDE

model, rev = "akdeniz27/bert-base-turkish-cased-ner", "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571"
recs = [json.loads(l) for l in open("/work/data/samples/pii/pii-100.jsonl", encoding="utf-8")]
text = (" ".join(x["text"] for x in recs))[:1000]
path = str(hf_path(model, rev))
pipe = pipeline("token-classification", model=path, tokenizer=path, aggregation_strategy="first", stride=STRIDE, device=-1)
print("loadavg", open("/proc/loadavg").read().strip(), "cpus", os.cpu_count())
enc = pipe.tokenizer(text, return_tensors="pt")
print("tokens", enc["input_ids"].shape)
def p(ts): return f"P95 {statistics.quantiles(ts, n=100)[94]:.0f} median {statistics.median(ts):.0f} min {min(ts):.0f} ms"
for threads in (1, 2, 4, os.cpu_count()):
    torch.set_num_threads(threads)
    with torch.inference_mode():
        pipe.model(**enc)
        fw = []
        for _ in range(30):
            a = time.perf_counter(); pipe.model(**enc); fw.append((time.perf_counter() - a) * 1000)
    pl = []
    for _ in range(30):
        a = time.perf_counter(); pipe(text); pl.append((time.perf_counter() - a) * 1000)
    tk = []
    for _ in range(30):
        a = time.perf_counter(); pipe.tokenizer(text, return_offsets_mapping=True); tk.append((time.perf_counter() - a) * 1000)
    print(f"threads {threads}: forward {p(fw)} | pipeline {p(pl)} | tokenizer {p(tk)}")
