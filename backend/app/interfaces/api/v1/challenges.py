"""
Cerberus CTF Platform - Challenge Endpoints
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.interfaces.api.v1.auth import get_current_user, require_admin

router = APIRouter()


class ChallengeResponse(BaseModel):
    """Challenge response model."""
    id: str
    title: str
    slug: str
    description: str
    category: str
    difficulty: str
    points: int
    solve_count: int
    hints: list[dict]
    file_urls: list[str]
    is_solved: bool = False


class ChallengeListResponse(BaseModel):
    """Paginated challenge list."""
    challenges: list[ChallengeResponse]
    cursor: str | None
    has_more: bool


class ChallengeCreateRequest(BaseModel):
    """Challenge creation request."""
    title: str = Field(min_length=1, max_length=200)
    description: str
    category_id: UUID
    difficulty: str
    points: int = Field(ge=1)
    flag: str
    flag_case_sensitive: bool = True
    hints: list[dict] = Field(default_factory=list)
    file_urls: list[str] = Field(default_factory=list)
    prerequisites: list[UUID] = Field(default_factory=list)


class ChallengeUpdateRequest(BaseModel):
    """Challenge update request."""
    title: str | None = None
    description: str | None = None
    points: int | None = None
    is_visible: bool | None = None


@router.get(
    "",
    response_model=ChallengeListResponse,
    summary="List Challenges",
)
async def list_challenges(
    current_user: Annotated[dict, Depends(get_current_user)],
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ChallengeListResponse:
    """List available challenges."""
    # Placeholder implementation
    return ChallengeListResponse(
        challenges=[],
        cursor=None,
        has_more=False,
    )


@router.get(
    "/{challenge_id}",
    response_model=ChallengeResponse,
    summary="Get Challenge",
)
async def get_challenge(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ChallengeResponse:
    """Get challenge details."""
    # Placeholder implementation
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Challenge not found",
    )


@router.post(
    "",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Challenge",
)
async def create_challenge(
    body: ChallengeCreateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
) -> ChallengeResponse:
    """Create a new challenge (admin only)."""
    # Placeholder implementation
    return ChallengeResponse(
        id="new-challenge-id",
        title=body.title,
        slug="new-challenge",
        description=body.description,
        category="misc",
        difficulty=body.difficulty,
        points=body.points,
        solve_count=0,
        hints=[],
        file_urls=body.file_urls,
    )


@router.patch(
    "/{challenge_id}",
    response_model=ChallengeResponse,
    summary="Update Challenge",
)
async def update_challenge(
    challenge_id: UUID,
    body: ChallengeUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
) -> ChallengeResponse:
    """Update challenge (admin only)."""
    # Placeholder implementation
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Challenge not found",
    )


@router.delete(
    "/{challenge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Challenge",
)
async def delete_challenge(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(require_admin)],
) -> None:
    """Delete challenge (admin only)."""
    pass


@router.post(
    "/{challenge_id}/hints/{hint_index}/reveal",
    summary="Reveal Hint",
)
async def reveal_hint(
    challenge_id: UUID,
    hint_index: int,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Reveal a hint (may cost points)."""
    # Placeholder implementation
    return {"hint": "Revealed hint content", "cost": 10}
