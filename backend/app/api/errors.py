"""Erros de API e handlers que os serializam como JSON.

Forma padrão de resposta de erro:
    {"error": {"code": "...", "message": "...", "details": {...}?}}

Serviços lançam `ApiError` (ou subclasses); handlers viram o JSON.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import jsonify
from pydantic import ValidationError as PydanticValidationError
from werkzeug.exceptions import HTTPException

if TYPE_CHECKING:
    from flask import Flask
    from flask.typing import ResponseReturnValue


class ApiError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class Unauthorized(ApiError):
    status_code = 401
    code = "unauthorized"


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class Conflict(ApiError):
    status_code = 409
    code = "conflict"


class Gone(ApiError):
    status_code = 410
    code = "gone"


class UnprocessableEntity(ApiError):
    status_code = 422
    code = "validation_error"


def _payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError) -> ResponseReturnValue:
        return jsonify(_payload(exc.code, exc.message, exc.details)), exc.status_code

    @app.errorhandler(PydanticValidationError)
    def _handle_pydantic(exc: PydanticValidationError) -> ResponseReturnValue:
        details = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return jsonify(_payload("validation_error", "invalid request body", details)), 422

    @app.errorhandler(HTTPException)
    def _handle_http(exc: HTTPException) -> ResponseReturnValue:
        code = (exc.name or "http_error").lower().replace(" ", "_")
        return jsonify(_payload(code, exc.description or exc.name or "")), exc.code or 500

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception) -> ResponseReturnValue:
        app.logger.exception("unhandled error", exc_info=exc)
        return jsonify(_payload("internal_error", "internal server error")), 500
