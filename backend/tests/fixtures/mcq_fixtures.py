"""
Pytest fixtures for MCQ and Hint System testing.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID

from app.domain.mcq.entities import (
    MCQChallenge,
    MCQOption,
    MCQQuestion,
    MCQAttempt,
    QuestionType,
    Hint,
    HintConfig,
    UserHint,
    UnlockMode,
    DeductionType,
)


@pytest.fixture
def sample_user_id() -> UUID:
    """Sample user ID."""
    return uuid4()


@pytest.fixture
def sample_challenge_id() -> UUID:
    """Sample challenge ID."""
    return uuid4()


@pytest.fixture
def single_question() -> MCQQuestion:
    """Create a single-answer question."""
    question = MCQQuestion(
        id=uuid4(),
        question_text="What is the capital of France?",
        question_type=QuestionType.SINGLE,
        explanation="Paris is the capital of France.",
        difficulty_weight=Decimal("1.0"),
        order_index=0,
    )
    
    # Add options
    question.add_option("London", is_correct=False)
    question.add_option("Paris", is_correct=True)
    question.add_option("Berlin", is_correct=False)
    question.add_option("Madrid", is_correct=False)
    
    return question


@pytest.fixture
def multiple_question() -> MCQQuestion:
    """Create a multiple-answer question."""
    question = MCQQuestion(
        id=uuid4(),
        question_text="Which of the following are prime numbers?",
        question_type=QuestionType.MULTIPLE,
        explanation="2, 3, and 5 are prime numbers. 4 is not.",
        difficulty_weight=Decimal("1.5"),
        order_index=1,
    )
    
    # Add options
    question.add_option("2", is_correct=True)
    question.add_option("3", is_correct=True)
    question.add_option("4", is_correct=False)
    question.add_option("5", is_correct=True)
    
    return question


@pytest.fixture
def true_false_question() -> MCQQuestion:
    """Create a true/false question."""
    question = MCQQuestion(
        id=uuid4(),
        question_text="The Earth is flat.",
        question_type=QuestionType.TRUE_FALSE,
        explanation="The Earth is approximately spherical.",
        difficulty_weight=Decimal("0.5"),
        order_index=2,
    )
    
    # Add options
    question.add_option("True", is_correct=False)
    question.add_option("False", is_correct=True)
    
    return question


@pytest.fixture
def mcq_challenge(
    sample_challenge_id: UUID,
    single_question: MCQQuestion,
    multiple_question: MCQQuestion,
    true_false_question: MCQQuestion,
) -> MCQChallenge:
    """Create an MCQ challenge with 3 questions."""
    challenge = MCQChallenge(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        allow_multiple_answers=True,
        shuffle_options=True,
        show_correct_after_submit=True,
        max_attempts=3,
        time_limit_seconds=300,
        points_per_question=Decimal("100"),
        penalty_per_wrong=Decimal("10"),
        partial_credit=True,
        passing_percentage=Decimal("70.00"),
        questions=[single_question, multiple_question, true_false_question],
    )
    
    return challenge


@pytest.fixture
def mcq_attempts(sample_user_id: UUID, sample_challenge_id: UUID, single_question: MCQQuestion) -> list[MCQAttempt]:
    """Create sample MCQ attempts."""
    correct_option = single_question.get_correct_options()[0]
    
    attempts = [
        MCQAttempt(
            id=uuid4(),
            user_id=sample_user_id,
            challenge_id=sample_challenge_id,
            question_id=single_question.id,
            selected_options=[correct_option.id],
            is_correct=True,
            attempt_number=1,
            time_spent_seconds=30,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            created_at=datetime.utcnow(),
        )
    ]
    
    return attempts


@pytest.fixture
def hint_config(sample_challenge_id: UUID) -> HintConfig:
    """Create hint configuration."""
    return HintConfig(
        challenge_id=sample_challenge_id,
        enabled=True,
        unlock_mode=UnlockMode.MANUAL,
        auto_unlock_minutes=None,
        progressive_chain=True,
        deduction_type=DeductionType.POINTS,
        deduction_value=Decimal("10.00"),
        max_hints_visible=3,
        cooldown_seconds=60,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def progressive_hints(sample_challenge_id: UUID) -> list[Hint]:
    """Create progressive hints for chain testing."""
    hint1 = Hint(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        title="Hint 1: Getting Started",
        content="Look at the URL structure carefully.",
        content_type="text",
        sequence_order=0,
        unlock_after_minutes=None,
        unlock_after_attempts=None,
        unlock_after_hint_id=None,
        custom_cost=None,
    )
    
    hint2 = Hint(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        title="Hint 2: Parameter Analysis",
        content="The 'id' parameter might be vulnerable.",
        content_type="text",
        sequence_order=1,
        unlock_after_minutes=None,
        unlock_after_attempts=None,
        unlock_after_hint_id=hint1.id,  # Requires hint1
        custom_cost=None,
    )
    
    hint3 = Hint(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        title="Hint 3: SQL Injection",
        content="Try adding a single quote to test for SQL injection.",
        content_type="text",
        sequence_order=2,
        unlock_after_minutes=None,
        unlock_after_attempts=2,  # Requires 2 attempts
        unlock_after_hint_id=hint2.id,  # Requires hint2
        custom_cost=Decimal("20.00"),
    )
    
    return [hint1, hint2, hint3]


@pytest.fixture
def attempt_based_hint(sample_challenge_id: UUID) -> Hint:
    """Create an attempt-based unlock hint."""
    return Hint(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        title="Hint: After 3 Attempts",
        content="You've tried 3 times. Consider reviewing the documentation.",
        content_type="text",
        sequence_order=0,
        unlock_after_minutes=None,
        unlock_after_attempts=3,
        unlock_after_hint_id=None,
        custom_cost=None,
    )


@pytest.fixture
def timed_hint(sample_challenge_id: UUID) -> Hint:
    """Create a timed unlock hint."""
    return Hint(
        id=uuid4(),
        challenge_id=sample_challenge_id,
        title="Hint: Time Released",
        content="This hint unlocks after 10 minutes.",
        content_type="text",
        sequence_order=0,
        unlock_after_minutes=10,
        unlock_after_attempts=None,
        unlock_after_hint_id=None,
        custom_cost=None,
    )


@pytest.fixture
def user_hint_unlocked(sample_user_id: UUID, sample_challenge_id: UUID, progressive_hints: list[Hint]) -> UserHint:
    """Create a user hint unlock record."""
    return UserHint(
        id=uuid4(),
        user_id=sample_user_id,
        hint_id=progressive_hints[0].id,
        challenge_id=sample_challenge_id,
        unlocked_at=datetime.utcnow(),
        points_deducted=Decimal("10.00"),
        time_into_challenge=None,
        attempt_number_when_used=1,
    )


@pytest.fixture
def rapid_submission_attempts(sample_user_id: UUID, sample_challenge_id: UUID, single_question: MCQQuestion) -> list[MCQAttempt]:
    """Create attempts that look like rapid submission (bot-like)."""
    attempts = []
    
    for i in range(5):
        # Always pick first option (suspicious pattern)
        first_option = single_question.options[0].id
        
        attempts.append(MCQAttempt(
            id=uuid4(),
            user_id=sample_user_id,
            challenge_id=sample_challenge_id,
            question_id=single_question.id,
            selected_options=[first_option],
            is_correct=False,
            attempt_number=i + 1,
            time_spent_seconds=1,  # Very fast
            ip_address="192.168.1.1",
            user_agent="Bot/1.0",  # Suspicious UA
            created_at=datetime.utcnow(),
        ))
    
    return attempts
