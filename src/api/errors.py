"""
Інструмент: Claude
Застосування: Реалізація єдиної структури обробки доменних помилок API (ApiError) та помилок валідації (RequestValidationError).
Верифікація: Перевірено вручну формат відповідей для статус-кодів 404, 409 та 422, узгоджено командою.
"""

"""
Узгоджена обробка помилок для всього API.

Кожна помилка повертається за єдиним каркасом (ErrorResponse зі schemas.py):
код, людиночитане повідомлення, деталі по полях, request_id, посилання на docs.
Це прибирає типовий антипатерн "різні формати помилок у різних кінцевих точках".
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .schemas import ErrorBody, ErrorDetail, ErrorResponse

DOCS_BASE = "/docs/api/api-design.md#error-handling"


class ApiError(Exception):
    """Базовий клас доменних помилок API (404 / 409 / 403 тощо)."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "NOT_FOUND", message)


class ConflictError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:10]}")


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = f"req_{uuid.uuid4().hex[:10]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                details=[],
                request_id=_request_id(request),
                documentation=DOCS_BASE,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(p) for p in err["loc"] if p != "body"),
                message=err["msg"],
                provided_value=str(err.get("input")) if err.get("input") is not None else None,
            )
            for err in exc.errors()
        ]
        body = ErrorResponse(
            error=ErrorBody(
                code="VALIDATION_ERROR",
                message="Запит містить невалідні поля",
                details=details,
                request_id=_request_id(request),
                documentation=f"{DOCS_BASE}#validation",
            )
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(mode="json"),
        )