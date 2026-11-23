"""16-1 r2 MAJOR-1 (A): who registers a source of each kind, in one table (`sources/policy.py`).

A network folder is the installation's (one FS_SOURCES_BASE for every project): its source and
its root or filters are the superadmin's. Kinds whose credentials the project brings (Confluence,
Jira, SharePoint: the project's own service account) are the project admin's.
"""

import pytest

from ffcore.models.sources import KINDS
from ffcore.sources import policy


def test_16_1_r2_every_kind_has_a_registration_rule():
    assert set(policy.REGISTRATION) == set(KINDS)
    assert policy.REGISTRATION["fs"] == policy.SUPERADMIN
    for kind in ("confluence", "jira", "sharepoint"):
        assert policy.REGISTRATION[kind] == policy.PROJECT_ADMIN


def test_16_1_r2_config_fields_that_need_the_registrar():
    # Root and filters decide what is read; name, schedule, mode, ratio and status do not.
    assert policy.config_change_needs_registrar({"config": {"root": "."}})
    assert policy.config_change_needs_registrar({"secret": {"token": "***"}})
    for harmless in ({"name": "x"}, {"schedule": {"kind": "manual"}}, {"status": "paused"},
                     {"sync_mode": "full"}, {"prune_max_ratio": 0.3}):  # fmt: skip
        assert not policy.config_change_needs_registrar(harmless)


def test_16_1_r2_unknown_kind_is_refused():
    with pytest.raises(KeyError):
        policy.registrar("gdrive")
