"""Request ID middleware for request correlation and tracing."""

import uuid
from typing import Callable

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to each request for log correlation.

    The request ID is read from the X-Request-ID header if present, otherwise
    a new 8-character UUID prefix is generated. The ID is attached to the
    request and added to the response headers so clients can correlate logs.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[
            :8
        ]
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
