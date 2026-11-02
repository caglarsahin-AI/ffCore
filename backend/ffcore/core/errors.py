"""OpenAI-shaped error bodies for every 4xx: {"error": {"message", "type", "code"}} (brief 03)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_TYPE_BY_STATUS = {
    400: ("invalid_request_error", "bad_request"),
    401: ("authentication_error", "unauthenticated"),
    403: ("permission_error", "forbidden"),
    404: ("not_found_error", "not_found"),
    405: ("invalid_request_error", "method_not_allowed"),
    409: ("conflict_error", "conflict"),
    422: ("invalid_request_error", "validation_error"),
    429: ("rate_limit_error", "rate_limited"),
}


class ApiError(Exception):
    """Typed, actionable error; message is English and never carries secrets."""

    def __init__(
        self, status_code: int, error_type: str, code: str, message: str, param: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.message = message
        # OpenAI's `param`: the request field the error is about (06b review r2); additive.
        self.param = param


def error_body(error_type: str, code: str, message: str, param: str | None = None) -> dict:
    error = {"message": message, "type": error_type, "code": code}
    if param is not None:
        error["param"] = param
    return {"error": error}


def _response(status_code: int, error_type: str, code: str, message: str, headers=None, param=None):
    return JSONResponse(error_body(error_type, code, message, param), status_code, headers=headers)


async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return _response(exc.status_code, exc.error_type, exc.code, exc.message, headers, exc.param)


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    error_type, code = _TYPE_BY_STATUS.get(exc.status_code, ("api_error", "http_error"))
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _response(exc.status_code, error_type, code, message, getattr(exc, "headers", None))


def _coded(exc: RequestValidationError) -> tuple[str, str] | None:
    """(code, message) of the first coded refusal among the errors, e.g. a C8 definition check."""
    for error in exc.errors():
        cause = (error.get("ctx") or {}).get("error")
        code = getattr(cause, "code", None)
        if isinstance(cause, ValueError) and isinstance(code, str):
            message = getattr(cause, "message", str(cause))
            where = ".".join(str(p) for p in error.get("loc", ()) if p != "body")
            return code, f"{where}: {message}" if where else message
    return None


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    coded = _coded(exc)
    if coded is not None:
        return _response(422, "invalid_request_error", *coded)
    fields = sorted({".".join(str(p) for p in e.get("loc", ())) for e in exc.errors()})
    message = "Invalid request: " + ", ".join(fields) if fields else "Invalid request."
    return _response(422, "invalid_request_error", "validation_error", message)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
