"""09-2 r1 probe, part 2 (backend container): what the from-run item holds in Langfuse.
Looks up the dataset items whose input mentions the probe question's marker ('fesih süresi')
and reports whether a raw synthetic value is left. Prints no item text beyond placeholders."""

import asyncio
import json
import re

from ffcore.core.config import get_settings
from ffcore.evaluation.langfuse_api import LangfuseApi

RAW = ("10000000146", "ayse.yilmaz@ornek.com")


async def main():
    api = LangfuseApi(get_settings())
    items = await api.items("hastane-a.rv2-gate")
    hits = [i for i in items if "fesih" in json.dumps(i.get("input"), ensure_ascii=False)]
    print(f"L0 dataset items={len(items)} probe items={len(hits)} ids={[i.get('id') for i in hits]}")
    for i in hits:
        blob = json.dumps({k: i.get(k) for k in ("input", "expectedOutput", "metadata")}, ensure_ascii=False)
        print(f"L1 id={i.get('id')} raw_left={[r for r in RAW if r in blob]} "
              f"placeholders={sorted(set(re.findall(r'<<PII_[0-9]+>>|\[[A-Z_]+\]', blob)))} "
              f"metadata_keys={sorted((i.get('metadata') or {}).keys())}")


asyncio.run(main())
