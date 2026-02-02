"""
Cerberus CTF Platform - Health Check Endpoints
Database, Redis, and disk health monitoring
"""

import os
import shutil
from datetime import datetime
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from app.infrastructure.database import DatabaseManager
from app.infrastructure.cache import CacheManager

logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    checks: Dict[str, Any]


class ComponentHealth(BaseModel):
    """Individual component health."""
    status: str
    latency_ms: float | None = None
    details: Dict[str, Any] | None = None


async def get_db_manager(request: Request) -> DatabaseManager:
    """Get database manager from app state."""
    return request.app.state.db


async def get_cache_manager(request: Request) -> CacheManager:
    """Get cache manager from app state."""
    return request.app.state.cache


@router.get(
    "",
    response_model=HealthStatus,
    summary="Health Check",
    description="Comprehensive health check for all services",
)
async def health_check(
    request: Request,
    db: DatabaseManager = Depends(get_db_manager),
    cache: CacheManager = Depends(get_cache_manager),
) -> HealthStatus:
    """
    Perform comprehensive health check.
    
    Checks:
    - Database connectivity and pool status
    - Redis connectivity and memory usage
    - Disk space availability
    """
    import time
    
    checks: Dict[str, Any] = {}
    overall_status = "healthy"
    
    # Database health check
    start = time.monotonic()
    db_health = await db.health_check()
    db_latency = (time.monotonic() - start) * 1000
    
    checks["database"] = {
        **db_health,
        "latency_ms": round(db_latency, 2),
    }
    
    if db_health["status"] != "healthy":
        overall_status = "degraded"
    
    # Redis health check
    start = time.monotonic()
    cache_health = await cache.health_check()
    cache_latency = (time.monotonic() - start) * 1000
    
    checks["redis"] = {
        **cache_health,
        "latency_ms": round(cache_latency, 2),
    }
    
    if cache_health["status"] != "healthy":
        overall_status = "degraded"
    
    # Disk health check
    disk_health = check_disk_health()
    checks["disk"] = disk_health
    
    if disk_health["status"] != "healthy":
        overall_status = "degraded"
    
    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=request.app.state.settings.app_version,
        checks=checks,
    )


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Kubernetes liveness probe endpoint",
)
async def liveness() -> Dict[str, str]:
    """
    Liveness probe for Kubernetes.
    
    Returns 200 if the application is running.
    """
    return {"status": "alive"}


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Kubernetes readiness probe endpoint",
)
async def readiness(
    db: DatabaseManager = Depends(get_db_manager),
    cache: CacheManager = Depends(get_cache_manager),
) -> Dict[str, str]:
    """
    Readiness probe for Kubernetes.
    
    Returns 200 if the application is ready to serve traffic.
    """
    # Check database
    db_health = await db.health_check()
    if db_health["status"] != "healthy":
        return {"status": "not_ready", "reason": "database"}
    
    # Check cache
    cache_health = await cache.health_check()
    if cache_health["status"] != "healthy":
        return {"status": "not_ready", "reason": "cache"}
    
    return {"status": "ready"}


def check_disk_health(
    path: str = "/opt/cerberus/data",
    warning_threshold: float = 0.8,
    critical_threshold: float = 0.95,
) -> Dict[str, Any]:
    """
    Check disk space availability.
    
    Args:
        path: Path to check
        warning_threshold: Warning threshold (0-1)
        critical_threshold: Critical threshold (0-1)
        
    Returns:
        Disk health status
    """
    try:
        # Use root path if specified path doesn't exist
        check_path = path if os.path.exists(path) else "/"
        
        total, used, free = shutil.disk_usage(check_path)
        usage_ratio = used / total
        
        status = "healthy"
        if usage_ratio >= critical_threshold:
            status = "critical"
        elif usage_ratio >= warning_threshold:
            status = "warning"
        
        return {
            "status": status,
            "path": check_path,
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "usage_percent": round(usage_ratio * 100, 1),
        }
    except Exception as e:
        logger.error("Disk health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }
