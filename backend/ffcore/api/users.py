"""Users (superadmin only)."""

from uuid import UUID

from fastapi import APIRouter

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import UserCreate, UserList, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], responses=ERROR_RESPONSES)


@router.get("", response_model=UserList, summary="List users")
async def list_users():
    raise not_implemented()


@router.post("", response_model=UserOut, status_code=201, summary="Create a user")
async def create_user(body: UserCreate):
    raise not_implemented()


@router.get("/{user_id}", response_model=UserOut, summary="Get a user")
async def get_user(user_id: UUID):
    raise not_implemented()


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user")
async def update_user(user_id: UUID, body: UserUpdate):
    raise not_implemented()


@router.delete("/{user_id}", status_code=204, summary="Delete a user (soft delete)")
async def delete_user(user_id: UUID) -> None:
    raise not_implemented()
