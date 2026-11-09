"""NOTE-2b: LocalNer serializes every NER call under one lock. Per-call latency and throughput
with 1, 2 and 4 concurrent callers (asyncio.to_thread, like the API), 1,000 characters."""
import asyncio, os, statistics, threading, time
import torch
from ffcore.guardrails import quality
from ffcore.guardrails.recognizers.ner import LocalNer

client = LocalNer("akdeniz27/bert-base-turkish-cased-ner", "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571")
client.load()
text = quality.latency_text(1000)
CATS = quality.NER_CATEGORIES
print("loadavg", open("/proc/loadavg").read().strip(), "| cpus", os.cpu_count(), "| torch threads", torch.get_num_threads())

async def caller(n, out):
    for _ in range(n):
        t = time.perf_counter(); await client.find(text, CATS); out.append((time.perf_counter() - t) * 1000)

async def run(concurrency, calls=12):
    out = []
    t = time.perf_counter()
    await asyncio.gather(*(caller(calls, out) for _ in range(concurrency)))
    wall = time.perf_counter() - t
    q = statistics.quantiles(out, n=100)
    return f"concurrency {concurrency}: per-call median {statistics.median(out):.0f} ms, P95 {q[94]:.0f} ms, throughput {len(out)/wall:.1f} calls/s"

asyncio.run(client.find(text, CATS))
for c in (1, 2, 4):
    print("lock (as shipped)  ", asyncio.run(run(c)))
# Without the call lock (measurement only; the HF pipeline is not documented thread-safe).
client._lock = type("NoLock", (), {"__enter__": lambda s: None, "__exit__": lambda s, *a: None})()
for c in (2, 4):
    print("no lock (probe)    ", asyncio.run(run(c)))
