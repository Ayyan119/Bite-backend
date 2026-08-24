"""Global exception handlers and error response formatters for FastAPI."""

import logging
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException | HTTPException
) -> ORJSONResponse:
    """Handle custom HTTP exceptions with uniform JSON output."""
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> ORJSONResponse:
    """Handle Pydantic request validation errors with formatted detail list."""
    errors = []
    for err in exc.errors():
        location = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append(
            {
                "field": location,
                "message": err.get("msg"),
                "type": err.get("type"),
            }
        )

    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Request validation failed.",
                "details": errors,
            }
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> ORJSONResponse:
    """Catch unhandled internal server errors without leaking tracebacks in production."""
    logger.exception(f"Unhandled exception during request processing: {exc}")
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error occurred. Please try again later.",
            }
        },
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application instance."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
