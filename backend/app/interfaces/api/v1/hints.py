"""
Cerberus CTF Platform - Hint System API Endpoints
Advanced hint management with progressive unlocks
"""

from typing import Annotated, Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.application.hints.service import AvailableHint, HintService, HintUnlockResult
from app.interfaces.api.v1.auth import get_current_user, require_admin

router = APIRouter()


# Request/Response Models

class HintResponse(BaseModel):
    """Hint response model."""
    id: str
    title: str | None
    sequence_order: int
    is_unlocked: bool
    can_unlock: bool
    cost: float
    conditions_not_met: list[str]
    unlocked_at: str | None
    preview: str | None
    content_type: str
    attachment_url: str | None


class HintsListResponse(BaseModel):
    """List of hints for a challenge."""
    challenge_id: str
    hints: list[HintResponse]
    hint_system_enabled: bool
    deduction_type: str
    deduction_value: float


class HintUnlockResponse(BaseModel):
    """Hint unlock response."""
    success: bool
    hint_id: str
    content: str | None
    content_type: str
    attachment_url: str | None
    points_deducted: float
    message: str
    conditions_not_met: list[str]


class HintPreviewResponse(BaseModel):
    """Hint preview response."""
    id: str
    title: str | None
    preview: str
    content_type: str
    is_unlocked: bool
    sequence_order: int


class HintCreateRequest(BaseModel):
    """Create hint request (admin)."""
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1)
    content_type: str = Field(default="text", pattern="^(text|image|video|link)$")
    attachment_url: str | None = None
    sequence_order: int = Field(default=0, ge=0)
    unlock_after_minutes: int | None = Field(default=None, ge=0)
    unlock_after_attempts: int | None = Field(default=None, ge=1)
    unlock_after_hint_id: str | None = None
    custom_cost: float | None = Field(default=None, ge=0)


class HintConfigUpdateRequest(BaseModel):
    """Update hint config request (admin)."""
    enabled: bool | None = None
    unlock_mode: str | None = Field(
        default=None,
        pattern="^(manual|timed|progressive|attempt_based|purchase)$"
    )
    auto_unlock_minutes: int | None = Field(default=None, ge=1)
    progressive_chain: bool | None = None
    deduction_type: str | None = Field(
        default=None,
        pattern="^(points|percentage|time_penalty)$"
    )
    deduction_value: float | None = Field(default=None, ge=0)
    max_hints_visible: int | None = Field(default=None, ge=1)
    cooldown_seconds: int | None = Field(default=None, ge=0)


class HintReorderRequest(BaseModel):
    """Reorder hints request (admin)."""
    hint_ids: list[str] = Field(min_length=1)


class ProgressiveChainResponse(BaseModel):
    """Progressive chain status response."""
    challenge_id: str
    chain_status: list[Dict[str, Any]]
    next_unlock_id: str | None
    completed: bool


# Dependencies

async def get_hint_service():
    """Get hint service instance."""
    raise NotImplementedError("Service dependency to be wired")


# Endpoints

@router.get(
    "/{challenge_id}/hints",
    response_model=HintsListResponse,
    summary="Get Available Hints",
    description="Get all hints for challenge with unlock status and costs for current user.",
)
async def get_available_hints(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> HintsListResponse:
    """Get hints available to user for challenge."""
    try:
        user_id = UUID(current_user["id"])
        
        # Get available hints
        available_hints = await hint_service.get_available_hints(challenge_id, user_id)
        
        # Get config
        config = await hint_service.get_hint_config(challenge_id)
        
        # Convert to response format
        hints = [hint.to_dict() for hint in available_hints]
        
        return HintsListResponse(
            challenge_id=str(challenge_id),
            hints=[HintResponse(**h) for h in hints],
            hint_system_enabled=config.enabled if config else False,
            deduction_type=config.deduction_type.value if config else "points",
            deduction_value=float(config.deduction_value) if config else 10.0
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/hints/{hint_id}/unlock",
    response_model=HintUnlockResponse,
    summary="Unlock Hint",
    description="Unlock a hint, deducting points if applicable. Idempotent - safe to retry.",
    responses={
        403: {"description": "Unlock conditions not met or already solved"},
        409: {"description": "Insufficient points"},
        429: {"description": "Cooldown period active"},
    }
)
async def unlock_hint(
    hint_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> HintUnlockResponse:
    """Unlock a hint."""
    try:
        user_id = UUID(current_user["id"])
        
        result: HintUnlockResult = await hint_service.unlock_hint(hint_id, user_id)
        
        if not result.success:
            # Determine appropriate status code
            if "conditions not met" in result.message.lower():
                status_code = status.HTTP_403_FORBIDDEN
            elif "insufficient points" in result.message.lower():
                status_code = status.HTTP_409_CONFLICT
            elif "already solved" in result.message.lower():
                status_code = status.HTTP_403_FORBIDDEN
            elif "cooldown" in result.message.lower():
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            else:
                status_code = status.HTTP_400_BAD_REQUEST
            
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": result.message,
                    "conditions_not_met": result.conditions_not_met
                }
            )
        
        # Build response
        return HintUnlockResponse(
            success=True,
            hint_id=str(hint_id),
            content=result.hint.content if result.hint else None,
            content_type=result.hint.content_type if result.hint else "text",
            attachment_url=result.hint.attachment_url if result.hint else None,
            points_deducted=float(result.points_deducted),
            message=result.message,
            conditions_not_met=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/hints/{hint_id}/preview",
    response_model=HintPreviewResponse,
    summary="Get Hint Preview",
    description="Get truncated preview of hint content before unlocking.",
)
async def get_hint_preview(
    hint_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
    preview_length: int = 100
) -> HintPreviewResponse:
    """Get hint preview."""
    try:
        user_id = UUID(current_user["id"])
        
        preview = await hint_service.get_hint_preview(hint_id, user_id, preview_length)
        
        if "error" in preview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=preview["error"]
            )
        
        return HintPreviewResponse(**preview)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{challenge_id}/hints/chain",
    response_model=ProgressiveChainResponse,
    summary="Get Progressive Chain Status",
    description="Get status of progressive hint chain for challenge.",
)
async def get_progressive_chain(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> ProgressiveChainResponse:
    """Get progressive chain status."""
    try:
        user_id = UUID(current_user["id"])
        
        chain_status = await hint_service.check_progressive_chain(challenge_id, user_id)
        
        return ProgressiveChainResponse(**chain_status)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Admin Endpoints

@router.post(
    "/{challenge_id}/admin/hints",
    status_code=status.HTTP_201_CREATED,
    summary="Create Hint (Admin)",
    description="Create a new hint with unlock conditions.",
)
async def create_hint(
    challenge_id: UUID,
    body: HintCreateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> Dict[str, Any]:
    """Create hint (admin only)."""
    # Implementation would create hint
    raise NotImplementedError("Admin endpoint to be implemented")


@router.patch(
    "/hints/{hint_id}/admin",
    summary="Update Hint (Admin)",
    description="Update hint content and unlock conditions.",
)
async def update_hint(
    hint_id: UUID,
    body: HintCreateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> Dict[str, Any]:
    """Update hint (admin only)."""
    raise NotImplementedError("Admin endpoint to be implemented")


@router.delete(
    "/hints/{hint_id}/admin",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Hint (Admin)",
)
async def delete_hint(
    hint_id: UUID,
    current_user: Annotated[dict, Depends(require_admin)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> None:
    """Delete hint (admin only)."""
    pass


@router.patch(
    "/{challenge_id}/admin/hint-config",
    summary="Update Hint Config (Admin)",
    description="Update hint system configuration for challenge.",
)
async def update_hint_config(
    challenge_id: UUID,
    body: HintConfigUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> Dict[str, Any]:
    """Update hint config (admin only)."""
    raise NotImplementedError("Admin endpoint to be implemented")


@router.put(
    "/{challenge_id}/admin/hints/order",
    summary="Reorder Hints (Admin)",
    description="Reorder hints in progressive chain.",
)
async def reorder_hints(
    challenge_id: UUID,
    body: HintReorderRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    hint_service: Annotated[HintService, Depends(get_hint_service)],
) -> Dict[str, Any]:
    """Reorder hints (admin only)."""
    raise NotImplementedError("Admin endpoint to be implemented")
