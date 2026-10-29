"""Request size limit for document uploads, before the multipart body is parsed (r1 MAJOR-5).

FastAPI parses (and spools) the whole multipart body before the route runs, so a route check
comes too late. This ASGI middleware answers 413 `request_too_large` when Content-Length is over
UPLOAD_MAX_REQUEST_BYTES, and also counts the bytes as they arrive (chunked transfer, a wrong
Content-Length): past the limit it stops reading and replaces whatever the app would answer.
"""

import re

from starlette.responses import JSONResponse

from ffcore.core.config import get_settings
from ffcore.core.errors import error_body

UPLOAD_PATH = re.compile(r"^/api/v1/projects/[^/]+/knowledge-bases/[^/]+/documents/?$")


class _TooLarge(Exception):
    pass


def _response(limit: int) -> JSONResponse:
    return JSONResponse(
        error_body(
            "invalid_request_error",
            "request_too_large",
            f"The upload is larger than {limit} bytes; send fewer or smaller files per request.",
        ),
        status_code=413,
    )


class UploadSizeLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not UPLOAD_PATH.match(scope["path"])
        ):
            await self.app(scope, receive, send)
            return
        # The request dependency, so a test override applies here too (as in main.lifespan).
        overrides = scope["app"].dependency_overrides
        limit = overrides.get(get_settings, get_settings)().upload_max_request_bytes
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            await _response(limit)(scope, receive, send)
            return
        received, exceeded = 0, False

        async def limited_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _TooLarge
            return message

        async def guarded_send(message):
            if not exceeded:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            # FastAPI may wrap the abort into its own error; only the abort is handled here.
            if not exceeded:
                raise
        if exceeded:
            await _response(limit)(scope, receive, send)
