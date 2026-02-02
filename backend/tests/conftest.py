"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(backend_path))

# Import fixtures
from tests.fixtures.mcq_fixtures import (
    sample_user_id,
    sample_challenge_id,
    single_question,
    multiple_question,
    true_false_question,
    mcq_challenge,
    mcq_attempts,
    hint_config,
    progressive_hints,
    attempt_based_hint,
    timed_hint,
    user_hint_unlocked,
    rapid_submission_attempts,
)

__all__ = [
    "sample_user_id",
    "sample_challenge_id",
    "single_question",
    "multiple_question",
    "true_false_question",
    "mcq_challenge",
    "mcq_attempts",
    "hint_config",
    "progressive_hints",
    "attempt_based_hint",
    "timed_hint",
    "user_hint_unlocked",
    "rapid_submission_attempts",
]


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
