"""
Cerberus CTF Platform - Error Handler Middleware
Consistent error response format
"""

import traceback
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler middleware.
    
    Catches all unhandled exceptions and returns consistent error responses.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process request and handle any exceptions.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response or error response
        """
        try:
            return await call_next(request)
        
        except Exception as exc:
            # Get request ID if available
            request_id = getattr(request.state, "request_id", None)
            
            # Log the error
            logger.error(
                "Unhandled exception",
                error=str(exc),
                error_type=type(exc).__name__,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
                traceback=traceback.format_exc(),
            )
            
            # Determine error code and status
            error_code, status_code, detail = self._classify_error(exc)
            
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": error_code,
                    "detail": detail,
                    "request_id": request_id,
                },
            )
    
    def _classify_error(self, exc: Exception) -> tuple[str, int, str]:
        """
        Classify exception and return error details.
        
        Args:
            exc: The exception to classify
            
        Returns:
            Tuple of (error_code, status_code, detail)
        """
        # Import here to avoid circular imports
        from sqlalchemy.exc import IntegrityError, OperationalError
        from redis.exceptions import ConnectionError as RedisConnectionError
        
        # Database errors
        if isinstance(exc, IntegrityError):
            return "DATABASE_INTEGRITY_ERROR", 409, "Database constraint violation"
        
        if isinstance(exc, OperationalError):
            return "DATABASE_ERROR", 503, "Database operation failed"
        
        # Redis errors
        if isinstance(exc, RedisConnectionError):
            return "CACHE_ERROR", 503, "Cache service unavailable"
        
        # Validation errors
        if isinstance(exc, ValueError):
            return "VALIDATION_ERROR", 400, str(exc)
        
        # Permission errors
        if isinstance(exc, PermissionError):
            return "PERMISSION_DENIED", 403, str(exc)
        
        # Not found errors
        if isinstance(exc, LookupError):
            return "NOT_FOUND", 404, str(exc)
        
        # Default: internal server error
        return "INTERNAL_ERROR", 500, "An unexpected error occurred"
