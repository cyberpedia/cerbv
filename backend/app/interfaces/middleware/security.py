"""
Cerberus CTF Platform - Security Middleware
Security headers, CORS, and request validation
"""

import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Implements:
    - Content-Security-Policy (CSP)
    - Strict-Transport-Security (HSTS)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """
    
    def __init__(self, app: ASGIApp, settings: Settings):
        """
        Initialize security headers middleware.
        
        Args:
            app: ASGI application
            settings: Application settings
        """
        super().__init__(app)
        self._settings = settings
        self._csp = self._build_csp()
    
    def _build_csp(self) -> str:
        """Build Content-Security-Policy header value."""
        directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # Adjust for your frontend
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        return "; ".join(directives)
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process request and add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with security headers
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Bind request ID to logger context
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        
        # HSTS (only in production with HTTPS)
        if self._settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # CSP
        response.headers["Content-Security-Policy"] = self._csp
        
        # Clear logger context
        structlog.contextvars.unbind_contextvars("request_id")
        
        return response


class RequestSigningMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify request signatures.
    
    Validates X-Cerberus-Sig header for authenticated requests.
    """
    
    def __init__(self, app: ASGIApp, settings: Settings):
        """
        Initialize request signing middleware.
        
        Args:
            app: ASGI application
            settings: Application settings
        """
        super().__init__(app)
        self._settings = settings
        
        from app.domain.security.services import RequestSigningService
        self._signing_service = RequestSigningService(settings.request_signing_key)
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Verify request signature if present.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response or 401 if signature invalid
        """
        # Skip signature verification for certain paths
        skip_paths = ["/api/v1/health", "/api/docs", "/api/redoc", "/metrics"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Check for signature header
        signature = request.headers.get("X-Cerberus-Sig")
        timestamp = request.headers.get("X-Cerberus-Timestamp")
        
        if signature and timestamp:
            # Read body for signature verification
            body = await request.body()
            
            # Verify signature
            is_valid = self._signing_service.verify_signature(
                signature=signature,
                method=request.method,
                path=request.url.path,
                timestamp=timestamp,
                body=body.decode() if body else "",
            )
            
            if not is_valid:
                logger.warning(
                    "Invalid request signature",
                    path=request.url.path,
                    method=request.method,
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "INVALID_SIGNATURE",
                        "detail": "Request signature verification failed",
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )
        
        return await call_next(request)
