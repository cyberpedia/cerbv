"""
Unit tests for Hint System domain entities.

Tests:
- Progressive hint unlocking sequence
- Unlock condition checking (timed, attempt-based, manual)
- Point deduction calculations
- Hint preview generation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.mcq.entities import (
    Hint,
    HintConfig,
    UserHint,
    UnlockMode,
    DeductionType,
)


class TestHintUnlockConditions:
    """Test hint unlock condition checking."""
    
    def test_manual_unlock_always_available(self):
        """Test that manual hints are always available to unlock."""
        hint = Hint(
            title="Test Hint",
            content="Hint content",
            unlock_after_minutes=None,
            unlock_after_attempts=None,
            unlock_after_hint_id=None,
        )
        
        can_unlock, conditions = hint.is_unlocked([], attempts_count=0)
        
        assert can_unlock is True
        assert len(conditions) == 0
    
    def test_already_unlocked(self, user_hint_unlocked):
        """Test that already unlocked hints return True."""
        hint = Hint(
            id=user_hint_unlocked.hint_id,
            title="Test Hint",
            content="Hint content",
        )
        
        can_unlock, conditions = hint.is_unlocked([user_hint_unlocked], attempts_count=0)
        
        assert can_unlock is True
        assert len(conditions) == 0
    
    def test_attempt_based_unlock_met(self, attempt_based_hint):
        """Test attempt-based unlock when condition met."""
        can_unlock, conditions = attempt_based_hint.is_unlocked(
            [], attempts_count=3
        )
        
        assert can_unlock is True
        assert len(conditions) == 0
    
    def test_attempt_based_unlock_not_met(self, attempt_based_hint):
        """Test attempt-based unlock when condition not met."""
        can_unlock, conditions = attempt_based_hint.is_unlocked(
            [], attempts_count=2
        )
        
        assert can_unlock is False
        assert len(conditions) == 1
        assert "3 attempts" in conditions[0]
    
    def test_timed_unlock_met(self, timed_hint):
        """Test timed unlock when enough time has passed."""
        start_time = datetime.utcnow() - timedelta(minutes=15)
        
        can_unlock, conditions = timed_hint.is_unlocked(
            [], attempts_count=0, challenge_start_time=start_time
        )
        
        assert can_unlock is True
        assert len(conditions) == 0
    
    def test_timed_unlock_not_met(self, timed_hint):
        """Test timed unlock when not enough time has passed."""
        start_time = datetime.utcnow() - timedelta(minutes=5)
        
        can_unlock, conditions = timed_hint.is_unlocked(
            [], attempts_count=0, challenge_start_time=start_time
        )
        
        assert can_unlock is False
        assert len(conditions) == 1
        assert "minutes" in conditions[0]
    
    def test_progressive_chain_unlock_met(self, progressive_hints):
        """Test progressive chain when previous hint unlocked."""
        hint2 = progressive_hints[1]  # Requires hint1
        hint1_unlocked = UserHint(hint_id=progressive_hints[0].id)
        
        can_unlock, conditions = hint2.is_unlocked(
            [hint1_unlocked], attempts_count=0
        )
        
        assert can_unlock is True
        assert len(conditions) == 0
    
    def test_progressive_chain_unlock_not_met(self, progressive_hints):
        """Test progressive chain when previous hint not unlocked."""
        hint2 = progressive_hints[1]  # Requires hint1
        
        can_unlock, conditions = hint2.is_unlocked(
            [], attempts_count=0
        )
        
        assert can_unlock is False
        assert len(conditions) == 1
        assert "Previous hint" in conditions[0]
    
    def test_multiple_conditions(self, progressive_hints):
        """Test hint with multiple unlock conditions."""
        hint3 = progressive_hints[2]  # Requires hint2 AND 2 attempts
        hint2_unlocked = UserHint(hint_id=progressive_hints[1].id)
        
        # Have hint2 but not enough attempts
        can_unlock, conditions = hint3.is_unlocked(
            [hint2_unlocked], attempts_count=1
        )
        
        assert can_unlock is False
        assert len(conditions) == 1
        assert "2 attempts" in conditions[0]


class TestHintConfig:
    """Test hint configuration."""
    
    def test_points_deduction_calculation(self):
        """Test fixed points deduction."""
        config = HintConfig(
            deduction_type=DeductionType.POINTS,
            deduction_value=Decimal("10.00"),
        )
        
        deduction = config.calculate_deduction(challenge_points=Decimal("100"))
        
        assert deduction == Decimal("10.00")
    
    def test_percentage_deduction_calculation(self):
        """Test percentage-based deduction."""
        config = HintConfig(
            deduction_type=DeductionType.PERCENTAGE,
            deduction_value=Decimal("10.00"),  # 10%
        )
        
        deduction = config.calculate_deduction(challenge_points=Decimal("100"))
        
        assert deduction == Decimal("10.00")  # 10% of 100
    
    def test_time_penalty_no_point_deduction(self):
        """Test time penalty doesn't deduct points."""
        config = HintConfig(
            deduction_type=DeductionType.TIME_PENALTY,
            deduction_value=Decimal("300"),  # 5 minutes
        )
        
        deduction = config.calculate_deduction(challenge_points=Decimal("100"))
        
        assert deduction == Decimal("0")
    
    def test_config_serialization(self):
        """Test config to_dict serialization."""
        config = HintConfig(
            enabled=True,
            unlock_mode=UnlockMode.PROGRESSIVE,
            deduction_type=DeductionType.POINTS,
            deduction_value=Decimal("15.00"),
            max_hints_visible=5,
            cooldown_seconds=60,
        )
        
        result = config.to_dict()
        
        assert result["enabled"] is True
        assert result["unlock_mode"] == "progressive"
        assert result["deduction_type"] == "points"
        assert result["deduction_value"] == 15.0
        assert result["max_hints_visible"] == 5
        assert result["cooldown_seconds"] == 60


class TestHintPreview:
    """Test hint preview generation."""
    
    def test_preview_short_content(self):
        """Test preview of short content (no truncation)."""
        hint = Hint(
            title="Test",
            content="Short content",
        )
        
        preview = hint.get_preview(length=100)
        
        assert preview == "Short content"
    
    def test_preview_long_content(self):
        """Test preview truncation."""
        hint = Hint(
            title="Test",
            content="A" * 200,
        )
        
        preview = hint.get_preview(length=50)
        
        assert len(preview) == 53  # 50 + "..."
        assert preview.endswith("...")
    
    def test_preview_exact_length(self):
        """Test preview at exact length boundary."""
        hint = Hint(
            title="Test",
            content="A" * 100,
        )
        
        preview = hint.get_preview(length=100)
        
        # Exact length should not be truncated
        assert preview == "A" * 100


class TestHintSerialization:
    """Test hint serialization."""
    
    def test_to_dict_without_content(self):
        """Test serialization without content (preview mode)."""
        hint = Hint(
            id=uuid4(),
            title="Secret Hint",
            content="This is the secret content",
            content_type="text",
            sequence_order=1,
            unlock_after_minutes=10,
            custom_cost=Decimal("20.00"),
        )
        
        result = hint.to_dict(include_content=False)
        
        assert "content" not in result
        assert result["preview"] == hint.get_preview()
        assert result["title"] == "Secret Hint"
        assert result["sequence_order"] == 1
        assert result["unlock_after_minutes"] == 10
        assert result["custom_cost"] == 20.0
    
    def test_to_dict_with_content(self):
        """Test serialization with content (unlocked)."""
        hint = Hint(
            id=uuid4(),
            title="Secret Hint",
            content="This is the secret content",
            content_type="text",
            attachment_url="https://example.com/hint.png",
        )
        
        result = hint.to_dict(include_content=True)
        
        assert result["content"] == "This is the secret content"
        assert result["attachment_url"] == "https://example.com/hint.png"
        assert "preview" not in result


class TestUserHint:
    """Test UserHint tracking."""
    
    def test_user_hint_creation(self):
        """Test user hint record creation."""
        user_hint = UserHint(
            user_id=uuid4(),
            hint_id=uuid4(),
            challenge_id=uuid4(),
            points_deducted=Decimal("10.00"),
            time_into_challenge=timedelta(minutes=5),
            attempt_number_when_used=2,
        )
        
        assert user_hint.points_deducted == Decimal("10.00")
        assert user_hint.time_into_challenge == timedelta(minutes=5)
        assert user_hint.attempt_number_when_used == 2
        assert user_hint.unlocked_at is not None
    
    def test_user_hint_to_dict(self):
        """Test user hint serialization."""
        user_hint = UserHint(
            hint_id=uuid4(),
            points_deducted=Decimal("15.00"),
            time_into_challenge=timedelta(minutes=10, seconds=30),
            attempt_number_when_used=3,
        )
        
        result = user_hint.to_dict()
        
        assert "hint_id" in result
        assert result["points_deducted"] == 15.0
        assert result["time_into_challenge"] == "0:10:30"
        assert result["attempt_number_when_used"] == 3
        assert "unlocked_at" in result
    
    def test_user_hint_none_time(self):
        """Test user hint with no time tracked."""
        user_hint = UserHint(
            hint_id=uuid4(),
            points_deducted=Decimal("10.00"),
            time_into_challenge=None,
        )
        
        result = user_hint.to_dict()
        
        assert result["time_into_challenge"] is None


class TestProgressiveHintChain:
    """Test progressive hint chain behavior."""
    
    def test_full_chain_unlocking(self, progressive_hints):
        """Test unlocking full progressive chain."""
        hint1, hint2, hint3 = progressive_hints
        
        # Initially none unlocked
        assert hint1.is_unlocked([], 0)[0] is True  # First hint always available
        assert hint2.is_unlocked([], 0)[0] is False  # Needs hint1
        assert hint3.is_unlocked([], 0)[0] is False  # Needs hint2
        
        # Unlock hint1
        unlocked1 = UserHint(hint_id=hint1.id)
        assert hint2.is_unlocked([unlocked1], 0)[0] is True
        assert hint3.is_unlocked([unlocked1], 0)[0] is False  # Still needs hint2
        
        # Unlock hint2
        unlocked2 = UserHint(hint_id=hint2.id)
        # Still need 2 attempts for hint3
        assert hint3.is_unlocked([unlocked1, unlocked2], 1)[0] is False
        assert hint3.is_unlocked([unlocked1, unlocked2], 2)[0] is True
    
    def test_chain_skip_attempt_fails(self, progressive_hints):
        """Test that chain cannot be skipped."""
        hint1, hint2, hint3 = progressive_hints
        
        # Try to get hint3 without hint1 or hint2
        user_hints = []
        can_unlock, conditions = hint3.is_unlocked(user_hints, attempts_count=5)
        
        assert can_unlock is False
        # Should fail due to missing hint2
        assert any("Previous hint" in c for c in conditions)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_no_challenge_start_time_for_timed_hint(self, timed_hint):
        """Test timed hint without challenge start time."""
        # Without start time, timed unlocks are treated as available
        can_unlock, conditions = timed_hint.is_unlocked(
            [], attempts_count=0, challenge_start_time=None
        )
        
        # Should be available since we can't verify timing
        assert can_unlock is True
    
    def test_zero_attempts_for_attempt_based(self, attempt_based_hint):
        """Test attempt-based hint with zero attempts."""
        can_unlock, conditions = attempt_based_hint.is_unlocked(
            [], attempts_count=0
        )
        
        assert can_unlock is False
        assert "3 attempts" in conditions[0]
    
    def test_negative_custom_cost(self):
        """Test hint with negative custom cost (should be handled)."""
        # Note: In real implementation, validation would prevent this
        hint = Hint(
            title="Test",
            content="Content",
            custom_cost=Decimal("-5.00"),
        )
        
        # The cost should still be stored
        assert hint.custom_cost == Decimal("-5.00")
        # But deduction logic should handle it appropriately
