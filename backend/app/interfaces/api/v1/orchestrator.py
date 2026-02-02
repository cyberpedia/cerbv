"""
Cerberus CTF Platform - Orchestrator API Endpoints

API for challenge instance lifecycle management:
- POST /orchestrator/spawn - Create new challenge instance
- GET /orchestrator/status/{instance_id} - Get instance status
- DELETE /orchestrator/destroy/{instance_id} - Destroy instance
- WebSocket /orchestrator/logs/{instance_id} - Stream logs
"""

from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager
from app.infrastructure.orchestrator.models import (
    ChallengeInstance,
    SandboxType,
    SpawnRequest,
)
from app.infrastructure.orchestrator.services.challenge_manager import ChallengeManager
from app.interfaces.api.v1.auth import get_current_user, require_admin

logger = structlog.get_logger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class SpawnRequestBody(BaseModel):
    """Request body for spawning a challenge instance."""
    challenge_id: UUID = Field(..., description="Challenge ID to spawn")
    sandbox_type: str = Field(default="docker", description="Sandbox type (docker, firecracker, terraform_aws, terraform_gcp)")
    timeout_seconds: int = Field(default=7200, ge=300, le=14400, description="Instance timeout in seconds (5 min - 4 hours)")


class SpawnResponse(BaseModel):
    """Response for spawn request."""
    success: bool
    instance_id: Optional[str] = None
    status: str
    access_url: Optional[str] = None
    connection_string: Optional[str] = None
    error_message: Optional[str] = None
    expires_at: Optional[str] = None


class InstanceStatusResponse(BaseModel):
    """Response for instance status request."""
    instance_id: str
    challenge_id: str
    user_id: str
    status: str
    sandbox_type: str
    access_url: Optional[str] = None
    connection_string: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    expires_at: Optional[str] = None
    health_check_failures: int = 0


class InstanceListResponse(BaseModel):
    """Response for listing user instances."""
    instances: list[InstanceStatusResponse]
    total: int


class ExtendTimeoutRequest(BaseModel):
    """Request to extend instance timeout."""
    additional_seconds: int = Field(..., ge=300, le=7200, description="Additional time in seconds (5 min - 2 hours)")


class ExtendTimeoutResponse(BaseModel):
    """Response for extend timeout request."""
    success: bool
    new_expires_at: Optional[str] = None
    error_message: Optional[str] = None


class DestroyResponse(BaseModel):
    """Response for destroy request."""
    success: bool
    message: str


# ============================================================================
# Dependencies
# ============================================================================

async def get_challenge_manager(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChallengeManager:
    """Get or create ChallengeManager instance."""
    # TODO: Proper dependency injection with lifespan management
    db_manager = DatabaseManager(settings)
    cache_manager = CacheManager(settings)
    
    # Note: In production, these should be managed via app state
    await db_manager.connect()
    await cache_manager.connect()
    
    manager = ChallengeManager(db_manager, cache_manager)
    return manager


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/spawn",
    response_model=SpawnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Spawn Challenge Instance",
    description="Create a new isolated challenge instance for the current user",
)
async def spawn_instance(
    body: SpawnRequestBody,
    current_user: Annotated[dict, Depends(get_current_user)],
    manager: Annotated[ChallengeManager, Depends(get_challenge_manager)],
) -> SpawnResponse:
    """
    Spawn a new challenge instance.
    
    Creates an isolated sandbox environment (Docker container, Firecracker VM,
    or cloud instance) for the specified challenge.
    """
    try:
        # Validate sandbox type
        try:
            sandbox_type = SandboxType(body.sandbox_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sandbox type: {body.sandbox_type}",
            )
        
        # Create spawn request
        request = SpawnRequest(
            challenge_id=body.challenge_id,
            user_id=UUID(current_user["id"]),
            team_id=UUID(current_user.get("team_id")) if current_user.get("team_id") else None,
            sandbox_type=sandbox_type,
            timeout_seconds=body.timeout_seconds,
        )
        
        logger.info(
            "Spawning challenge instance",
            challenge_id=str(body.challenge_id),
            user_id=current_user["id"],
            sandbox_type=body.sandbox_type,
        )
        
        # Spawn instance
        result = await manager.spawn(request)
        
        if not result.success:
            logger.warning(
                "Failed to spawn instance",
                challenge_id=str(body.challenge_id),
                error=result.error_message,
            )
            return SpawnResponse(
                success=False,
                status="error",
                error_message=result.error_message,
            )
        
        instance = result.instance
        
        return SpawnResponse(
            success=True,
            instance_id=str(instance.id),
            status=instance.status.value,
            access_url=instance.access_url,
            connection_string=instance.connection_string,
            expires_at=instance.expires_at.isoformat() if instance.expires_at else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error spawning instance", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn instance: {str(e)}",
        )


@router.get(
    "/status/{instance_id}",
    response_model=InstanceStatusResponse,
    summary="Get Instance Status",
    description="Get current status of a challenge instance",
)
async def get_instance_status(
    instance_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    manager: Annotated[ChallengeManager, Depends(get_challenge_manager)],
) -> InstanceStatusResponse:
    """Get the status of a specific challenge instance."""
    try:
        instance = await manager.get_status(instance_id)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Instance not found",
            )
        
        # Verify ownership
        if str(instance.user_id) != current_user["id"] and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        
        return InstanceStatusResponse(
            instance_id=str(instance.id),
            challenge_id=str(instance.challenge_id),
            user_id=str(instance.user_id),
            status=instance.status.value,
            sandbox_type=instance.sandbox_type.value,
            access_url=instance.access_url,
            connection_string=instance.connection_string,
            created_at=instance.created_at.isoformat(),
            started_at=instance.started_at.isoformat() if instance.started_at else None,
            expires_at=instance.expires_at.isoformat() if instance.expires_at else None,
            health_check_failures=instance.health_check_failures,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting instance status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instance status: {str(e)}",
        )


@router.get(
    "/instances",
    response_model=InstanceListResponse,
    summary="List User Instances",
    description="List all active challenge instances for the current user",
)
async def list_user_instances(
    current_user: Annotated[dict, Depends(get_current_user)],
    manager: Annotated[ChallengeManager, Depends(get_challenge_manager)],
) -> InstanceListResponse:
    """List all active instances for the current user."""
    try:
        instances = await manager.list_user_instances(UUID(current_user["id"]))
        
        instance_responses = [
            InstanceStatusResponse(
                instance_id=str(inst.id),
                challenge_id=str(inst.challenge_id),
                user_id=str(inst.user_id),
                status=inst.status.value,
                sandbox_type=inst.sandbox_type.value,
                access_url=inst.access_url,
                connection_string=inst.connection_string,
                created_at=inst.created_at.isoformat(),
                started_at=inst.started_at.isoformat() if inst.started_at else None,
                expires_at=inst.expires_at.isoformat() if inst.expires_at else None,
                health_check_failures=inst.health_check_failures,
            )
            for inst in instances
        ]
        
        return InstanceListResponse(
            instances=instance_responses,
            total=len(instance_responses),
        )
        
    except Exception as e:
        logger.exception("Error listing instances", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list instances: {str(e)}",
        )


@router.post(
    "/extend/{instance_id}",
    response_model=ExtendTimeoutResponse,
    summary="Extend Instance Timeout",
    description="Extend the timeout of an active challenge instance",
)
async def extend_timeout(
    instance_id: UUID,
    body: ExtendTimeoutRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    manager: Annotated[ChallengeManager, Depends(get_challenge_manager)],
) -> ExtendTimeoutResponse:
    """Extend the timeout of an active instance."""
    try:
        # Verify ownership
        instance = await manager.get_status(instance_id)
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Instance not found",
            )
        
        if str(instance.user_id) != current_user["id"] and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        
        success = await manager.extend_timeout(instance_id, body.additional_seconds)
        
        if not success:
            return ExtendTimeoutResponse(
                success=False,
                error_message="Failed to extend timeout - instance may not be active",
            )
        
        # Get updated instance
        updated = await manager.get_status(instance_id)
        
        return ExtendTimeoutResponse(
            success=True,
            new_expires_at=updated.expires_at.isoformat() if updated.expires_at else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error extending timeout", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend timeout: {str(e)}",
        )


@router.delete(
    "/destroy/{instance_id}",
    response_model=DestroyResponse,
    summary="Destroy Instance",
    description="Destroy a challenge instance and cleanup resources",
)
async def destroy_instance(
    instance_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    manager: Annotated[ChallengeManager, Depends(get_challenge_manager)],
) -> DestroyResponse:
    """Destroy a challenge instance."""
    try:
        # Verify ownership
        instance = await manager.get_status(instance_id)
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Instance not found",
            )
        
        if str(instance.user_id) != current_user["id"] and not current_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        
        logger.info(
            "Destroying instance",
            instance_id=str(instance_id),
            user_id=current_user["id"],
        )
        
        success = await manager.destroy(instance_id)
        
        if success:
            return DestroyResponse(
                success=True,
                message="Instance destroyed successfully",
            )
        else:
            return DestroyResponse(
                success=False,
                message="Failed to destroy instance",
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error destroying instance", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to destroy instance: {str(e)}",
        )


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@router.websocket("/logs/{instance_id}")
async def stream_logs(
    websocket: WebSocket,
    instance_id: UUID,
    token: str,
):
    """
    WebSocket endpoint for streaming instance logs.
    
    Args:
        websocket: WebSocket connection
        instance_id: Instance ID to stream logs from
        token: Authentication token (passed as query parameter)
    """
    await websocket.accept()
    
    try:
        # TODO: Validate token and permissions
        # TODO: Get appropriate sandbox provider
        # TODO: Stream logs
        
        while True:
            # Keep connection alive
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info(
            "Log stream disconnected",
            instance_id=str(instance_id),
        )
    except Exception as e:
        logger.error(
            "Log stream error",
            instance_id=str(instance_id),
            error=str(e),
        )
        await websocket.close(code=1011)


@router.websocket("/status/{instance_id}/ws")
async def stream_status(
    websocket: WebSocket,
    instance_id: UUID,
    token: str,
):
    """
    WebSocket endpoint for streaming instance status updates.
    
    Args:
        websocket: WebSocket connection
        instance_id: Instance ID to monitor
        token: Authentication token
    """
    await websocket.accept()
    
    try:
        # TODO: Validate token
        # TODO: Stream status updates
        
        while True:
            await asyncio.sleep(5)
            # Send status update
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(
            "Status stream error",
            instance_id=str(instance_id),
            error=str(e),
        )
        await websocket.close(code=1011)