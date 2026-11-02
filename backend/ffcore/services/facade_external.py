"""06b external agent (`agents.kind = external`).

The facade's contract for it is frozen with C11 (kind and event subset); the call path itself
comes with 06b-2 (K-06b A-06b-0008). Until then a request for an external agent fails loud."""

from ffcore.core.errors import ApiError


def not_this_path() -> ApiError:
    return ApiError(
        501,
        "api_error",
        "external_agent_not_available",
        "External agents cannot be called through the facade yet.",
    )
