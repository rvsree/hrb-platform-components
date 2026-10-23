"""Shared error-response helper, same shape as hrb_chatbot_v2's api/dependencies.py::json_error.
Not business logic - safe for every src/platform/<module> to reuse."""

from fastapi.responses import JSONResponse


def json_error(status_code: int, message: str, code: str, **extra) -> JSONResponse:
    """Build a consistent error shape: {"error": ..., "code": ..., ...extra}."""
    body = {"error": message, "code": code}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body)
