"""Problem details (RFC 9457, `application/problem+json`) for every API error."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from mdcopilot_blog.domain.errors import (
    ArticleStructureError,
    PublishingDisabled,
    UnknownCitationMarker,
)
from mdcopilot_blog.domain.state_machine import InvalidTransition

PROBLEM_JSON = "application/problem+json"
VALIDATION_TITLE = "Request validation failed"


class ProblemError(Exception):
    """Raise anywhere in a request to return a problem+json response."""

    def __init__(self, status: int, title: str, detail: object | None = None, type_: str = "about:blank") -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: object | None = None,
    type_: str = "about:blank",
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Body `{type, title, status, instance, detail?}`; `detail` is made JSON-safe with `jsonable_encoder`."""
    body: dict[str, Any] = {"type": type_, "title": title, "status": status, "instance": request.url.path}
    if detail is not None:
        body["detail"] = jsonable_encoder(detail)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def _status_phrase(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def _plain(value: object) -> object:
    return value if value is None or isinstance(value, str | int | float | bool) else str(value)


def validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """`exc.errors()` without `input` (it can echo a submitted password) and with `ctx` values as plain JSON."""
    cleaned: list[dict[str, Any]] = []
    for error in exc.errors():
        item: dict[str, Any] = {key: error[key] for key in ("type", "loc", "msg") if key in error}
        ctx = error.get("ctx")
        if isinstance(ctx, Mapping):
            item["ctx"] = {str(key): _plain(value) for key, value in ctx.items()}
        cleaned.append(item)
    return cleaned


def install_problem_handlers(app: FastAPI) -> None:
    """Map ProblemError, Starlette/FastAPI HTTPException (incl. 404/405) and RequestValidationError."""

    @app.exception_handler(ProblemError)
    async def _problem_error(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(request, exc.status, exc.title, exc.detail, exc.type_)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, str):
            title, detail = exc.detail, None
        else:
            title, detail = _status_phrase(exc.status_code), exc.detail
        return problem_response(request, exc.status_code, title, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(request, 422, VALIDATION_TITLE, validation_errors(exc))

    @app.exception_handler(InvalidTransition)
    async def _invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        return problem_response(request, 409, "Invalid state transition", str(exc))

    @app.exception_handler(ArticleStructureError)
    async def _article_structure(request: Request, exc: ArticleStructureError) -> JSONResponse:
        return problem_response(request, 422, "Article structure invalid", str(exc))

    @app.exception_handler(UnknownCitationMarker)
    async def _unknown_marker(request: Request, exc: UnknownCitationMarker) -> JSONResponse:
        return problem_response(request, 422, "Unknown citation marker", str(exc))

    @app.exception_handler(PublishingDisabled)
    async def _publishing_disabled(request: Request, exc: PublishingDisabled) -> JSONResponse:
        return problem_response(request, 409, "Publishing disabled", str(exc))
