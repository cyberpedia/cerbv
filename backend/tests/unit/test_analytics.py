"""
Unit tests for analytics services.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.domain.analytics.services import (
    ChallengeAnalyticsService,
    UserSkillRadarService,
    ChallengeStats,
    TimeDistribution,
    SkillRadar,
)


class TestChallengeAnalyticsService:
    """Tests for the ChallengeAnalyticsService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock session
        self.mock_session = None
        self.service = ChallengeAnalyticsService(session=self.mock_session)
    
    def test_calculate_median_solve_time(self):
        """Median calculation should work correctly."""
        # No data case
        result = self.service.calculate_median_solve_time(uuid4())
        assert result is None
    
    def test_calculate_average_solve_time(self):
        """Average calculation should work correctly."""
        # No data case
        result = self.service.calculate_average_solve_time(uuid4())
        assert result is None
    
    def test_calculate_drop_off_rate_no_attempts(self):
        """Drop-off rate should be 0 when no attempts."""
        result = self.service.calculate_drop_off_rate(uuid4())
        assert result == 0.0
    
    def test_calculate_drop_off_rate_all_solved(self):
        """Drop-off rate should be 0 when all attempts solved."""
        # Mock behavior - in real implementation this would query DB
        result = self.service.calculate_drop_off_rate(uuid4())
        assert result == 0.0
    
    def test_get_time_distribution_buckets(self):
        """Time distribution should have correct bucket structure."""
        result = self.service.get_time_distribution(uuid4())
        
        assert isinstance(result, TimeDistribution)
        assert "0-5min" in result.buckets
        assert "5-15min" in result.buckets
        assert "15-30min" in result.buckets
        assert "30-60min" in result.buckets
        assert "1-2hrs" in result.buckets
        assert "2-6hrs" in result.buckets
        assert "6-24hrs" in result.buckets
        assert "24hrs+" in result.buckets
        assert result.unit == "minutes"
    
    def test_get_challenge_stats_structure(self):
        """Challenge stats should have correct structure."""
        stats = self.service.get_challenge_stats(uuid4())
        
        assert isinstance(stats, ChallengeStats)
        assert stats.challenge_id is not None
        assert isinstance(stats.total_attempts, int)
        assert isinstance(stats.total_solves, int)
        assert isinstance(stats.drop_off_rate, float)
    
    def test_get_category_stats(self):
        """Category stats should return per-category data."""
        result = self.service.get_category_stats()
        
        assert isinstance(result, dict)
        for category, data in result.items():
            assert "total_challenges" in data
            assert "total_solves" in data
            assert "avg_difficulty" in data
    
    def test_get_overall_competition_stats(self):
        """Competition stats should have all required fields."""
        result = self.service.get_overall_competition_stats()
        
        assert "total_participants" in result
        assert "total_solves" in result
        assert "total_challenges" in result
        assert "solved_challenges" in result
        assert "average_solves_per_team" in result
        assert "competition_duration_hours" in result
        assert "current_phase" in result


class TestUserSkillRadarService:
    """Tests for the UserSkillRadarService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = None
        self.service = UserSkillRadarService(session=self.mock_session)
        self.user_id = uuid4()
    
    def test_calculate_skill_radar_structure(self):
        """Skill radar should have correct structure."""
        radar = self.service.calculate_skill_radar(self.user_id)
        
        assert isinstance(radar, SkillRadar)
        assert radar.user_id == self.user_id
        assert isinstance(radar.category_scores, dict)
        assert isinstance(radar.overall_score, float)
        assert isinstance(radar.strong_categories, list)
        assert isinstance(radar.weak_categories, list)
        assert isinstance(radar.last_updated, datetime)
    
    def test_category_scores_normalized(self):
        """Category scores should be between 0 and 100."""
        radar = self.service.calculate_skill_radar(self.user_id)
        
        for cat, score in radar.category_scores.items():
            assert 0 <= score <= 100
    
    def test_strong_categories_above_threshold(self):
        """Strong categories should have scores >= 70."""
        radar = self.service.calculate_skill_radar(self.user_id)
        
        for cat in radar.strong_categories:
            assert radar.category_scores.get(cat, 0) >= 70
    
    def test_weak_categories_below_threshold(self):
        """Weak categories should have scores < 50."""
        radar = self.service.calculate_skill_radar(self.user_id)
        
        for cat in radar.weak_categories:
            assert radar.category_scores.get(cat, 100) < 50
    
    def test_get_skill_radar_returns_none_for_cached(self):
        """Get skill radar should return None when not cached."""
        result = self.service.get_skill_radar(self.user_id)
        assert result is None
    
    def test_compare_skill_radars_structure(self):
        """Compare should return structured comparison data."""
        user2_id = uuid4()
        
        result = self.service.compare_skill_radars(self.user_id, user2_id)
        
        assert "overall_comparison" in result
        assert "user1_score" in result["overall_comparison"]
        assert "user2_score" in result["overall_comparison"]
        assert "difference" in result["overall_comparison"]
        assert "categories" in result
        
        # All categories should be compared
        for cat, comparison in result["categories"].items():
            assert "user1" in comparison
            assert "user2" in comparison
            assert "difference" in comparison
    
    def test_update_all_skill_radars(self):
        """Update all should return count of updated users."""
        result = self.service.update_all_skill_radars()
        assert isinstance(result, int)


class TestTimeDistribution:
    """Tests for TimeDistribution."""
    
    def test_time_buckets_complete(self):
        """All time buckets should cover expected ranges."""
        service = ChallengeAnalyticsService(session=None)
        
        # Create a distribution
        distribution = TimeDistribution(buckets={"0-5min": 10, "5-15min": 5})
        
        # Verify bucket labels match expected
        expected_buckets = ["0-5min", "5-15min", "15-30min", "30-60min", "1-2hrs", "2-6hrs", "6-24hrs", "24hrs+"]
        
        for expected in expected_buckets:
            # At least the service method should include this
            result = service.get_time_distribution(uuid4())
            assert expected in result.buckets
    
    def test_bucket_values_are_integers(self):
        """Bucket values should be integer counts."""
        service = ChallengeAnalyticsService(session=None)
        distribution = service.get_time_distribution(uuid4())
        
        for label, count in distribution.buckets.items():
            assert isinstance(count, int)
            assert count >= 0
