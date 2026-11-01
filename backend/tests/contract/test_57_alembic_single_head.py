"""FOLLOWUP-57/132: the migration graph has exactly one head (PLAN 5, R2.6).

Packages write their revisions under their own branch label; a merge revision joins the branch
heads so that `alembic heads` prints one line and `alembic upgrade head` (singular) works. A new
package revision starts from that single head (see docs/gelistirme-ortami.md). No database needed.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]

# Every package branch head on main when the merge was written; the merge must reach all of them.
BRANCH_HEADS = {
    "03a_0001",
    "03b_0001",
    "03c_0002",
    "04a_0001",
    "05a_0001",
    "06a_0002",
    "07_0001",
    "08_0001",
}


def _script() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_57_1_single_head():
    heads = _script().get_heads()
    assert len(heads) == 1, f"alembic has {len(heads)} heads, expected one: {sorted(heads)}"


def test_57_1_head_reaches_every_package_branch():
    script = _script()
    (head,) = script.get_heads()
    ancestors = {rev.revision for rev in script.iterate_revisions(head, "base")}
    assert BRANCH_HEADS <= ancestors, f"not merged: {sorted(BRANCH_HEADS - ancestors)}"


def test_57_1_merge_revisions_are_empty():
    # The two merge steps only join heads; schema changes stay in package revisions.
    script = _script()
    step1, step2 = script.get_revision("57_0001"), script.get_revision("57_0002")
    assert step1.is_merge_point and step2.is_merge_point
    parents = set(step1._all_down_revisions) | set(step2._all_down_revisions)
    assert parents == BRANCH_HEADS | {"57_0001"}
    for rev in (step1, step2):
        source = Path(rev.path).read_text(encoding="utf-8")
        assert "op." not in source, f"{rev.revision} must not change the schema"
