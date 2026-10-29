"""Tool registry rules (05a): upstream identity, its encryption and masking, endpoint checks.

The endpoint is user input: it passes the egress policy at registration (C5) and again at
call time (the pinned transport). forward_user goes only to internal FFCore services (C3).
"""

from typing import Any

import httpx2

from ffcore.core.config import Settings
from ffcore.core.egress import EgressDenied, EgressPolicy
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json

MASK = "***"
# Fields of each auth type that never leave the backend (the header name is not secret).
SECRET_FIELDS = {
    "none": (),
    "bearer": ("token",),
    "header": ("value",),
    "basic": ("username", "password"),
    "forward_user": (),
}


def _bad_request(code: str, message: str) -> ApiError:
    return ApiError(400, "invalid_request_error", code, message)


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", code, message)


def check_endpoint(url: str, auth_type: str, settings: Settings) -> None:
    """Registration-time checks: egress policy for the URL (same codes as at call time) and the
    forward_user internal-host rule."""
    target = httpx2.URL(url)
    policy = EgressPolicy(settings)
    try:
        policy.check_url(target)
    except EgressDenied as exc:
        raise _bad_request(exc.code, f"Refused by the outbound policy ({exc.code}).") from None
    if auth_type == "forward_user" and not policy.is_internal(target.host):
        raise _bad_request(
            "forward_user_not_internal",
            "forward_user is allowed only for internal services (ALLOWED_INTERNAL_HOSTS).",
        )


def auth_fields(auth: dict[str, Any]) -> dict[str, str]:
    """The stored part of an auth body: everything but its type."""
    return {k: v for k, v in auth.items() if k != "type"}


def new_auth(auth: dict[str, Any]) -> dict[str, str]:
    fields = auth_fields(auth)
    for name in SECRET_FIELDS[auth["type"]]:
        if fields.get(name) == MASK:
            raise _invalid("invalid_auth_config", f"Auth field {name} is masked; send the value.")
    return fields


def merged_auth(auth: dict[str, Any], stored_type: str, stored: dict[str, str]) -> dict[str, str]:
    """A secret field sent back as *** keeps its stored value, only for the same auth type."""
    fields = auth_fields(auth)
    for name in SECRET_FIELDS[auth["type"]]:
        if fields.get(name) == MASK:
            if auth["type"] != stored_type or name not in stored:
                raise _invalid(
                    "invalid_auth_config", f"Auth field {name} is masked; send the value."
                )
            fields[name] = stored[name]
    return fields


def masked_auth(auth_type: str, fields: dict[str, str]) -> dict[str, str]:
    secret = SECRET_FIELDS[auth_type]
    return {"type": auth_type, **{k: MASK if k in secret else v for k, v in fields.items()}}


def encrypt_auth(fields: dict[str, str], settings: Settings) -> bytes:
    return encrypt_json(fields, settings)


def decrypt_auth(token: bytes, settings: Settings) -> dict[str, str]:
    return decrypt_json(token, settings)
