"""
Cerberus CTF Platform - User Management Endpoints
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.interfaces.api.v1.auth import get_current_user, require_admin

router = APIRouter()


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[dict]
    cursor: str | None
    has_more: bool


class UserUpdateRequest(BaseModel):
    """User update request."""
    display_name: str | None = None
    bio: str | None = None
    country_code: str | None = None


class RoleChangeRequest(BaseModel):
    """Role change request."""
    role: str


@router.get(
    "",
    response_model=UserListResponse,
    summary="List Users",
    description="List users with cursor-based pagination",
)
async def list_users(
    current_user: Annotated[dict, Depends(require_admin)],
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    limit: int = Query(default=20, ge=1, le=100),
) -> UserListResponse:
    """List all users (admin only)."""
    # Placeholder implementation
    return UserListResponse(
        users=[],
        cursor=None,
        has_more=False,
    )


@router.get(
    "/{user_id}",
    summary="Get User",
)
async def get_user(
    user_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Get user by ID."""
    # Placeholder implementation
    return {"id": str(user_id), "username": "placeholder"}


@router.patch(
    "/{user_id}",
    summary="Update User",
)
async def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Update user profile."""
    # Check authorization
    if str(user_id) != current_user["id"] and current_user["role"] not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other users",
        )
    
    # Placeholder implementation
    return {"id": str(user_id), "updated": True}


@router.post(
    "/{user_id}/role",
    summary="Change User Role",
)
async def change_role(
    user_id: UUID,
    body: RoleChangeRequest,
    current_user: Annotated[dict, Depends(require_admin)],
) -> dict:
    """Change user role (admin only)."""
    # Placeholder implementation
    return {"id": str(user_id), "role": body.role}


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User",
)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[dict, Depends(require_admin)],
) -> None:
    """Soft delete user (admin only)."""
    pass
