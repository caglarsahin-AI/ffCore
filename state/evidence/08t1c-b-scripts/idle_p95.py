"""Idle P95: fp32 vs int8 ('first'), quality.ner_latency_sample (local rules + NER, 1,000 chars)."""
import os, sys
import torch
from transformers import pipeline
from ffcore.guardrails import quality
from ffcore.guardrails.recognizers.ner import STRIDE, LocalNer, NerRecognizer
from ffcore.knowledge.models import hf_path

if len(sys.argv) > 1:
    torch.set_num_threads(int(sys.argv[1]))
model, rev = "akdeniz27/bert-base-turkish-cased-ner", "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571"
print("loadavg", open("/proc/loadavg").read().strip(), "| cpus", os.cpu_count(), "| torch threads", torch.get_num_threads())
path = str(hf_path(model, rev))
pipe = pipeline("token-classification", model=path, tokenizer=path, aggregation_strategy="first", stride=STRIDE, device=-1)
fp32 = NerRecognizer(model, rev, pipeline=pipe, labels=pipe.model.config.id2label)
int8 = LocalNer(model, rev)
int8.load()
for round_ in (1, 2):
    for name, find in (("fp32", fp32.recognize), ("int8", int8._recognize)):
        p95 = quality.ner_latency_sample(find, chars=1000, runs=200)
        print(f"round {round_} {name}: P95 {p95:.0f} ms (200 runs) | loadavg {open('/proc/loadavg').read().split()[0]}")
