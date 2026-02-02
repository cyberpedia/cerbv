"""
Cerberus CTF Platform - FastAPI Application Factory
Clean Architecture with dependency injection
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.infrastructure.database import DatabaseManager
from app.infrastructure.cache import CacheManager
from app.infrastructure.orchestrator.services.ad_manager import ADManager
from app.infrastructure.orchestrator.services.koth_manager import KOTHManager
from app.infrastructure.orchestrator.services.programming_judge import ProgrammingJudge
from app.infrastructure.orchestrator.services.hardware_lab import HardwareLabManager
from app.infrastructure.orchestrator.services.websocket_manager import ConnectionManager
from app.interfaces.api.v1 import api_router
from app.interfaces.middleware.security import SecurityHeadersMiddleware
from app.interfaces.middleware.request_signing import RequestSigningMiddleware
from app.interfaces.middleware.error_handler import ErrorHandlerMiddleware

# Advanced orchestrator services
ad_manager: Optional[ADManager] = None
koth_manager: Optional[KOTHManager] = None
programming_judge: Optional[ProgrammingJudge] = None
hardware_lab: Optional[HardwareLabManager] = None
ws_manager: Optional[ConnectionManager] = None

logger = structlog.get_logger(__name__)


def create_limiter(settings: Settings) -> Limiter:
    """Create rate limiter with Redis backend."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
        storage_uri=settings.redis_url,
        strategy="fixed-window",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown."""
    settings = get_settings()
    
    # Setup structured logging
    setup_logging(settings.log_level, settings.log_format)
    
    logger.info("Starting Cerberus CTF Platform", version=settings.app_version)
    
    # Initialize database connection pool
    db_manager = DatabaseManager(settings)
    await db_manager.connect()
    app.state.db = db_manager
    
    # Initialize cache connection
    cache_manager = CacheManager(settings)
    await cache_manager.connect()
    app.state.cache = cache_manager
    
    # Initialize WebSocket connection manager
    global ws_manager
    ws_manager = ConnectionManager(cache_manager)
    await ws_manager.start()
    app.state.ws_manager = ws_manager
    
    # Initialize AD Manager
    global ad_manager
    ad_manager = ADManager(
        db_manager,
        cache_manager,
        flag_secret_key=settings.secret_key.encode(),
        tick_duration=settings.ad_tick_duration or 300,
    )
    await ad_manager.start()
    app.state.ad_manager = ad_manager
    
    # Initialize KOTH Manager
    global koth_manager
    koth_manager = KOTHManager(
        db_manager,
        cache_manager,
        koth_host=settings.koth_host,
        ssh_port=settings.koth_ssh_port or 22,
        check_interval=60,
    )
    await koth_manager.start()
    app.state.koth_manager = koth_manager
    
    # Initialize Programming Judge
    global programming_judge
    programming_judge = ProgrammingJudge(
        db_manager,
        cache_manager,
        scoring_mode="static",
    )
    app.state.programming_judge = programming_judge
    
    # Initialize Hardware Lab Manager
    global hardware_lab
    hardware_lab = HardwareLabManager(db_manager, cache_manager)
    await hardware_lab.start()
    app.state.hardware_lab = hardware_lab
    
    logger.info("All services initialized successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Cerberus CTF Platform")
    
    # Stop advanced services
    if ws_manager:
        await ws_manager.stop()
    if ad_manager:
        await ad_manager.stop()
    if koth_manager:
        await koth_manager.stop()
    if hardware_lab:
        await hardware_lab.stop()
    
    await cache_manager.disconnect()
    await db_manager.disconnect()
    logger.info("Shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory pattern for FastAPI.
    
    Args:
        settings: Optional settings override for testing
        
    Returns:
        Configured FastAPI application instance
    """
    if settings is None:
        settings = get_settings()
    
    app = FastAPI(
        title="Cerberus CTF Platform",
        description="Enterprise-grade Capture The Flag platform",
        version=settings.app_version,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    
    # Store settings in app state
    app.state.settings = settings
    
    # Setup rate limiter
    limiter = create_limiter(settings)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Add middleware (order matters - last added is first executed)
    
    # Error handler (outermost)
    app.add_middleware(ErrorHandlerMiddleware)
    
    # Security headers
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    
    # Request signing verification
    if settings.require_request_signing:
        app.add_middleware(RequestSigningMiddleware, settings=settings)
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Cerberus-Sig"],
    )
    
    # Mount Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    return app


# Create default application instance
app = create_app()
