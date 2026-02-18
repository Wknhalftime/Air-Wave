"""Query logging middleware for monitoring database performance.

This middleware tracks database query execution time and logs slow queries
to help identify performance bottlenecks.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class QueryLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log slow database queries and request timing.
    
    This middleware measures the total request time and logs warnings
    for requests that exceed the slow query threshold.
    
    Attributes:
        slow_query_threshold: Time in seconds to consider a query slow.
    """
    
    def __init__(self, app, slow_query_threshold: float = 1.0):
        """Initialize query logging middleware.
        
        Args:
            app: FastAPI application instance.
            slow_query_threshold: Threshold in seconds for slow query warnings.
        """
        super().__init__(app)
        self.slow_query_threshold = slow_query_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log timing information.
        
        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.
            
        Returns:
            HTTP response.
        """
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log request details
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "duration_ms": round(duration * 1000, 2),
            "status_code": response.status_code,
        }
        
        # Log slow queries
        if duration > self.slow_query_threshold:
            logger.warning(
                f"SLOW REQUEST: {log_data['method']} {log_data['path']} "
                f"took {log_data['duration_ms']}ms (threshold: {self.slow_query_threshold * 1000}ms)"
            )
        else:
            logger.debug(
                f"{log_data['method']} {log_data['path']} - "
                f"{log_data['duration_ms']}ms - {log_data['status_code']}"
            )
        
        # Add timing header to response
        response.headers["X-Process-Time"] = str(duration)
        
        return response

