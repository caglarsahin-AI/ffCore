"""C2: the `api_keys.scopes` enum (first defined in 03c). Values may only be added; a removal or a
rename fails here. Code, migration CHECK and the API schema list the same values.
"""

import importlib.util
from pathlib import Path

from ffcore.api.keys_schemas import ApiKeyAclRole, ApiKeyScope
from ffcore.models import ApiKey
from ffcore.models.keys import API_KEY_ACL_ROLES, API_KEY_SCOPES

FROZEN_SCOPES = {"chat_direct", "agents", "impersonate", "kb_search", "tools_invoke"}
MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "03c_0001_keys_quota_usage.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("m03c", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check(name: str) -> str:
    for constraint in ApiKey.__table__.constraints:
        if getattr(constraint, "name", None) in (name, f"ck_api_keys_{name}"):
            return str(constraint.sqltext)
    raise AssertionError(f"no check constraint {name} on api_keys")


def test_c2_api_key_scopes_frozen():
    assert set(API_KEY_SCOPES) == FROZEN_SCOPES
    assert {s.value for s in ApiKeyScope} == FROZEN_SCOPES
    assert set(_migration().API_KEY_SCOPES) == FROZEN_SCOPES
    for scope in FROZEN_SCOPES:
        assert f"'{scope}'" in _check("scopes")


def test_c2_api_key_acl_roles_exclude_user():
    assert (
        set(API_KEY_ACL_ROLES)
        == {r.value for r in ApiKeyAclRole}
        == {
            "analyst",
            "developer",
            "admin",
        }
    )
    assert set(_migration().API_KEY_ACL_ROLES) == set(API_KEY_ACL_ROLES)
