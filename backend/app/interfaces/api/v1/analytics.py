"""
Analytics API endpoints.
"""

from uuid import UUID
from fastapi import APIRouter, Depends


router = APIRouter(prefix="/analytics", tags=["Analytics"])


# === Challenge Analytics Endpoints ===

@router.get("/challenges/{challenge_id}/stats")
async def get_challenge_stats(challenge_id: UUID):
    """
    Get statistics for a specific challenge.
    """
    # In real implementation: use ChallengeAnalyticsService
    return {
        "challenge_id": str(challenge_id),
        "total_attempts": 100,
        "total_solves": 60,
        "average_solve_time_seconds": 1800.0,
        "median_solve_time_seconds": 1500.0,
        "drop_off_rate": 40.0,
        "first_solve_time": "2024-01-01T12:00:00Z",
        "last_solve_time": "2024-01-01T18:00:00Z",
    }


@router.get("/challenges/stats")
async def get_all_challenge_stats():
    """
    Get statistics for all challenges.
    """
    # In real implementation: use ChallengeAnalyticsService
    return {
        "challenges": []
    }


@router.get("/challenges/{challenge_id}/distribution")
async def get_time_distribution(challenge_id: UUID):
    """
    Get time distribution histogram for a challenge.
    """
    return {
        "challenge_id": str(challenge_id),
        "buckets": {
            "0-5min": 10,
            "5-15min": 15,
            "15-30min": 12,
            "30-60min": 8,
            "1-2hrs": 5,
            "2-6hrs": 3,
            "6-24hrs": 2,
            "24hrs+": 0,
        },
        "unit": "minutes",
    }


@router.get("/categories/stats")
async def get_category_stats():
    """
    Get statistics by challenge category.
    """
    return {
        "web": {"total_challenges": 10, "total_solves": 150, "avg_difficulty": 5.2},
        "pwn": {"total_challenges": 8, "total_solves": 80, "avg_difficulty": 6.1},
        "crypto": {"total_challenges": 12, "total_solves": 200, "avg_difficulty": 4.5},
        "reverse": {"total_challenges": 6, "total_solves": 40, "avg_difficulty": 7.0},
    }


@router.get("/competition/overview")
async def get_competition_overview():
    """
    Get overall competition statistics.
    """
    return {
        "total_participants": 500,
        "total_solves": 2500,
        "total_challenges": 50,
        "solved_challenges": 45,
        "average_solves_per_team": 5.0,
        "competition_duration_hours": 48.0,
        "current_phase": "active",
    }


# === User Skill Radar Endpoints ===

@router.get("/users/{user_id}/skills")
async def get_user_skills(user_id: UUID):
    """
    Get skill profile for a user.
    """
    return {
        "user_id": str(user_id),
        "category_scores": {
            "web": 75.5,
            "pwn": 45.0,
            "crypto": 88.0,
            "reverse": 30.0,
            "forensics": 60.0,
            "misc": 85.0,
        },
        "overall_score": 63.9,
        "strong_categories": ["crypto", "misc", "web"],
        "weak_categories": ["reverse", "pwn"],
        "last_updated": "2024-01-01T12:00:00Z",
    }


@router.post("/users/{user_id}/skills/refresh")
async def refresh_user_skills(user_id: UUID):
    """
    Refresh skill profile for a user (recalculate from solves).
    """
    return {
        "success": True,
        "message": "Skill profile refreshed",
    }


@router.get("/users/{user_id}/skills/compare/{other_user_id}")
async def compare_user_skills(user_id: UUID, other_user_id: UUID):
    """
    Compare skill profiles of two users.
    """
    return {
        "overall_comparison": {
            "user1_score": 63.9,
            "user2_score": 72.5,
            "difference": -8.6,
        },
        "categories": {
            "web": {"user1": 75.5, "user2": 80.0, "difference": -4.5},
            "pwn": {"user1": 45.0, "user2": 55.0, "difference": -10.0},
            "crypto": {"user1": 88.0, "user2": 85.0, "difference": 3.0},
            "reverse": {"user1": 30.0, "user2": 45.0, "difference": -15.0},
        },
    }
