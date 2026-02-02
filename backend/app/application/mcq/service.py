"""
Cerberus CTF Platform - MCQ Application Service
Business logic for MCQ challenges with anti-cheat detection
"""

import hashlib
import hmac
import ipaddress
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import structlog

from app.domain.mcq.entities import (
    AntiCheatResult,
    MCQAttempt,
    MCQChallenge,
    MCQOption,
    MCQQuestion,
)

logger = structlog.get_logger(__name__)


@dataclass
class ShuffledQuestion:
    """Question with shuffled options for a specific user."""
    question: MCQQuestion
    shuffled_options: List[MCQOption]
    shuffle_seed: str


@dataclass
class SubmissionResult:
    """Result of MCQ submission."""
    success: bool
    score: Decimal
    total_possible: Decimal
    passed: bool
    correct_answers: Dict[UUID, bool]  # question_id -> is_correct
    anti_cheat_result: Optional[AntiCheatResult] = None
    message: str = ""
    time_exceeded: bool = False


class MCQService:
    """
    Service for managing MCQ challenges.
    
    Handles question retrieval with user-specific shuffling,
    submission processing with anti-cheat detection, and scoring.
    """
    
    RAPID_SUBMISSION_THRESHOLD = 10  # seconds
    MIN_TIME_PER_QUESTION = 2  # seconds
    BOT_PATTERN_THRESHOLD = 0.8  # 80% same pattern
    
    def __init__(self, db_session, cache_client=None):
        """
        Initialize MCQ service.
        
        Args:
            db_session: Database session for persistence
            cache_client: Optional cache client for rate limiting
        """
        self._db = db_session
        self._cache = cache_client
    
    def _generate_shuffle_seed(self, user_id: UUID, challenge_id: UUID) -> str:
        """
        Generate deterministic shuffle seed for user.
        
        Uses HMAC to ensure same user always gets same order,
        but different users get different orders.
        """
        secret_key = "cerberus-mcq-shuffle-secret"  # In production, use env var
        data = f"{challenge_id}:{user_id}"
        return hmac.new(
            secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _shuffle_options(self, options: List[MCQOption], seed: str) -> List[MCQOption]:
        """Shuffle options deterministically based on seed."""
        # Create RNG with seed
        rng = random.Random(seed)
        
        # Shuffle copy of options
        shuffled = options.copy()
        rng.shuffle(shuffled)
        
        return shuffled
    
    async def get_questions_for_user(
        self,
        challenge_id: UUID,
        user_id: UUID,
        include_admin: bool = False
    ) -> List[ShuffledQuestion]:
        """
        Get questions with user-specific shuffled options.
        
        Args:
            challenge_id: The MCQ challenge ID
            user_id: User requesting questions
            include_admin: If True, don't shuffle (for admin preview)
            
        Returns:
            List of questions with shuffled options
        """
        # Fetch challenge with questions
        challenge = await self._get_challenge(challenge_id)
        
        if not challenge:
            raise ValueError(f"Challenge not found: {challenge_id}")
        
        result = []
        seed = self._generate_shuffle_seed(user_id, challenge_id)
        
        for question in challenge.questions:
            if include_admin or not challenge.shuffle_options:
                # No shuffling for admins or if disabled
                shuffled = question.options
            else:
                # Shuffle options deterministically
                shuffled = self._shuffle_options(question.options, seed + str(question.id))
            
            result.append(ShuffledQuestion(
                question=question,
                shuffled_options=shuffled,
                shuffle_seed=seed
            ))
        
        logger.info(
            "Retrieved MCQ questions",
            challenge_id=str(challenge_id),
            user_id=str(user_id),
            question_count=len(result)
        )
        
        return result
    
    async def submit_answers(
        self,
        challenge_id: UUID,
        user_id: UUID,
        answers: List[Dict[str, Any]],
        client_info: Dict[str, Any],
    ) -> SubmissionResult:
        """
        Submit MCQ answers with anti-cheat validation.
        
        Args:
            challenge_id: The MCQ challenge ID
            user_id: User submitting answers
            answers: List of {question_id, selected_option_ids, time_spent_seconds}
            client_info: {ip_address, user_agent, started_at}
            
        Returns:
            SubmissionResult with score and anti-cheat flags
        """
        challenge = await self._get_challenge(challenge_id)
        
        if not challenge:
            return SubmissionResult(
                success=False,
                score=Decimal("0"),
                total_possible=Decimal("0"),
                passed=False,
                correct_answers={},
                message="Challenge not found"
            )
        
        # Check rate limiting
        if await self._is_rate_limited(user_id, challenge_id):
            return SubmissionResult(
                success=False,
                score=Decimal("0"),
                total_possible=Decimal("0"),
                passed=False,
                correct_answers={},
                message="Rate limit exceeded. Maximum 5 attempts per minute."
            )
        
        # Calculate total time
        started_at = client_info.get("started_at")
        if started_at:
            total_time = (datetime.utcnow() - started_at).total_seconds()
        else:
            total_time = sum(a.get("time_spent_seconds", 0) for a in answers)
        
        # Check time limit
        time_exceeded = False
        if challenge.time_limit_seconds and total_time > challenge.time_limit_seconds:
            time_exceeded = True
        
        # Process each answer
        attempts = []
        correct_answers = {}
        
        for answer in answers:
            question_id = UUID(answer["question_id"])
            selected_options = [UUID(opt) for opt in answer["selected_option_ids"]]
            time_spent = answer.get("time_spent_seconds")
            
            # Get attempt number
            attempt_number = await self._get_next_attempt_number(
                user_id, challenge_id, question_id
            )
            
            # Check max attempts
            if attempt_number > challenge.max_attempts:
                return SubmissionResult(
                    success=False,
                    score=Decimal("0"),
                    total_possible=Decimal("0"),
                    passed=False,
                    correct_answers={},
                    message=f"Maximum attempts ({challenge.max_attempts}) exceeded"
                )
            
            # Find question and validate
            question = next(
                (q for q in challenge.questions if q.id == question_id),
                None
            )
            
            if not question:
                continue
            
            is_correct, _ = question.validate_answer(selected_options)
            correct_answers[question_id] = is_correct
            
            # Create attempt record
            attempt = MCQAttempt(
                user_id=user_id,
                challenge_id=challenge_id,
                question_id=question_id,
                selected_options=selected_options,
                is_correct=is_correct,
                attempt_number=attempt_number,
                time_spent_seconds=time_spent,
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
            )
            attempts.append(attempt)
            
            # Save attempt
            await self._save_attempt(attempt)
        
        # Run anti-cheat detection
        anti_cheat = challenge.check_anti_cheat(attempts, int(total_time))
        
        # Calculate score
        all_attempts = await self._get_user_attempts(user_id, challenge_id)
        score, passed = challenge.calculate_score(all_attempts)
        
        # Log suspicious activity
        if anti_cheat.is_suspicious:
            logger.warning(
                "Suspicious MCQ activity detected",
                user_id=str(user_id),
                challenge_id=str(challenge_id),
                confidence=anti_cheat.confidence_score,
                reasons=anti_cheat.reasons
            )
        
        return SubmissionResult(
            success=True,
            score=score,
            total_possible=challenge.get_total_points(),
            passed=passed and not time_exceeded,
            correct_answers=correct_answers,
            anti_cheat_result=anti_cheat,
            message="Time limit exceeded" if time_exceeded else "",
            time_exceeded=time_exceeded
        )
    
    async def calculate_partial_credit(
        self,
        challenge_id: UUID,
        user_id: UUID
    ) -> Dict[UUID, Tuple[bool, float]]:
        """
        Calculate partial credit for all questions.
        
        Returns:
            Dict mapping question_id to (is_correct, score_percentage)
        """
        challenge = await self._get_challenge(challenge_id)
        
        if not challenge or not challenge.partial_credit:
            return {}
        
        attempts = await self._get_user_attempts(user_id, challenge_id)
        result = {}
        
        for question in challenge.questions:
            question_attempts = [
                a for a in attempts if a.question_id == question.id
            ]
            
            if question_attempts:
                best = max(question_attempts, key=lambda a: a.is_correct or False)
                is_correct, score = question.validate_answer(best.selected_options)
                result[question.id] = (is_correct, score)
            else:
                result[question.id] = (False, 0.0)
        
        return result
    
    async def get_results(self, challenge_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """
        Get user's results for a challenge.
        
        Returns detailed results including correct answers if allowed.
        """
        challenge = await self._get_challenge(challenge_id)
        
        if not challenge:
            return {"error": "Challenge not found"}
        
        attempts = await self._get_user_attempts(user_id, challenge_id)
        score, passed = challenge.calculate_score(attempts)
        
        # Build result details
        question_results = []
        for question in challenge.questions:
            question_attempts = [
                a for a in attempts if a.question_id == question.id
            ]
            
            best_attempt = None
            if question_attempts:
                best_attempt = max(
                    question_attempts,
                    key=lambda a: (a.is_correct or False, -a.attempt_number)
                )
            
            result = {
                "question_id": str(question.id),
                "question_text": question.question_text,
                "attempts_count": len(question_attempts),
                "is_correct": best_attempt.is_correct if best_attempt else None,
            }
            
            # Include correct answers if configured
            if challenge.show_correct_after_submit:
                result["correct_options"] = [
                    str(opt.id) for opt in question.get_correct_options()
                ]
                result["explanation"] = question.explanation
            
            question_results.append(result)
        
        return {
            "challenge_id": str(challenge_id),
            "score": float(score),
            "total_possible": float(challenge.get_total_points()),
            "passed": passed,
            "passing_percentage": float(challenge.passing_percentage),
            "questions": question_results,
        }
    
    # Repository methods (to be implemented with actual database)
    
    async def _get_challenge(self, challenge_id: UUID) -> Optional[MCQChallenge]:
        """Fetch challenge from database."""
        # This would be implemented with actual ORM queries
        # For now, returning None to indicate repository pattern
        raise NotImplementedError("Repository method to be implemented")
    
    async def _save_attempt(self, attempt: MCQAttempt) -> None:
        """Save attempt to database."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def _get_user_attempts(
        self, user_id: UUID, challenge_id: UUID
    ) -> List[MCQAttempt]:
        """Get all attempts by user for challenge."""
        raise NotImplementedError("Repository method to be implemented")
    
    async def _get_next_attempt_number(
        self, user_id: UUID, challenge_id: UUID, question_id: UUID
    ) -> int:
        """Get next attempt number for question."""
        attempts = await self._get_user_attempts(user_id, challenge_id)
        question_attempts = [
            a for a in attempts if a.question_id == question_id
        ]
        return len(question_attempts) + 1
    
    async def _is_rate_limited(self, user_id: UUID, challenge_id: UUID) -> bool:
        """Check if user is rate limited."""
        if not self._cache:
            return False
        
        key = f"mcq_rate_limit:{user_id}:{challenge_id}"
        
        # This would use cache client to check/increment counter
        # For now, returning False
        return False
    
    # Anti-cheat helper methods
    
    def _check_ip_reputation(self, ip_address: str) -> float:
        """
        Check IP address reputation.
        
        Returns risk score 0.0 to 1.0.
        """
        try:
            ip = ipaddress.ip_address(ip_address)
            
            # Check for private/residential ranges (lower risk)
            if ip.is_private:
                return 0.3
            
            # Check for known datacenter/cloud ranges (higher risk)
            # This would integrate with IP reputation services
            
            return 0.5  # Default
        except ValueError:
            return 0.8  # Invalid IP is suspicious
    
    def _analyze_answer_pattern(self, attempts: List[MCQAttempt]) -> Dict[str, Any]:
        """
        Analyze answer patterns for bot detection.
        
        Returns pattern analysis results.
        """
        if len(attempts) < 3:
            return {"suspicious": False, "reason": "Insufficient data"}
        
        # Check for sequential selection (1,2,3,4,5...)
        sequential_count = 0
        for i, attempt in enumerate(attempts[:-1]):
            if len(attempt.selected_options) == 1:
                current_idx = int(attempt.selected_options[0]) % 100  # Simplified
                next_idx = int(attempts[i + 1].selected_options[0]) % 100
                if next_idx == current_idx + 1:
                    sequential_count += 1
        
        sequential_ratio = sequential_count / max(1, len(attempts) - 1)
        
        return {
            "suspicious": sequential_ratio > 0.5,
            "sequential_ratio": sequential_ratio,
            "reason": "Sequential pattern detected" if sequential_ratio > 0.5 else "Normal pattern"
        }
