"""
Analytics service for challenge metrics and user skill tracking.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from collections import defaultdict
import statistics


@dataclass
class ChallengeStats:
    """Statistics for a single challenge."""
    challenge_id: UUID
    challenge_name: str
    total_attempts: int
    total_solves: int
    average_solve_time_seconds: Optional[float]
    median_solve_time_seconds: Optional[float]
    drop_off_rate: float
    first_solve_time: Optional[datetime]
    last_solve_time: Optional[datetime]


@dataclass
class TimeDistribution:
    """Histogram distribution of solve times."""
    buckets: Dict[str, int]  # e.g., {"0-5min": 10, "5-10min": 5, ...}
    unit: str = "minutes"


@dataclass
class SkillRadar:
    """User skill profile by category."""
    user_id: UUID
    category_scores: Dict[str, float]  # Category -> normalized score 0-100
    overall_score: float
    strong_categories: List[str]
    weak_categories: List[str]
    last_updated: datetime


class ChallengeAnalyticsService:
    """
    Service for computing challenge analytics.
    All methods return aggregate statistics, never individual data.
    """
    
    # Time bucket definitions for histograms
    TIME_BUCKETS = [
        (0, 5, "0-5min"),
        (5, 15, "5-15min"),
        (15, 30, "15-30min"),
        (30, 60, "30-60min"),
        (60, 120, "1-2hrs"),
        (120, 360, "2-6hrs"),
        (360, 1440, "6-24hrs"),
        (1440, float("inf"), "24hrs+"),
    ]
    
    def __init__(self, session):
        self.session = session
    
    def get_challenge_stats(self, challenge_id: UUID) -> ChallengeStats:
        """
        Get comprehensive statistics for a challenge.
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            ChallengeStats with all metrics
        """
        # In real implementation: query database
        # solves = self.session.query(Solve).filter_by(challenge_id=challenge_id).all()
        # attempts = self.session.query(Submission).filter_by(challenge_id=challenge_id).all()
        
        # Placeholder return
        return ChallengeStats(
            challenge_id=challenge_id,
            challenge_name="Challenge",
            total_attempts=0,
            total_solves=0,
            average_solve_time_seconds=None,
            median_solve_time_seconds=None,
            drop_off_rate=0.0,
            first_solve_time=None,
            last_solve_time=None,
        )
    
    def get_all_challenge_stats(self) -> List[ChallengeStats]:
        """
        Get statistics for all challenges.
        
        Returns:
            List of ChallengeStats for all challenges
        """
        # In real implementation: query all challenges and compute stats
        return []
    
    def calculate_average_solve_time(self, challenge_id: UUID) -> Optional[float]:
        """
        Calculate average solve time for a challenge (outlier resistant).
        
        Uses trimmed mean (remove top/bottom 10%) for outlier resistance.
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            Average solve time in seconds, or None if no data
        """
        # In real implementation: get solve times from database
        solve_times = []  # List of solve times in seconds
        
        if len(solve_times) < 2:
            return None
        
        # Trim 10% from each end
        sorted_times = sorted(solve_times)
        trim_count = max(1, len(sorted_times) // 10)
        trimmed = sorted_times[trim_count:-trim_count] if trim_count > 0 else sorted_times
        
        if not trimmed:
            return None
        
        return statistics.mean(trimmed)
    
    def calculate_median_solve_time(self, challenge_id: UUID) -> Optional[float]:
        """
        Calculate median solve time (naturally outlier resistant).
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            Median solve time in seconds, or None if no data
        """
        # In real implementation: get solve times from database
        solve_times = []
        
        if not solve_times:
            return None
        
        return statistics.median(solve_times)
    
    def calculate_drop_off_rate(self, challenge_id: UUID) -> float:
        """
        Calculate the percentage of attempts that were never solved.
        
        drop_off = (attempts - solves) / attempts
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            Drop-off rate as percentage 0-100
        """
        # In real implementation: query database
        total_attempts = 100
        total_solves = 60
        
        if total_attempts == 0:
            return 0.0
        
        return ((total_attempts - total_solves) / total_attempts) * 100
    
    def get_time_distribution(self, challenge_id: UUID) -> TimeDistribution:
        """
        Get histogram of solve times (no individual data).
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            TimeDistribution with bucketed counts
        """
        # In real implementation: get solve times
        solve_times = []  # List of solve times in minutes
        
        buckets = {}
        for min_val, max_val, label in self.TIME_BUCKETS:
            count = sum(
                1 for t in solve_times 
                if (min_val <= t < max_val) or (min_val <= t and max_val == float("inf"))
            )
            buckets[label] = count
        
        return TimeDistribution(buckets=buckets)
    
    def get_category_stats(self) -> Dict[str, Any]:
        """
        Get statistics by challenge category.
        
        Returns:
            Dictionary with per-category stats
        """
        # In real implementation: aggregate by category
        return {
            "web": {"total_challenges": 10, "total_solves": 150, "avg_difficulty": 5.2},
            "pwn": {"total_challenges": 8, "total_solves": 80, "avg_difficulty": 6.1},
            "crypto": {"total_challenges": 12, "total_solves": 200, "avg_difficulty": 4.5},
            "reverse": {"total_challenges": 6, "total_solves": 40, "avg_difficulty": 7.0},
        }
    
    def get_overall_competition_stats(self) -> Dict[str, Any]:
        """
        Get overall competition statistics.
        
        Returns:
            Dictionary with competition-wide stats
        """
        return {
            "total_participants": 0,
            "total_solves": 0,
            "total_challenges": 0,
            "solved_challenges": 0,
            "average_solves_per_team": 0.0,
            "competition_duration_hours": 0.0,
            "current_phase": "not_started",
        }


class UserSkillRadarService:
    """
    Service for calculating and storing user skill profiles.
    Only stores derived metrics, never individual solve data.
    """
    
    # Category weights for scoring
    CATEGORY_WEIGHTS = {
        "web": 1.0,
        "pwn": 1.2,  # Typically harder
        "crypto": 1.1,
        "reverse": 1.1,
        "forensics": 0.9,
        "misc": 0.8,
        "osint": 0.7,
    }
    
    def __init__(self, session):
        self.session = session
    
    def calculate_skill_radar(self, user_id: UUID) -> SkillRadar:
        """
        Calculate skill profile for a user based on solve history.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            SkillRadar with category scores
        """
        # In real implementation: query user's solves with challenge categories
        category_scores = {
            "web": 75.5,
            "pwn": 45.0,
            "crypto": 88.0,
            "reverse": 30.0,
            "forensics": 60.0,
            "misc": 85.0,
            "osint": 70.0,
        }
        
        # Calculate overall score
        weighted_scores = []
        for cat, score in category_scores.items():
            weight = self.CATEGORY_WEIGHTS.get(cat, 1.0)
            weighted_scores.append(score * weight)
        
        overall = statistics.mean(weighted_scores) if weighted_scores else 0.0
        
        # Determine strong/weak categories
        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        strong = [c[0] for c in sorted_cats[:3] if c[1] >= 70]
        weak = [c[0] for c in sorted_cats[-3:] if c[1] < 50]
        
        return SkillRadar(
            user_id=user_id,
            category_scores=category_scores,
            overall_score=overall,
            strong_categories=strong,
            weak_categories=weak,
            last_updated=datetime.now(timezone.utc),
        )
    
    def get_skill_radar(self, user_id: UUID) -> Optional[SkillRadar]:
        """
        Get cached skill radar for a user.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            SkillRadar or None if not calculated
        """
        # In real implementation: query database cache
        return None
    
    def store_skill_radar(self, radar: SkillRadar):
        """
        Store computed skill radar.
        
        Args:
            radar: The skill radar to store
        """
        # In real implementation: save to database
        pass
    
    def update_all_skill_radars(self) -> int:
        """
        Recalculate skill radars for all active users.
        
        Returns:
            Number of users updated
        """
        # In real implementation: query all active users and recalculate
        return 0
    
    def compare_skill_radars(
        self, 
        user_id_1: UUID, 
        user_id_2: UUID
    ) -> Dict[str, Any]:
        """
        Compare skill profiles of two users.
        
        Args:
            user_id_1: First user's UUID
            user_id_2: Second user's UUID
            
        Returns:
            Comparison dictionary
        """
        radar1 = self.calculate_skill_radar(user_id_1)
        radar2 = self.calculate_skill_radar(user_id_2)
        
        comparisons = {}
        all_categories = set(radar1.category_scores.keys()) | set(radar2.category_scores.keys())
        
        for cat in all_categories:
            score1 = radar1.category_scores.get(cat, 0)
            score2 = radar2.category_scores.get(cat, 0)
            comparisons[cat] = {
                "user1": score1,
                "user2": score2,
                "difference": score1 - score2,
            }
        
        return {
            "overall_comparison": {
                "user1_score": radar1.overall_score,
                "user2_score": radar2.overall_score,
                "difference": radar1.overall_score - radar2.overall_score,
            },
            "categories": comparisons,
        }
