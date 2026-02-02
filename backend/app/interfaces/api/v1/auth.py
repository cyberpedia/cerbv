"""
Cerberus CTF Platform - Authentication Endpoints
JWT auth with RBAC
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field

from app.core.config import Settings, get_settings
from app.domain.security.services import PasswordService, TokenService

logger = structlog.get_logger(__name__)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# =============================================================================
# Request/Response Models
# =============================================================================

class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(min_length=12)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""
    username: str
    password: str
    totp_code: str | None = None


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    email: str
    role: str
    display_name: str | None
    email_verified: bool
    two_factor_enabled: bool
    created_at: datetime


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(min_length=12)


class TwoFactorSetupResponse(BaseModel):
    """2FA setup response."""
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class TwoFactorVerifyRequest(BaseModel):
    """2FA verification request."""
    code: str = Field(min_length=6, max_length=6)


# =============================================================================
# JWT Utilities
# =============================================================================

def create_access_token(
    data: dict,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    data: dict,
    settings: Settings,
) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    
    to_encode.update({"exp": expire, "type": "refresh"})
    
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, settings: Settings) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# =============================================================================
# Dependencies
# =============================================================================

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    request: Request,
) -> dict:
    """
    Get current authenticated user from JWT token.
    
    This is a simplified version - in production, this would
    fetch the full user from the database.
    """
    settings = request.app.state.settings
    
    payload = decode_token(token, settings)
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # In production, fetch user from database here
    return {
        "id": user_id,
        "username": payload.get("username"),
        "role": payload.get("role"),
    }


async def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require admin role."""
    if current_user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_super_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Require super admin role."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login for Access Token",
    description="OAuth2 compatible token endpoint",
)
async def login_for_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """
    OAuth2 compatible login endpoint.
    
    Returns access and refresh tokens.
    """
    settings = request.app.state.settings
    password_service = PasswordService(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
    )
    
    # In production, fetch user from database and verify password
    # This is a placeholder implementation
    
    # Create tokens
    token_data = {
        "sub": "user-id-placeholder",
        "username": form_data.username,
        "role": "player",
    }
    
    access_token = create_access_token(token_data, settings)
    refresh_token = create_refresh_token(token_data, settings)
    
    logger.info("User logged in", username=form_data.username)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
)
async def refresh_token(
    request: Request,
    body: TokenRefreshRequest,
) -> TokenResponse:
    """Refresh access token using refresh token."""
    settings = request.app.state.settings
    
    payload = decode_token(body.refresh_token, settings)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # Create new tokens
    token_data = {
        "sub": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }
    
    access_token = create_access_token(token_data, settings)
    refresh_token = create_refresh_token(token_data, settings)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
)
async def register(
    request: Request,
    body: RegisterRequest,
) -> UserResponse:
    """Register a new user account."""
    settings = request.app.state.settings
    password_service = PasswordService(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
    )
    
    # Validate password
    is_valid, errors = password_service.validate_password(body.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"password_errors": errors},
        )
    
    # Hash password
    password_hash = password_service.hash_password(body.password)
    
    # In production, create user in database
    # This is a placeholder implementation
    
    logger.info("User registered", username=body.username)
    
    return UserResponse(
        id="new-user-id",
        username=body.username,
        email=body.email,
        role="player",
        display_name=body.display_name,
        email_verified=False,
        two_factor_enabled=False,
        created_at=datetime.now(timezone.utc),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User",
)
async def get_me(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user profile."""
    # In production, fetch full user from database
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email="user@example.com",
        role=current_user["role"],
        display_name=None,
        email_verified=True,
        two_factor_enabled=False,
        created_at=datetime.now(timezone.utc),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
)
async def logout(
    current_user: Annotated[dict, Depends(get_current_user)],
    request: Request,
) -> None:
    """
    Logout current user.
    
    In production, this would invalidate the refresh token.
    """
    logger.info("User logged out", user_id=current_user["id"])
