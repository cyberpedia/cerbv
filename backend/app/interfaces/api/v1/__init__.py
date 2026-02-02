"""
Cerberus CTF Platform - API v1 Router
Aggregates all API endpoints
"""

from fastapi import APIRouter

from app.interfaces.api.v1.health import router as health_router
from app.interfaces.api.v1.auth import router as auth_router
from app.interfaces.api.v1.users import router as users_router
from app.interfaces.api.v1.challenges import router as challenges_router
from app.interfaces.api.v1.submissions import router as submissions_router
from app.interfaces.api.v1.orchestrator_advanced import router as orchestrator_advanced_router
from app.interfaces.api.v1.privacy import router as privacy_router
from app.interfaces.api.v1.analytics import router as analytics_router

api_router = APIRouter()

# Health check endpoints
api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)

# Authentication endpoints
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)

# User management endpoints
api_router.include_router(
    users_router,
    prefix="/users",
    tags=["Users"],
)

# Challenge endpoints
api_router.include_router(
    challenges_router,
    prefix="/challenges",
    tags=["Challenges"],
)

# Submission endpoints
api_router.include_router(
    submissions_router,
    prefix="/submissions",
    tags=["Submissions"],
)

# Advanced Orchestrator endpoints
api_router.include_router(
    orchestrator_advanced_router,
    prefix="/orchestrator",
    tags=["Advanced Orchestrator"],
)

# Privacy and GDPR endpoints
api_router.include_router(
    privacy_router,
    prefix="/privacy",
    tags=["Privacy & GDPR"],
)

# Analytics endpoints
api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"],
)
