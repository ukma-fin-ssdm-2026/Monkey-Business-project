"""
Інструмент: Claude
Застосування: Реалізація єдиної структури обробки доменних помилок API (ApiError)
та помилок валідації (RequestValidationError); виправлення витоку тіла запиту
й секретів у provided_value (CWE-209).
Верифікація: Перевірено вручну формат відповідей для статус-кодів 404,
409 та 422, узгоджено командою; CWE-209 — регресійні тести tests/test_errors.py,
які падали до виправлення.

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

# Absolute URL: the API does not serve the markdown docs, so a
# relative path would 404 for clients.
DOCS_BASE = (
    "https://github.com/ukma-fin-ssdm-2026/Monkey-Business-project/"
    "blob/main/docs/api/api-design.md"
)

SENSITIVE_FIELD_MARKERS = ("password", "token", "secret")
MAX_PROVIDED_VALUE_LENGTH = 100


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


class UnauthorizedError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message)


class ForbiddenError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


class ConflictError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message)


class ServiceUnavailableError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", message)


def error_responses(
    not_found: str,
    invalid: str = "Невалідні параметри запиту",
    examples: dict | None = None,
    conflict: str | None = None,
) -> dict:
    # Without an explicit 422 entry FastAPI documents its default HTTPValidationError,
    # which is not what handle_validation_error actually returns.
    responses = {
        401: _error_response(
            "Потрібна автентифікація",
            "UNAUTHORIZED",
            "Потрібен Bearer-токен",
            "#error-handling",
        ),
        403: _error_response(
            "Недостатньо прав",
            "FORBIDDEN",
            "Недостатньо прав для виконання цієї дії",
            "#error-handling",
        ),
        404: _error_response(
            not_found,
            "NOT_FOUND",
            not_found,
            "#error-handling",
        ),
        422: _error_response(
            invalid,
            "VALIDATION_ERROR",
            "Запит містить невалідні поля",
            "#validation",
        ),
    }
    for code, response_examples in (examples or {}).items():
        if code in responses:
            responses[code]["content"]["application/json"]["examples"].update(
                response_examples
            )
    if conflict is not None:
        responses[409] = _error_response(
            "Конфлікт із поточним станом ресурсу",
            "CONFLICT",
            conflict,
            "#error-handling",
        )
    return responses


def _error_response(
    description: str,
    code: str,
    message: str,
    documentation_fragment: str,
) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "examples": {
                    code.lower(): {
                        "summary": message,
                        "value": {
                            "error": {
                                "code": code,
                                "message": message,
                                "details": [],
                                "request_id": "req_example",
                                "documentation": f"{DOCS_BASE}{documentation_fragment}",
                            }
                        },
                    }
                }
            }
        },
    }


def auth_error_responses(
    *,
    unauthorized: str = "Невірний email або пароль",
    conflict: str | None = None,
    forbidden: str | None = None,
) -> dict:
    responses = {
        401: _error_response(
            "Невірні облікові дані",
            "UNAUTHORIZED",
            unauthorized,
            "#error-handling",
        )
    }
    if conflict is not None:
        responses[409] = _error_response(
            "Email уже зареєстровано",
            "CONFLICT",
            conflict,
            "#error-handling",
        )
    if forbidden is not None:
        responses[403] = _error_response(
            "Недостатньо прав",
            "FORBIDDEN",
            forbidden,
            "#error-handling",
        )
    responses[422] = _error_response(
        "Невалідні дані запиту",
        "VALIDATION_ERROR",
        "Запит містить невалідні поля",
        "#validation",
    )
    return responses


def _safe_provided_value(err: dict) -> str | None:
    """Значення для provided_value без витоку тіла запиту та секретів (CWE-209)."""
    value = err.get("input")
    # For `missing` errors Pydantic puts the whole parent object into `input`,
    # so dicts and lists can carry other fields such as the password.
    if value is None or err["type"] == "missing" or isinstance(value, (dict, list)):
        return None
    field = str(err["loc"][-1]).lower() if err["loc"] else ""
    if any(marker in field for marker in SENSITIVE_FIELD_MARKERS):
        return None
    return str(value)[:MAX_PROVIDED_VALUE_LENGTH]


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
                documentation=f"{DOCS_BASE}#error-handling",
            )
        )
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=body.model_dump(mode="json"),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(p) for p in err["loc"] if p != "body"),
                message=err["msg"],
                provided_value=_safe_provided_value(err),
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
