"""
Cerberus CTF Platform - Hint System Application Service
Advanced hint management with progressive unlocks and point deductions
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import structlog

from app.domain.mcq.entities import (
    DeductionType,
    Hint,
    HintConfig,
    UnlockMode,
    UserHint,
)

logger = structlog.get_logger(__name__)


@dataclass
class HintUnlockResult:
    """Result of hint unlock operation."""
    success: bool
    hint: Optional[Hint] = None
    user_hint: Optional[UserHint] = None
    points_deducted: Decimal = field(default_factory=lambda: Decimal("0"))
    message: str = ""
    conditions_not_met: List[str] = field(default_factory=list)


@dataclass
class AvailableHint:
    """Hint with unlock status for user."""
    hint: Hint
    is_unlocked: bool
    can_unlock: bool
    cost: Decimal
    conditions_not_met: List[str]
    unlocked_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.hint.id),
            "title": self.hint.title,
            "sequence_order": self.hint.sequence_order,
            "is_unlocked": self.is_unlocked,
            "can_unlock": self.can_unlock,
            "cost": float(self.cost),
            "conditions_not_met": self.conditions_not_met,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "preview": self.hint.get_preview() if not self.is_unlocked else None,
            "content_type": self.hint.content_type,
            "attachment_url": self.hint.attachment_url if self.is_unlocked else None,
        }


class HintService:
    """
    Service for managing the hint system.
    
    Handles hint unlocks with various strategies (timed, progressive,
    attempt-based), point deductions, and transaction safety.
    """
    
    def __init__(self, db_session, cache_client=None):
        """
        Initialize hint service.
        
        Args:
            db_session: Database session for persistence
            cache_client: Optional cache client for cooldown tracking
        """
        self._db = db_session
        self._cache = cache_client
    
    async def get_hint_config(self, challenge_id: UUID) -> Optional[HintConfig]:
        """Get hint configuration for a challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_hints_for_challenge(self, challenge_id: UUID) -> List[Hint]:
        """Get all hints for a challenge ordered by sequence."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_user_hints(
        self, user_id: UUID, challenge_id: UUID
    ) -> List[UserHint]:
        """Get hints unlocked by user for a challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_user_attempt_count(self, user_id: UUID, challenge_id: UUID) -> int:
        """Get number of attempts user has made on challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_challenge_start_time(
        self, user_id: UUID, challenge_id: UUID
    ) -> Optional[datetime]:
        """Get when user started the challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def is_challenge_solved(self, user_id: UUID, challenge_id: UUID) -> bool:
        """Check if user has already solved the challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_challenge_points(self, challenge_id: UUID) -> Decimal:
        """Get points value of the challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def deduct_user_points(
        self, user_id: UUID, points: Decimal, reason: str
    ) -> bool:
        """Deduct points from user. Returns success status."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def save_user_hint(self, user_hint: UserHint) -> None:
        """Save user hint unlock record."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_hint_by_id(self, hint_id: UUID) -> Optional[Hint]:
        """Get hint by ID."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def is_hint_unlocked(self, user_id: UUID, hint_id: UUID) -> bool:
        """Check if user has already unlocked this hint."""
        user_hints = await self._get_user_hints_by_hint(user_id, hint_id)
        return len(user_hints) > 0
    
    async def _get_user_hints_by_hint(
        self, user_id: UUID, hint_id: UUID
    ) -> List[UserHint]:
        """Get user hint records for specific hint."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def get_available_hints(
        self,
        challenge_id: UUID,
        user_id: UUID,
    ) -> List[AvailableHint]:
        """
        Get all hints for challenge with unlock status for user.
        
        Args:
            challenge_id: The challenge ID
            user_id: User requesting hints
            
        Returns:
            List of hints with unlock status and costs
        """
        config = await self.get_hint_config(challenge_id)
        
        if not config or not config.enabled:
            return []
        
        hints = await self.get_hints_for_challenge(challenge_id)
        user_hints = await self.get_user_hints(user_id, challenge_id)
        attempts_count = await self.get_user_attempt_count(user_id, challenge_id)
        challenge_start = await self.get_challenge_start_time(user_id, challenge_id)
        challenge_points = await self.get_challenge_points(challenge_id)
        
        result = []
        unlocked_hints = {uh.hint_id for uh in user_hints}
        
        for hint in hints:
            # Check if already unlocked
            is_unlocked = hint.id in unlocked_hints
            
            # Calculate cost
            if hint.custom_cost is not None:
                cost = hint.custom_cost
            else:
                cost = config.calculate_deduction(challenge_points)
            
            # Check unlock conditions
            can_unlock = True
            conditions_not_met = []
            
            if not is_unlocked:
                can_unlock, conditions_not_met = hint.is_unlocked(
                    user_hints, attempts_count, challenge_start
                )
            
            # Find unlock time if already unlocked
            unlocked_at = None
            for uh in user_hints:
                if uh.hint_id == hint.id:
                    unlocked_at = uh.unlocked_at
                    break
            
            result.append(AvailableHint(
                hint=hint,
                is_unlocked=is_unlocked,
                can_unlock=can_unlock,
                cost=cost,
                conditions_not_met=conditions_not_met,
                unlocked_at=unlocked_at
            ))
        
        # Apply max hints visible limit
        if config.max_hints_visible:
            visible_count = sum(1 for h in result if h.is_unlocked or h.can_unlock)
            if visible_count > config.max_hints_visible:
                # Hide hints beyond the limit
                result = result[:config.max_hints_visible]
        
        return result
    
    async def unlock_hint(
        self,
        hint_id: UUID,
        user_id: UUID,
    ) -> HintUnlockResult:
        """
        Unlock a hint for a user.
        
        Args:
            hint_id: The hint to unlock
            user_id: User unlocking the hint
            
        Returns:
            HintUnlockResult with success status and hint content
        """
        # Get hint
        hint = await self.get_hint_by_id(hint_id)
        if not hint:
            return HintUnlockResult(
                success=False,
                message="Hint not found"
            )
        
        challenge_id = hint.challenge_id
        
        # Check if already unlocked (idempotent)
        if await self.is_hint_unlocked(user_id, hint_id):
            user_hint = await self._get_user_hint_record(user_id, hint_id)
            return HintUnlockResult(
                success=True,
                hint=hint,
                user_hint=user_hint,
                points_deducted=user_hint.points_deducted if user_hint else Decimal("0"),
                message="Hint already unlocked"
            )
        
        # Check if challenge is already solved
        if await self.is_challenge_solved(user_id, challenge_id):
            return HintUnlockResult(
                success=False,
                message="Cannot unlock hints after solving the challenge"
            )
        
        # Get config
        config = await self.get_hint_config(challenge_id)
        if not config or not config.enabled:
            return HintUnlockResult(
                success=False,
                message="Hint system is disabled for this challenge"
            )
        
        # Check cooldown
        if await self._is_on_cooldown(user_id, challenge_id, config.cooldown_seconds):
            return HintUnlockResult(
                success=False,
                message="Please wait before unlocking another hint"
            )
        
        # Check unlock conditions
        user_hints = await self.get_user_hints(user_id, challenge_id)
        attempts_count = await self.get_user_attempt_count(user_id, challenge_id)
        challenge_start = await self.get_challenge_start_time(user_id, challenge_id)
        
        can_unlock, conditions_not_met = hint.is_unlocked(
            user_hints, attempts_count, challenge_start
        )
        
        if not can_unlock:
            return HintUnlockResult(
                success=False,
                hint=hint,
                conditions_not_met=conditions_not_met,
                message="Hint unlock conditions not met"
            )
        
        # Calculate deduction
        challenge_points = await self.get_challenge_points(challenge_id)
        if hint.custom_cost is not None:
            points_to_deduct = hint.custom_cost
        else:
            points_to_deduct = config.calculate_deduction(challenge_points)
        
        # Check progressive chain
        if config.progressive_chain and hint.unlock_after_hint_id:
            prev_unlocked = any(
                uh.hint_id == hint.unlock_after_hint_id for uh in user_hints
            )
            if not prev_unlocked:
                return HintUnlockResult(
                    success=False,
                    message="You must unlock the previous hint first"
                )
        
        # Calculate time into challenge
        time_into_challenge = None
        if challenge_start:
            time_into_challenge = datetime.utcnow() - challenge_start
        
        # Create user hint record
        user_hint = UserHint(
            user_id=user_id,
            hint_id=hint_id,
            challenge_id=challenge_id,
            points_deducted=points_to_deduct,
            time_into_challenge=time_into_challenge,
            attempt_number_when_used=attempts_count
        )
        
        # Deduct points and save in transaction
        try:
            if points_to_deduct > 0:
                success = await self.deduct_user_points(
                    user_id, points_to_deduct, f"Hint unlock: {hint.title or hint_id}"
                )
                if not success:
                    return HintUnlockResult(
                        success=False,
                        message="Insufficient points to unlock hint"
                    )
            
            await self.save_user_hint(user_hint)
            await self._set_cooldown(user_id, challenge_id, config.cooldown_seconds)
            
            logger.info(
                "Hint unlocked",
                user_id=str(user_id),
                hint_id=str(hint_id),
                challenge_id=str(challenge_id),
                points_deducted=float(points_to_deduct)
            )
            
            return HintUnlockResult(
                success=True,
                hint=hint,
                user_hint=user_hint,
                points_deducted=points_to_deduct,
                message="Hint unlocked successfully"
            )
            
        except Exception as e:
            logger.error(
                "Failed to unlock hint",
                user_id=str(user_id),
                hint_id=str(hint_id),
                error=str(e)
            )
            return HintUnlockResult(
                success=False,
                message="An error occurred while unlocking the hint"
            )
    
    async def get_hint_preview(
        self,
        hint_id: UUID,
        user_id: UUID,
        preview_length: int = 100
    ) -> Dict[str, Any]:
        """
        Get truncated preview of hint content.
        
        Args:
            hint_id: The hint ID
            user_id: User requesting preview
            preview_length: Length of preview text
            
        Returns:
            Preview data including truncated content
        """
        hint = await self.get_hint_by_id(hint_id)
        if not hint:
            return {"error": "Hint not found"}
        
        is_unlocked = await self.is_hint_unlocked(user_id, hint_id)
        
        return {
            "id": str(hint_id),
            "title": hint.title,
            "preview": hint.get_preview(preview_length),
            "content_type": hint.content_type,
            "is_unlocked": is_unlocked,
            "sequence_order": hint.sequence_order,
        }
    
    async def check_progressive_chain(
        self,
        challenge_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Check progressive chain status for hints.
        
        Returns which hints in the chain are unlocked and which are next.
        """
        hints = await self.get_hints_for_challenge(challenge_id)
        user_hints = await self.get_user_hints(user_id, challenge_id)
        unlocked_ids = {uh.hint_id for uh in user_hints}
        
        # Sort by sequence order
        sorted_hints = sorted(hints, key=lambda h: h.sequence_order)
        
        chain_status = []
        next_unlock = None
        
        for hint in sorted_hints:
            is_unlocked = hint.id in unlocked_ids
            
            status = {
                "hint_id": str(hint.id),
                "title": hint.title,
                "sequence_order": hint.sequence_order,
                "is_unlocked": is_unlocked,
            }
            
            # Check if this is the next hint to unlock
            if not is_unlocked and next_unlock is None:
                # Check if previous hint is unlocked
                if hint.unlock_after_hint_id:
                    prev_unlocked = hint.unlock_after_hint_id in unlocked_ids
                    if prev_unlocked:
                        next_unlock = hint.id
                        status["is_next"] = True
                else:
                    next_unlock = hint.id
                    status["is_next"] = True
            
            chain_status.append(status)
        
        return {
            "challenge_id": str(challenge_id),
            "chain_status": chain_status,
            "next_unlock_id": str(next_unlock) if next_unlock else None,
            "completed": all(s["is_unlocked"] for s in chain_status)
        }
    
    async def _get_user_hint_record(
        self, user_id: UUID, hint_id: UUID
    ) -> Optional[UserHint]:
        """Get user hint record for specific hint."""
        user_hints = await self._get_user_hints_by_hint(user_id, hint_id)
        return user_hints[0] if user_hints else None
    
    async def _is_on_cooldown(
        self, user_id: UUID, challenge_id: UUID, cooldown_seconds: int
    ) -> bool:
        """Check if user is on cooldown for hint unlocks."""
        if cooldown_seconds <= 0 or not self._cache:
            return False
        
        key = f"hint_cooldown:{user_id}:{challenge_id}"
        # This would check cache for cooldown
        return False
    
    async def _set_cooldown(
        self, user_id: UUID, challenge_id: UUID, cooldown_seconds: int
    ) -> None:
        """Set cooldown for user after hint unlock."""
        if cooldown_seconds <= 0 or not self._cache:
            return
        
        key = f"hint_cooldown:{user_id}:{challenge_id}"
        # This would set cache with TTL
        pass