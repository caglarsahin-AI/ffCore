"""Login, logout, current user and own password (03a)."""

from fastapi import APIRouter

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import LoginRequest, MeResponse, PasswordChangeRequest

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=MeResponse, summary="Sign in with email and password")
async def login(body: LoginRequest):
    """Sets the `ffcore_session` cookie (HttpOnly, SameSite=Strict, Secure). A wrong email or
    password gives the same 401 `invalid_credentials`."""
    raise not_implemented()


@router.post("/logout", status_code=204, summary="Sign out")
async def logout() -> None:
    """Clears the cookie and revokes every session token of the user."""
    raise not_implemented()


@router.get("/me", response_model=MeResponse, summary="Current user, role and access mode")
async def me():
    raise not_implemented()


@router.post("/password", status_code=204, summary="Change own password")
async def change_password(body: PasswordChangeRequest) -> None:
    """Allowed in read-only access mode (own data). Revokes other sessions."""
    raise not_implemented()
