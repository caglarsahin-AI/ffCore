"""16-1 acceptance: a 1,000-file network folder syncs in full, then one changed file syncs
incrementally in under a minute (plan/16 "ikincisi 1 dakikanın altında"). FAKE_EMBED and the
weightless converter keep the measurement about the sync, not the model."""

import time

from tests.integration import sources_support
from tests.integration.sources_support import (
    age_tree,
    create_fs_source,
    document_text,
    documents,
    drain,
    sync,
    write_tree,
)

src_world = sources_support.src_world


def test_16_1_thousand_files_then_one_change_under_a_minute(src_world, pg):
    w = src_world
    write_tree(
        w["root"],
        {f"klasor-{n // 100}/belge-{n:04d}.md": document_text(f"Belge {n}", f"o{n:04d}") for n in range(1000)},
    )
    age_tree(w["root"])
    source = create_fs_source(w)
    sync(w, source["id"], mode="full")
    raw, silver = drain(w)
    assert raw["added"] == 1000 and silver["added"] == 1000 and silver["errors"] == []
    assert len(documents(pg, w["kb"])) == 1000

    (w["root"] / "klasor-4" / "belge-0421.md").write_text(
        document_text("Belge 421", "degisti0421"), encoding="utf-8"
    )
    started = time.monotonic()
    sync(w, source["id"], mode="delta")
    raw, silver = drain(w)
    elapsed = time.monotonic() - started
    assert (raw["listed"], raw["updated"], silver["updated"]) == (1, 1, 1)
    assert elapsed < 60, f"incremental sync took {elapsed:.1f} s"
    print(f"16-1 scale: incremental sync of 1 changed file in 1,000: {elapsed:.2f} s")
