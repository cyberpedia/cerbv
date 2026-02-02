"""
Cerberus CTF Platform - MCQ Domain Entities
Multiple Choice Question challenge type with advanced hint system
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4


class QuestionType(str, Enum):
    """MCQ question types."""
    SINGLE = "single"       # Single correct answer
    MULTIPLE = "multiple"   # Multiple correct answers
    TRUE_FALSE = "true_false"  # True/False question


class UnlockMode(str, Enum):
    """Hint unlock modes."""
    MANUAL = "manual"           # User manually unlocks
    TIMED = "timed"             # Auto-unlock after time
    PROGRESSIVE = "progressive" # Unlock in sequence
    ATTEMPT_BASED = "attempt_based"  # Unlock after N attempts
    PURCHASE = "purchase"       # Purchase with points


class DeductionType(str, Enum):
    """Hint deduction types."""
    POINTS = "points"           # Fixed points deduction
    PERCENTAGE = "percentage"   # Percentage of challenge points
    TIME_PENALTY = "time_penalty"  # Adds time penalty


@dataclass
class MCQOption:
    """Value object for MCQ option."""
    id: UUID = field(default_factory=uuid4)
    option_text: str = ""
    is_correct: bool = False
    explanation: Optional[str] = None
    order_index: int = 0
    
    def to_dict(self, include_answer: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": str(self.id),
            "option_text": self.option_text,
            "order_index": self.order_index,
        }
        if include_answer:
            result["is_correct"] = self.is_correct
            result["explanation"] = self.explanation
        return result


@dataclass
class MCQQuestion:
    """Value object for MCQ question."""
    id: UUID = field(default_factory=uuid4)
    question_text: str = ""
    question_type: QuestionType = QuestionType.SINGLE
    explanation: Optional[str] = None
    difficulty_weight: Decimal = field(default_factory=lambda: Decimal("1.00"))
    order_index: int = 0
    image_url: Optional[str] = None
    code_snippet: Optional[str] = None
    options: List[MCQOption] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate question after initialization."""
        if self.question_type == QuestionType.TRUE_FALSE:
            # True/False questions should have exactly 2 options
            if len(self.options) != 2:
                raise ValueError("True/False questions must have exactly 2 options")
    
    def add_option(self, text: str, is_correct: bool = False, 
                   explanation: Optional[str] = None) -> MCQOption:
        """Add an option to the question."""
        option = MCQOption(
            option_text=text,
            is_correct=is_correct,
            explanation=explanation,
            order_index=len(self.options),
        )
        self.options.append(option)
        return option
    
    def get_correct_options(self) -> List[MCQOption]:
        """Get all correct options."""
        return [opt for opt in self.options if opt.is_correct]
    
    def validate_answer(self, selected_option_ids: List[UUID]) -> Tuple[bool, float]:
        """
        Validate answer and return (is_correct, score_percentage).
        
        For single answer: all-or-nothing
        For multiple answers: partial credit possible
        """
        correct_ids = {opt.id for opt in self.options if opt.is_correct}
        selected_set = set(selected_option_ids)
        
        if self.question_type == QuestionType.SINGLE:
            # Single answer: must match exactly one correct option
            is_correct = len(selected_set) == 1 and selected_set == correct_ids
            return is_correct, 1.0 if is_correct else 0.0
        
        elif self.question_type == QuestionType.MULTIPLE:
            # Multiple answers: partial credit
            if not selected_set:
                return False, 0.0
            
            correct_selected = len(selected_set & correct_ids)
            incorrect_selected = len(selected_set - correct_ids)
            total_correct = len(correct_ids)
            
            if total_correct == 0:
                return False, 0.0
            
            # Score = correct_selected/total_correct - penalty for wrong answers
            score = correct_selected / total_correct
            penalty = incorrect_selected / len(self.options) if self.options else 0
            final_score = max(0.0, score - penalty)
            
            is_correct = correct_selected == total_correct and incorrect_selected == 0
            return is_correct, final_score
        
        elif self.question_type == QuestionType.TRUE_FALSE:
            # True/False: single correct answer
            is_correct = len(selected_set) == 1 and selected_set == correct_ids
            return is_correct, 1.0 if is_correct else 0.0
        
        return False, 0.0
    
    def to_dict(self, include_answers: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "question_text": self.question_text,
            "question_type": self.question_type.value,
            "explanation": self.explanation if include_answers else None,
            "difficulty_weight": float(self.difficulty_weight),
            "order_index": self.order_index,
            "image_url": self.image_url,
            "code_snippet": self.code_snippet,
            "options": [opt.to_dict(include_answer=include_answers) 
                       for opt in self.options],
        }


@dataclass
class MCQAttempt:
    """Value object for MCQ attempt tracking."""
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    question_id: UUID = field(default_factory=uuid4)
    selected_options: List[UUID] = field(default_factory=list)
    is_correct: Optional[bool] = None
    attempt_number: int = 1
    time_spent_seconds: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "question_id": str(self.question_id),
            "selected_options": [str(opt) for opt in self.selected_options],
            "is_correct": self.is_correct,
            "attempt_number": self.attempt_number,
            "time_spent_seconds": self.time_spent_seconds,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class AntiCheatResult:
    """Result of anti-cheat analysis."""
    is_suspicious: bool = False
    reasons: List[str] = field(default_factory=list)
    confidence_score: float = 0.0  # 0.0 to 1.0
    
    def add_flag(self, reason: str, severity: float = 0.5):
        """Add a suspicious activity flag."""
        self.reasons.append(reason)
        self.confidence_score = min(1.0, self.confidence_score + severity)
        self.is_suspicious = self.confidence_score >= 0.7


@dataclass
class MCQChallenge:
    """
    MCQ Challenge aggregate root.
    
    Extends the base Challenge concept for multiple choice questions.
    """
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    
    # Configuration
    allow_multiple_answers: bool = False
    shuffle_options: bool = True
    show_correct_after_submit: bool = False
    max_attempts: int = 3
    time_limit_seconds: Optional[int] = None
    points_per_question: Decimal = field(default_factory=lambda: Decimal("0"))
    penalty_per_wrong: Decimal = field(default_factory=lambda: Decimal("0"))
    partial_credit: bool = False
    passing_percentage: Decimal = field(default_factory=lambda: Decimal("70.00"))
    
    # Questions
    questions: List[MCQQuestion] = field(default_factory=list)
    
    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_question(self, text: str, question_type: QuestionType = QuestionType.SINGLE,
                     explanation: Optional[str] = None) -> MCQQuestion:
        """Add a question to the challenge."""
        question = MCQQuestion(
            question_text=text,
            question_type=question_type,
            explanation=explanation,
            order_index=len(self.questions),
        )
        self.questions.append(question)
        self.updated_at = datetime.utcnow()
        return question
    
    def get_total_points(self) -> Decimal:
        """Calculate total available points."""
        if self.points_per_question > 0:
            return self.points_per_question * len(self.questions)
        return Decimal("0")
    
    def calculate_score(self, attempts: List[MCQAttempt]) -> Tuple[Decimal, bool]:
        """
        Calculate total score from attempts.
        
        Returns (score, passed) tuple.
        """
        if not self.questions:
            return Decimal("0"), False
        
        # Group attempts by question
        attempts_by_question: Dict[UUID, List[MCQAttempt]] = {}
        for attempt in attempts:
            if attempt.question_id not in attempts_by_question:
                attempts_by_question[attempt.question_id] = []
            attempts_by_question[attempt.question_id].append(attempt)
        
        total_score = Decimal("0")
        
        for question in self.questions:
            question_attempts = attempts_by_question.get(question.id, [])
            if not question_attempts:
                continue
            
            # Get the best attempt for this question
            best_attempt = max(
                question_attempts,
                key=lambda a: (a.is_correct or False, -a.attempt_number)
            )
            
            # Calculate score for this question
            is_correct, percentage = question.validate_answer(best_attempt.selected_options)
            
            if is_correct:
                question_score = self.points_per_question * question.difficulty_weight
            elif self.partial_credit:
                question_score = self.points_per_question * question.difficulty_weight * Decimal(str(percentage))
            else:
                question_score = Decimal("0")
            
            # Apply penalty for wrong attempts
            wrong_attempts = sum(1 for a in question_attempts if not a.is_correct)
            penalty = self.penalty_per_wrong * wrong_attempts
            
            total_score += max(Decimal("0"), question_score - penalty)
        
        # Check if passed
        total_possible = self.get_total_points()
        if total_possible > 0:
            percentage = (total_score / total_possible) * 100
            passed = percentage >= self.passing_percentage
        else:
            passed = False
        
        return total_score, passed
    
    def check_anti_cheat(self, attempts: List[MCQAttempt], 
                        total_time_seconds: int) -> AntiCheatResult:
        """
        Check for suspicious activity patterns.
        
        Detects:
        - Rapid submissions (< 10 seconds total)
        - Always selecting first option (bot pattern)
        - Impossible timing
        """
        result = AntiCheatResult()
        
        if not attempts:
            return result
        
        # Check rapid submission
        if total_time_seconds < 10:
            result.add_flag("Rapid submission detected (< 10 seconds)", 0.8)
        
        # Check for bot pattern (always first option)
        if len(attempts) >= 3:
            first_option_count = 0
            for attempt in attempts:
                # Get first option for the question
                question = next(
                    (q for q in self.questions if q.id == attempt.question_id),
                    None
                )
                if question and question.options:
                    first_option_id = question.options[0].id
                    if len(attempt.selected_options) == 1 and attempt.selected_options[0] == first_option_id:
                        first_option_count += 1
            
            if first_option_count >= len(attempts) * 0.8:  # 80% first option
                result.add_flag("Suspicious pattern: always selecting first option", 0.9)
        
        # Check impossible timing (faster than human reading speed)
        avg_time_per_question = total_time_seconds / len(self.questions) if self.questions else 0
        if avg_time_per_question < 2:  # Less than 2 seconds per question
            result.add_flag("Impossible reading speed detected", 0.7)
        
        return result
    
    def to_dict(self, include_answers: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "allow_multiple_answers": self.allow_multiple_answers,
            "shuffle_options": self.shuffle_options,
            "show_correct_after_submit": self.show_correct_after_submit,
            "max_attempts": self.max_attempts,
            "time_limit_seconds": self.time_limit_seconds,
            "points_per_question": float(self.points_per_question),
            "penalty_per_wrong": float(self.penalty_per_wrong),
            "partial_credit": self.partial_credit,
            "passing_percentage": float(self.passing_percentage),
            "questions": [q.to_dict(include_answers=include_answers) 
                         for q in self.questions],
        }


@dataclass
class HintConfig:
    """Hint system configuration for a challenge."""
    challenge_id: UUID = field(default_factory=uuid4)
    enabled: bool = True
    unlock_mode: UnlockMode = UnlockMode.MANUAL
    auto_unlock_minutes: Optional[int] = None
    progressive_chain: bool = False
    deduction_type: DeductionType = DeductionType.POINTS
    deduction_value: Decimal = field(default_factory=lambda: Decimal("10.00"))
    max_hints_visible: Optional[int] = None
    cooldown_seconds: int = 0
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_deduction(self, challenge_points: Decimal) -> Decimal:
        """Calculate point deduction for unlocking a hint."""
        if self.deduction_type == DeductionType.POINTS:
            return self.deduction_value
        elif self.deduction_type == DeductionType.PERCENTAGE:
            return challenge_points * (self.deduction_value / 100)
        elif self.deduction_type == DeductionType.TIME_PENALTY:
            return Decimal("0")  # Time penalty doesn't deduct points
        return Decimal("0")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "challenge_id": str(self.challenge_id),
            "enabled": self.enabled,
            "unlock_mode": self.unlock_mode.value,
            "auto_unlock_minutes": self.auto_unlock_minutes,
            "progressive_chain": self.progressive_chain,
            "deduction_type": self.deduction_type.value,
            "deduction_value": float(self.deduction_value),
            "max_hints_visible": self.max_hints_visible,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass
class Hint:
    """Hint entity with unlock conditions."""
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    title: Optional[str] = None
    content: str = ""
    content_type: str = "text"  # text, image, video, link
    attachment_url: Optional[str] = None
    sequence_order: int = 0
    
    # Unlock conditions
    unlock_after_minutes: Optional[int] = None
    unlock_after_attempts: Optional[int] = None
    unlock_after_hint_id: Optional[UUID] = None
    custom_cost: Optional[Decimal] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_preview(self, length: int = 100) -> str:
        """Get truncated preview of hint content."""
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + "..."
    
    def is_unlocked(self, user_hints: List["UserHint"], 
                   attempts_count: int = 0,
                   challenge_start_time: Optional[datetime] = None) -> Tuple[bool, List[str]]:
        """
        Check if hint is unlocked for user.
        
        Returns (is_unlocked, conditions_not_met) tuple.
        """
        conditions_not_met = []
        
        # Check if already unlocked
        if any(uh.hint_id == self.id for uh in user_hints):
            return True, []
        
        # Check progressive chain - previous hint must be unlocked
        if self.unlock_after_hint_id:
            prev_unlocked = any(uh.hint_id == self.unlock_after_hint_id for uh in user_hints)
            if not prev_unlocked:
                conditions_not_met.append("Previous hint not unlocked")
        
        # Check attempt-based unlock
        if self.unlock_after_attempts is not None:
            if attempts_count < self.unlock_after_attempts:
                conditions_not_met.append(
                    f"Requires {self.unlock_after_attempts} attempts, you have {attempts_count}"
                )
        
        # Check time-based unlock
        if self.unlock_after_minutes is not None and challenge_start_time:
            elapsed = datetime.utcnow() - challenge_start_time
            required = timedelta(minutes=self.unlock_after_minutes)
            if elapsed < required:
                remaining = required - elapsed
                conditions_not_met.append(
                    f"Unlocks in {remaining.seconds // 60} minutes"
                )
        
        return len(conditions_not_met) == 0, conditions_not_met
    
    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "title": self.title,
            "content_type": self.content_type,
            "sequence_order": self.sequence_order,
            "unlock_after_minutes": self.unlock_after_minutes,
            "unlock_after_attempts": self.unlock_after_attempts,
            "custom_cost": float(self.custom_cost) if self.custom_cost else None,
        }
        
        if include_content:
            result["content"] = self.content
            result["attachment_url"] = self.attachment_url
        else:
            result["preview"] = self.get_preview()
        
        return result


@dataclass
class UserHint:
    """Tracks hints unlocked by users."""
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    hint_id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    unlocked_at: datetime = field(default_factory=datetime.utcnow)
    points_deducted: Decimal = field(default_factory=lambda: Decimal("0"))
    time_into_challenge: Optional[timedelta] = None
    attempt_number_when_used: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "hint_id": str(self.hint_id),
            "unlocked_at": self.unlocked_at.isoformat(),
            "points_deducted": float(self.points_deducted),
            "time_into_challenge": str(self.time_into_challenge) if self.time_into_challenge else None,
            "attempt_number_when_used": self.attempt_number_when_used,
        }
