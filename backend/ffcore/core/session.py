"""Console session: a signed cookie, its credential resolver and the cross-origin rule (C6).

The cookie carries an HS256 token (`SECRET_KEY`) with the user id and the user's
`token_version`; logout and password change bump the version, which revokes every older token.
Token signing and verification live in core/auth.py (C2: every token is verified there);
this module holds the cookie, the cross-origin rule and the resolver registered in main.py.
"""

import uuid

from fastapi import Request, Response
from sqlalchemy import select

from ffcore.core import db
from ffcore.core.auth import Actor, issue_session_token, verify_session_token
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError

COOKIE_NAME = "ffcore_session"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

issue_token = issue_session_token


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_s,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def check_same_origin(request: Request, settings: Settings) -> None:
    """C6: a cookie-authenticated mutation must come from the console's own origin.

    SameSite=Strict already keeps the cookie off cross-site requests; this makes the rule
    explicit and testable, and also covers same-site (sibling subdomain) requests.
    """
    if request.method not in UNSAFE_METHODS:
        return
    fetch_site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    foreign_origin = origin is not None and origin.lower().rstrip("/") not in set(
        settings.console_origins
    )
    if fetch_site in ("cross-site", "same-site") or foreign_origin:
        raise ApiError(
            403,
            "permission_error",
            "cross_origin_forbidden",
            "Cookie-authenticated changes must come from the console origin.",
        )


async def session_resolver(request: Request, settings: Settings) -> Actor | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    claims = verify_session_token(token, settings)
    if claims is None:
        return None

    from ffcore.models.identity import User

    try:
        user_id = uuid.UUID(claims.user_id)
    except ValueError:
        return None
    async with db.session_scope() as session:
        user = await session.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    if user is None or not user.is_active or user.token_version != claims.token_version:
        return None
    check_same_origin(request, settings)
    return Actor(actor_type="user", actor_id=str(user.id))
