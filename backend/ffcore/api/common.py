"""Shared router pieces: documented error responses, dependencies and error helpers."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.schemas import ErrorBody
from ffcore.core import db
from ffcore.core.errors import ApiError

ERROR_RESPONSES = {
    status: {"model": ErrorBody, "description": description}
    for status, description in {
        400: "Invalid request.",
        401: "Not authenticated.",
        403: "Role or access mode not sufficient, or cross-origin request.",
        404: "Not found.",
        409: "Conflict with the current state.",
        422: "Request body or parameters failed validation.",
    }.items()
}

SessionDep = Annotated[AsyncSession, Depends(db.get_session)]


def not_implemented() -> ApiError:
    return ApiError(501, "api_error", "not_implemented", "This endpoint is not implemented yet.")


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found_error", f"{what}_not_found", f"{what.capitalize()} not found.")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, "conflict_error", code, message)


def invalid(code: str, message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", code, message)


def path_resource(name: str) -> Callable[[Request], str]:
    """`resource_id` for @audited on routes whose response has no id (deletes, members).

    A dependency, not a parameter: the OpenAPI contract keeps its path parameter names.
    """

    def resource_id(request: Request) -> str:
        return str(request.path_params[name])

    return resource_id
