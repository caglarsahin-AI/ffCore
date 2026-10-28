"""Shared router pieces: documented error responses and the not-yet-implemented marker."""

from ffcore.api.schemas import ErrorBody
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


def not_implemented() -> ApiError:
    return ApiError(501, "api_error", "not_implemented", "This endpoint is not implemented yet.")
