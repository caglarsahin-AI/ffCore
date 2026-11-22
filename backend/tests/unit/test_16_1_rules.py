"""16-1: the pure rules of the sync engine. Safe delete (D4, R10.3, C20), Kapı 0 for source
attachments (D1), permission mapping (C15), schedules (K-16-0002 S2) and network-folder paths
(C5). No database; the engine's use of them is tests/integration/test_16_1_sync.py."""

from datetime import UTC, date, datetime

import pytest

from ffcore.sources import acl, gate0, paths, prune, schedule
from ffcore.sources.base import SourceError

# --- safe delete -------------------------------------------------------------------------


def full(**kw):
    base = dict(
        mode="full",
        tombstones=False,
        listing_ok=True,
        count_before=27,
        count_after=27,
        seen=27,
        to_delete=3,
        max_ratio=0.2,
        force=False,
    )
    return prune.decide(prune.PruneInput(**{**base, **kw}))


def test_16_1_prune_three_of_thirty_is_done():
    decision = full()
    assert decision.decision == "done" and decision.allowed
    assert decision.ratio == pytest.approx(3 / 27)


def test_16_1_prune_ratio_over_limit_is_refused_and_only_force_passes():
    # The service account lost a space: the source now counts 10, 20 known items are gone.
    refused = full(count_before=10, count_after=10, seen=10, to_delete=20)
    assert refused.decision == "prune_refused" and not refused.allowed
    forced = full(count_before=10, count_after=10, seen=10, to_delete=20, force=True)
    assert forced.decision == "forced" and forced.allowed


def test_16_1_prune_ratio_denominator_is_the_source_total():
    # C20: the share is over what the source holds (count after listing), not the batch.
    assert full(count_before=100, count_after=100, seen=100, to_delete=20).decision == "done"
    assert full(count_before=99, count_after=99, seen=99, to_delete=20).decision == "prune_refused"


@pytest.mark.parametrize(
    "counts",
    [
        dict(count_before=27, count_after=26),  # the source changed while listing
        dict(count_before=None, count_after=27),  # no count before
        dict(count_before=27, count_after=None),  # no count after
        dict(seen=20),  # the listing saw fewer than the source counts (cut in the middle)
    ],
)
def test_16_1_prune_count_mismatch_deletes_nothing_even_forced(counts):
    assert full(**counts).decision == "count_mismatch"
    assert full(**counts, force=True).decision == "count_mismatch"


def test_16_1_prune_broken_listing_deletes_nothing():
    assert full(listing_ok=False, force=True).decision == "listing_failed"


def test_16_1_prune_delta_without_tombstones_never_deletes():
    assert full(mode="delta", to_delete=0).decision == "none"
    with pytest.raises(ValueError):
        full(mode="delta", to_delete=3)


def test_16_1_prune_tombstone_delta_uses_the_same_rules():
    # SharePoint: 30 of 100 removed at once (> 0.2 of the 70 left) is refused (R10.3, C20).
    big = full(mode="delta", tombstones=True, count_before=70, count_after=70, seen=0, to_delete=30)
    assert big.decision == "prune_refused"
    small = full(mode="delta", tombstones=True, count_before=97, count_after=97, seen=5, to_delete=3)
    assert small.decision == "done"
    moving = full(mode="delta", tombstones=True, count_before=97, count_after=96, to_delete=3)
    assert moving.decision == "count_mismatch"


def test_16_1_prune_empty_source_is_refused_unless_forced():
    assert full(count_before=0, count_after=0, seen=0, to_delete=5).decision == "prune_refused"
    assert full(count_before=0, count_after=0, seen=0, to_delete=5, force=True).allowed


def test_16_1_prune_nothing_to_delete():
    assert full(to_delete=0, count_after=None).decision == "none"


# --- Kapı 0 for attachments ----------------------------------------------------------------

MB = 1024 * 1024
WHEN = datetime(2024, 5, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("name", "size", "reason"),
    [
        ("kurulum.exe", 10, "binary"),
        ("ekran.png", 10, "out_of_scope"),
        ("rapor.xlsx", 10, "out_of_scope"),
        ("yedek.zip", 10, "out_of_scope"),
        ("buyuk.pdf", 500 * MB + 1, "too_large"),
        ("uygulama.log", 5 * MB + 1, "too_large"),
        ("", 10, "name_invalid"),
    ],
)
def test_16_1_gate0_skips_before_download(name, size, reason):
    assert gate0.decide(name, size, WHEN, min_date=None) == ("skipped", reason)


def test_16_1_gate0_limits_pass_at_the_edge():
    assert gate0.decide("buyuk.pdf", 500 * MB, WHEN, min_date=None) == ("ok", None)
    assert gate0.decide("uygulama.log", 5 * MB, WHEN, min_date=None) == ("ok", None)


def test_16_1_gate0_source_date_rule():
    rule = date(2021, 1, 1)
    assert gate0.decide("eski.pdf", 10, datetime(2020, 12, 31, tzinfo=UTC), min_date=rule) == (
        "skipped",
        "stale",
    )
    assert gate0.decide("yeni.pdf", 10, datetime(2021, 1, 1, tzinfo=UTC), min_date=rule) == (
        "ok",
        None,
    )
    # No date from the source: the rule cannot judge it, the attachment passes.
    assert gate0.decide("tarihsiz.pdf", 10, None, min_date=rule) == ("ok", None)
    # No rule configured: old attachments pass.
    assert gate0.decide("eski.pdf", 10, datetime(2010, 1, 1, tzinfo=UTC), min_date=None)[0] == "ok"


def test_16_1_gate0_unknown_size_is_bounded_while_streaming():
    assert gate0.decide("belge.pdf", None, WHEN, min_date=None) == ("ok", None)
    assert gate0.max_bytes("belge.pdf") == 500 * MB
    assert gate0.max_bytes("kayit.log") == 5 * MB


# --- permission mapping ---------------------------------------------------------------------

ANALYST_USER = "11111111-1111-1111-1111-111111111111"


def rules(*rows):
    return [acl.AclRule(*row) for row in rows]


def test_16_1_acl_unmapped_group_is_admin_only():
    resolved = acl.resolve(["Yonetim"], [], [], {})
    assert resolved.roles == ("admin",) and resolved.users == ()
    assert resolved.default_admin and resolved.unmapped_groups == ("Yonetim",)


def test_16_1_acl_item_without_groups_is_admin_only():
    assert acl.resolve([], [], [], {}).roles == ("admin",)


def test_16_1_acl_mapped_group_and_every_item_row():
    mapped = acl.resolve(["Yonetim", "Destek"], [], rules(("Destek", "analyst")), {})
    assert mapped.roles == ("analyst",) and not mapped.default_admin
    assert mapped.unmapped_groups == ("Yonetim",)
    every = acl.resolve(["Herhangi"], [], rules(("*", "analyst")), {})
    assert every.roles == ("analyst",)


def test_16_1_acl_union_for_source_groups():
    resolved = acl.resolve(
        ["Yonetim", "Destek"], [], rules(("Yonetim", "admin"), ("Destek", "analyst")), {}
    )
    assert set(resolved.roles) == {"admin", "analyst"}


def test_16_1_acl_user_mapping_and_email_match():
    resolved = acl.resolve(
        ["Ekip"],
        ["Ayse.Kaya@Example.Test", "bilinmeyen@example.test"],
        rules(("Ekip", None, "22222222-2222-2222-2222-222222222222")),
        {"ayse.kaya@example.test": ANALYST_USER},
    )
    assert set(resolved.users) == {"22222222-2222-2222-2222-222222222222", ANALYST_USER}
    assert resolved.roles == () and resolved.unmatched_emails == 1


def test_16_1_acl_folders_most_specific_mapping_wins():
    groups = acl.folder_groups("sozlesmeler/yonetim/2024/kurul.md")
    assert groups == (
        "folder:/",
        "folder:/sozlesmeler",
        "folder:/sozlesmeler/yonetim",
        "folder:/sozlesmeler/yonetim/2024",
    )
    mappings = rules(("folder:/", "analyst"), ("folder:/sozlesmeler/yonetim", "admin"))
    narrowed = acl.resolve(groups, [], mappings, {}, most_specific=True)
    assert narrowed.roles == ("admin",)
    open_doc = acl.resolve(acl.folder_groups("genel/el-kitabi.md"), [], mappings, {}, most_specific=True)
    assert open_doc.roles == ("analyst",)
    # The same rows as a union would open the management folder to analysts: never for folders.
    assert "analyst" in acl.resolve(groups, [], mappings, {}).roles


# --- schedules ---------------------------------------------------------------------------


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def test_16_1_schedule_validation():
    assert schedule.Schedule().kind == "manual"
    schedule.Schedule(kind="daily", at="02:30")
    schedule.Schedule(kind="weekly", weekday=6, at="23:00")
    schedule.Schedule(kind="hourly", minute=15)
    for bad in (
        {"kind": "cron", "at": "0 2 * * *"},
        {"kind": "daily"},
        {"kind": "daily", "at": "25:00"},
        {"kind": "daily", "at": "2:3"},
        {"kind": "hourly", "minute": 15, "at": "02:00"},
        {"kind": "manual", "at": "02:00"},
        {"kind": "weekly", "at": "02:00"},
    ):
        with pytest.raises(ValueError, match="schedule_invalid|validation"):
            schedule.Schedule.model_validate(bad)


def test_16_1_schedule_due():
    daily = schedule.Schedule(kind="daily", at="02:00")
    assert schedule.due(daily, at(21, 1), at(22, 2, 0))  # slot passed after the last run
    assert not schedule.due(daily, at(22, 2, 1), at(22, 3))  # already ran after the slot
    assert schedule.due(daily, at(19, 2), at(22, 9))  # missed slots: due once
    assert not schedule.due(daily, None, at(22, 9))  # never synced: the first run is manual
    assert not schedule.due(schedule.Schedule(), at(1, 1), at(22, 9))
    hourly = schedule.Schedule(kind="hourly", minute=30)
    assert schedule.due(hourly, at(22, 8, 31), at(22, 9, 30))
    assert not schedule.due(hourly, at(22, 9, 31), at(22, 10, 0))
    weekly = schedule.Schedule(kind="weekly", weekday=6, at="03:00")  # Sunday
    assert schedule.last_slot(weekly, at(25, 12)) == at(22, 3)  # 22 Nov 2026 is a Sunday
    assert schedule.due(weekly, at(21, 3), at(22, 3, 5))


# --- network-folder paths ---------------------------------------------------------------


@pytest.mark.parametrize("root", ["/", "/etc", "../..", "a/../../b", "~/x", "a\\b"])
def test_16_1_root_outside_base_is_refused(root):
    with pytest.raises(SourceError) as error:
        paths.check_root(root)
    assert error.value.code == "path_outside_base"


def test_16_1_root_inside_base(tmp_path):
    (tmp_path / "paylasim" / "sozlesmeler").mkdir(parents=True)
    assert paths.check_root("") == "." and paths.check_root("./paylasim") == "paylasim"
    assert paths.resolve_root(str(tmp_path), "paylasim/sozlesmeler").name == "sozlesmeler"
    with pytest.raises(SourceError) as missing:
        paths.resolve_root(str(tmp_path), "yok")
    assert missing.value.code == "fs_root_missing"


def test_16_1_root_through_a_symlink_is_refused(tmp_path):
    base, outside = tmp_path / "base", tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (base / "kacis").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SourceError) as error:
        paths.resolve_root(str(base), "kacis")
    assert error.value.code == "path_outside_base"


def test_16_1_raw_item_dir_cannot_escape(tmp_path):
    item = paths.raw_item_dir(str(tmp_path), "p", "k", "fs", "default", "../../etc/passwd")
    assert tmp_path in item.parents and ".." not in item.parts
    a = paths.raw_item_dir(str(tmp_path), "p", "k", "fs", "default", "a/b.md")
    b = paths.raw_item_dir(str(tmp_path), "p", "k", "fs", "default", "a__b.md")
    assert a != b  # the hash keeps two ids apart even when their readable parts meet


def test_16_1_safe_name():
    assert paths.safe_name("Rapor: 2024/Q1?.pdf") == "Rapor_ 2024_Q1_.pdf"
    long = paths.safe_name("a" * 300 + ".docx")
    assert len(long) == paths.SAFE_NAME_MAX and long.endswith(".docx")
    with pytest.raises(SourceError):
        paths.safe_name("...")
