"""04b-2 slice 2, D6: the internal key search (06b S2) takes the same filters as the search API;
before, the unknown field was ignored and a scope would have been dropped silently."""

from tests.integration import test_06b_key_search as key_search
from tests.integration.test_04a_api import PROSE, create_kb, process_all, upload
from tests.integration.test_04b_2_scope_search import SOURCES, _names, _set_sources

# 04a's fixtures (pgvector), as test_06b_key_search uses them.
world = key_search.world
settings = key_search.settings
queue = key_search.queue


def test_04b_2_89_key_search_honours_filters(world, settings, queue, pg):
    kb = create_kb(world)
    for name in SOURCES:
        upload(world, world["admin"], kb["id"], name, PROSE * 8 + " " + name)
    _set_sources(pg, kb["id"])
    process_all(settings, queue)
    key = key_search._key(world)
    scoped = key_search._search(
        world, kb["id"], key["id"], filters={"metadata": {"source": ["jira:PAY"]}}
    )
    assert _names(scoped) == {"pay.md"}
