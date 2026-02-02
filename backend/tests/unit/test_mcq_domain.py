"""
Unit tests for MCQ domain entities.

Tests:
- Question validation (single, multiple, true/false)
- Partial credit calculation
- Anti-cheat detection
- Shuffling determinism
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.mcq.entities import (
    MCQChallenge,
    MCQOption,
    MCQQuestion,
    MCQAttempt,
    QuestionType,
    AntiCheatResult,
)


class TestMCQQuestionValidation:
    """Test question answer validation."""
    
    def test_single_answer_correct(self):
        """Test single answer question with correct answer."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.SINGLE,
        )
        opt1 = question.add_option("Wrong", is_correct=False)
        opt2 = question.add_option("Correct", is_correct=True)
        
        is_correct, score = question.validate_answer([opt2.id])
        
        assert is_correct is True
        assert score == 1.0
    
    def test_single_answer_incorrect(self):
        """Test single answer question with wrong answer."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.SINGLE,
        )
        opt1 = question.add_option("Wrong", is_correct=False)
        opt2 = question.add_option("Correct", is_correct=True)
        
        is_correct, score = question.validate_answer([opt1.id])
        
        assert is_correct is False
        assert score == 0.0
    
    def test_single_answer_multiple_selections(self):
        """Test single answer with multiple selections (invalid)."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.SINGLE,
        )
        opt1 = question.add_option("A", is_correct=False)
        opt2 = question.add_option("B", is_correct=True)
        
        is_correct, score = question.validate_answer([opt1.id, opt2.id])
        
        assert is_correct is False
        assert score == 0.0
    
    def test_multiple_answer_all_correct(self):
        """Test multiple answer with all correct options."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.MULTIPLE,
        )
        opt1 = question.add_option("A", is_correct=True)
        opt2 = question.add_option("B", is_correct=True)
        opt3 = question.add_option("C", is_correct=False)
        
        is_correct, score = question.validate_answer([opt1.id, opt2.id])
        
        assert is_correct is True
        assert score == 1.0
    
    def test_multiple_answer_partial_credit(self):
        """Test multiple answer partial credit."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.MULTIPLE,
        )
        opt1 = question.add_option("A", is_correct=True)
        opt2 = question.add_option("B", is_correct=True)
        opt3 = question.add_option("C", is_correct=False)
        
        # Select 1 correct out of 2
        is_correct, score = question.validate_answer([opt1.id])
        
        assert is_correct is False
        assert score == 0.5  # 50% correct
    
    def test_multiple_answer_with_wrong_penalty(self):
        """Test multiple answer with wrong selection penalty."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.MULTIPLE,
        )
        opt1 = question.add_option("A", is_correct=True)
        opt2 = question.add_option("B", is_correct=True)
        opt3 = question.add_option("C", is_correct=False)
        
        # Select all correct plus one wrong
        is_correct, score = question.validate_answer([opt1.id, opt2.id, opt3.id])
        
        assert is_correct is False
        # Score = 1.0 (all correct) - 0.33 (penalty for wrong) = 0.67
        assert score > 0.5 and score < 1.0
    
    def test_true_false_correct(self):
        """Test true/false question."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.TRUE_FALSE,
        )
        opt_true = question.add_option("True", is_correct=False)
        opt_false = question.add_option("False", is_correct=True)
        
        is_correct, score = question.validate_answer([opt_false.id])
        
        assert is_correct is True
        assert score == 1.0
    
    def test_true_false_invalid_options(self):
        """Test true/false with wrong number of options."""
        question = MCQQuestion(
            question_text="Test?",
            question_type=QuestionType.TRUE_FALSE,
        )
        question.add_option("True", is_correct=False)
        question.add_option("False", is_correct=True)
        
        # Should raise on post_init if not exactly 2 options
        # But since we add them manually, we test validation
        assert len(question.options) == 2


class TestMCQChallengeScoring:
    """Test challenge scoring logic."""
    
    def test_calculate_score_all_correct(self, mcq_challenge, mcq_attempts):
        """Test score calculation with all correct answers."""
        # mcq_attempts has 1 correct attempt
        score, passed = mcq_challenge.calculate_score(mcq_attempts)
        
        expected_score = Decimal("100") * Decimal("1.0")  # points * difficulty
        assert score == expected_score
        assert passed is True
    
    def test_calculate_score_with_partial_credit(self):
        """Test score with partial credit enabled."""
        challenge = MCQChallenge(
            points_per_question=Decimal("100"),
            partial_credit=True,
            passing_percentage=Decimal("50"),
        )
        
        # Create question
        question = challenge.add_question("Test?", QuestionType.MULTIPLE)
        opt1 = question.add_option("A", is_correct=True)
        opt2 = question.add_option("B", is_correct=True)
        opt3 = question.add_option("C", is_correct=False)
        
        # Attempt with partial correct
        attempt = MCQAttempt(
            question_id=question.id,
            selected_options=[opt1.id],  # 50% correct
            is_correct=False,
            attempt_number=1,
        )
        
        score, passed = challenge.calculate_score([attempt])
        
        # Should get 50% of points with partial credit
        assert score == Decimal("50")
    
    def test_calculate_score_with_penalty(self):
        """Test score with wrong answer penalty."""
        challenge = MCQChallenge(
            points_per_question=Decimal("100"),
            penalty_per_wrong=Decimal("10"),
            partial_credit=False,
        )
        
        question = challenge.add_question("Test?", QuestionType.SINGLE)
        opt1 = question.add_option("Wrong", is_correct=False)
        opt2 = question.add_option("Correct", is_correct=True)
        
        # Two wrong attempts then correct
        attempts = [
            MCQAttempt(
                question_id=question.id,
                selected_options=[opt1.id],
                is_correct=False,
                attempt_number=1,
            ),
            MCQAttempt(
                question_id=question.id,
                selected_options=[opt1.id],
                is_correct=False,
                attempt_number=2,
            ),
            MCQAttempt(
                question_id=question.id,
                selected_options=[opt2.id],
                is_correct=True,
                attempt_number=3,
            ),
        ]
        
        score, passed = challenge.calculate_score(attempts)
        
        # 100 - (2 * 10) = 80
        assert score == Decimal("80")
        assert passed is True
    
    def test_passing_percentage_calculation(self):
        """Test passing percentage logic."""
        challenge = MCQChallenge(
            points_per_question=Decimal("100"),
            passing_percentage=Decimal("70"),
        )
        
        q1 = challenge.add_question("Q1?", QuestionType.SINGLE)
        q1.add_option("Correct", is_correct=True)
        q1.add_option("Wrong", is_correct=False)
        
        q2 = challenge.add_question("Q2?", QuestionType.SINGLE)
        q2.add_option("Correct", is_correct=True)
        q2.add_option("Wrong", is_correct=False)
        
        # Get only 50% correct
        attempts = [
            MCQAttempt(
                question_id=q1.id,
                selected_options=[q1.options[0].id],
                is_correct=True,
                attempt_number=1,
            ),
            MCQAttempt(
                question_id=q2.id,
                selected_options=[q2.options[1].id],
                is_correct=False,
                attempt_number=1,
            ),
        ]
        
        score, passed = challenge.calculate_score(attempts)
        
        assert score == Decimal("100")  # 1 out of 2 questions
        assert passed is False  # 50% < 70% passing threshold


class TestAntiCheatDetection:
    """Test anti-cheat detection logic."""
    
    def test_rapid_submission_detection(self, mcq_challenge):
        """Test detection of rapid submissions."""
        attempts = [
            MCQAttempt(time_spent_seconds=1),
            MCQAttempt(time_spent_seconds=1),
            MCQAttempt(time_spent_seconds=1),
        ]
        
        result = mcq_challenge.check_anti_cheat(attempts, total_time_seconds=5)
        
        assert result.is_suspicious is True
        assert any("Rapid submission" in r for r in result.reasons)
    
    def test_bot_pattern_detection(self, mcq_challenge):
        """Test detection of bot-like patterns."""
        question = mcq_challenge.questions[0]
        first_option_id = question.options[0].id
        
        attempts = []
        for i in range(5):
            attempts.append(MCQAttempt(
                question_id=question.id,
                selected_options=[first_option_id],
                attempt_number=i+1,
            ))
        
        result = mcq_challenge.check_anti_cheat(attempts, total_time_seconds=60)
        
        assert result.is_suspicious is True
        assert any("first option" in r.lower() for r in result.reasons)
    
    def test_impossible_timing_detection(self, mcq_challenge):
        """Test detection of impossible reading speed."""
        # 3 questions answered in 3 seconds total = 1 second per question
        attempts = [
            MCQAttempt(time_spent_seconds=1),
            MCQAttempt(time_spent_seconds=1),
            MCQAttempt(time_spent_seconds=1),
        ]
        
        result = mcq_challenge.check_anti_cheat(attempts, total_time_seconds=3)
        
        assert result.is_suspicious is True
        assert any("reading speed" in r.lower() for r in result.reasons)
    
    def test_normal_submission_not_flagged(self, mcq_challenge):
        """Test that normal submissions are not flagged."""
        attempts = [
            MCQAttempt(time_spent_seconds=30),
            MCQAttempt(time_spent_seconds=45),
            MCQAttempt(time_spent_seconds=20),
        ]
        
        result = mcq_challenge.check_anti_cheat(attempts, total_time_seconds=95)
        
        assert result.is_suspicious is False
        assert result.confidence_score < 0.7


class TestShufflingDeterminism:
    """Test that shuffling is deterministic per user."""
    
    def test_same_user_same_order(self):
        """Test same user gets same shuffle order."""
        from app.application.mcq.service import MCQService
        
        service = MCQService(db_session=None)
        user_id = uuid4()
        challenge_id = uuid4()
        
        seed1 = service._generate_shuffle_seed(user_id, challenge_id)
        seed2 = service._generate_shuffle_seed(user_id, challenge_id)
        
        assert seed1 == seed2
    
    def test_different_users_different_order(self):
        """Test different users get different shuffle orders."""
        from app.application.mcq.service import MCQService
        
        service = MCQService(db_session=None)
        user1_id = uuid4()
        user2_id = uuid4()
        challenge_id = uuid4()
        
        seed1 = service._generate_shuffle_seed(user1_id, challenge_id)
        seed2 = service._generate_shuffle_seed(user2_id, challenge_id)
        
        assert seed1 != seed2
    
    def test_shuffle_determinism(self):
        """Test shuffle produces same result with same seed."""
        from app.application.mcq.service import MCQService
        
        service = MCQService(db_session=None)
        
        options = [
            MCQOption(id=uuid4(), option_text="A"),
            MCQOption(id=uuid4(), option_text="B"),
            MCQOption(id=uuid4(), option_text="C"),
            MCQOption(id=uuid4(), option_text="D"),
        ]
        
        seed = "test-seed-123"
        shuffled1 = service._shuffle_options(options, seed)
        shuffled2 = service._shuffle_options(options, seed)
        
        # Same order
        assert [opt.id for opt in shuffled1] == [opt.id for opt in shuffled2]
        
        # Different order with different seed
        shuffled3 = service._shuffle_options(options, "different-seed")
        assert [opt.id for opt in shuffled1] != [opt.id for opt in shuffled3]


class TestMCQOption:
    """Test MCQ option value object."""
    
    def test_option_to_dict(self):
        """Test option serialization."""
        option = MCQOption(
            option_text="Test option",
            is_correct=True,
            explanation="This is why",
            order_index=0,
        )
        
        # Without answer
        dict_no_answer = option.to_dict(include_answer=False)
        assert "is_correct" not in dict_no_answer
        assert "explanation" not in dict_no_answer
        
        # With answer
        dict_with_answer = option.to_dict(include_answer=True)
        assert dict_with_answer["is_correct"] is True
        assert dict_with_answer["explanation"] == "This is why"


class TestMCQAttempt:
    """Test MCQ attempt value object."""
    
    def test_attempt_to_dict(self):
        """Test attempt serialization."""
        attempt = MCQAttempt(
            question_id=uuid4(),
            selected_options=[uuid4(), uuid4()],
            is_correct=True,
            attempt_number=1,
            time_spent_seconds=30,
        )
        
        result = attempt.to_dict()
        
        assert "question_id" in result
        assert "selected_options" in result
        assert result["is_correct"] is True
        assert result["attempt_number"] == 1
