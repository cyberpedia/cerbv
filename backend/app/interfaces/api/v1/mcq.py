"""
Cerberus CTF Platform - MCQ API Endpoints
Multiple Choice Question challenge endpoints with anti-cheat
"""

from datetime import datetime
from typing import Annotated, Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.application.mcq.service import MCQService, SubmissionResult
from app.interfaces.api.v1.auth import get_current_user, require_admin

router = APIRouter()


# Request/Response Models

class MCQOptionResponse(BaseModel):
    """MCQ option response (without correct answer)."""
    id: str
    option_text: str
    order_index: int


class MCQQuestionResponse(BaseModel):
    """MCQ question response."""
    id: str
    question_text: str
    question_type: str
    difficulty_weight: float
    order_index: int
    image_url: str | None
    code_snippet: str | None
    options: list[MCQOptionResponse]


class MCQQuestionsListResponse(BaseModel):
    """List of MCQ questions for a challenge."""
    challenge_id: str
    questions: list[MCQQuestionResponse]
    time_limit_seconds: int | None
    max_attempts: int
    started_at: str | None = None  # Server timestamp when user started


class MCQAnswerSubmission(BaseModel):
    """Single question answer submission."""
    question_id: str
    selected_option_ids: list[str]
    time_spent_seconds: int | None = Field(default=None, ge=0)
    
    @field_validator("selected_option_ids")
    @classmethod
    def validate_selection(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one option must be selected")
        return v


class MCQSubmitRequest(BaseModel):
    """MCQ submission request."""
    answers: list[MCQAnswerSubmission]
    started_at: str | None = None  # ISO timestamp when user started


class MCQCorrectAnswerInfo(BaseModel):
    """Correct answer info (only shown if configured)."""
    question_id: str
    is_correct: bool
    correct_options: list[str] | None = None
    explanation: str | None = None


class MCQSubmitResponse(BaseModel):
    """MCQ submission response."""
    success: bool
    score: float
    total_possible: float
    passed: bool
    time_exceeded: bool = False
    answers: list[MCQCorrectAnswerInfo]
    anti_cheat_flags: list[str] = Field(default_factory=list)
    message: str = ""


class MCQResultResponse(BaseModel):
    """MCQ results response."""
    challenge_id: str
    score: float
    total_possible: float
    passed: bool
    passing_percentage: float
    questions: list[Dict[str, Any]]


class MCQConfigUpdateRequest(BaseModel):
    """MCQ configuration update request (admin)."""
    allow_multiple_answers: bool | None = None
    shuffle_options: bool | None = None
    show_correct_after_submit: bool | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    time_limit_seconds: int | None = Field(default=None, ge=10)
    points_per_question: float | None = Field(default=None, ge=0)
    penalty_per_wrong: float | None = Field(default=None, ge=0)
    partial_credit: bool | None = None
    passing_percentage: float | None = Field(default=None, ge=0, le=100)


class MCQQuestionCreateRequest(BaseModel):
    """Create MCQ question request (admin)."""
    question_text: str = Field(min_length=1)
    question_type: str = Field(pattern="^(single|multiple|true_false)$")
    explanation: str | None = None
    difficulty_weight: float = Field(default=1.0, ge=0.1, le=5.0)
    image_url: str | None = None
    code_snippet: str | None = None
    options: list[Dict[str, Any]] = Field(min_length=2)
    
    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[Dict[str, Any]], info) -> list[Dict[str, Any]]:
        if len(v) < 2:
            raise ValueError("At least 2 options required")
        
        # Check for at least one correct option
        correct_count = sum(1 for opt in v if opt.get("is_correct"))
        if correct_count == 0:
            raise ValueError("At least one option must be correct")
        
        # For single/true_false, only one correct
        question_type = info.data.get("question_type")
        if question_type in ("single", "true_false") and correct_count != 1:
            raise ValueError(f"{question_type} questions must have exactly 1 correct option")
        
        return v


# Dependencies

async def get_mcq_service():
    """Get MCQ service instance."""
    # In real implementation, this would inject database session and cache
    raise NotImplementedError("Service dependency to be wired")


# Endpoints

@router.get(
    "/{challenge_id}/mcq/questions",
    response_model=MCQQuestionsListResponse,
    summary="Get MCQ Questions",
    description="Get questions with user-specific shuffled options. Same user always sees same order.",
)
async def get_mcq_questions(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> MCQQuestionsListResponse:
    """Get MCQ questions for user with shuffled options."""
    try:
        user_id = UUID(current_user["id"])
        shuffled_questions = await mcq_service.get_questions_for_user(
            challenge_id, user_id
        )
        
        # Get challenge config
        challenge = await mcq_service._get_challenge(challenge_id)
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MCQ challenge not found"
            )
        
        # Convert to response format
        questions = []
        for sq in shuffled_questions:
            q = sq.question
            options = [
                MCQOptionResponse(
                    id=str(opt.id),
                    option_text=opt.option_text,
                    order_index=i
                )
                for i, opt in enumerate(sq.shuffled_options)
            ]
            
            questions.append(MCQQuestionResponse(
                id=str(q.id),
                question_text=q.question_text,
                question_type=q.question_type.value,
                difficulty_weight=float(q.difficulty_weight),
                order_index=q.order_index,
                image_url=q.image_url,
                code_snippet=q.code_snippet,
                options=options
            ))
        
        return MCQQuestionsListResponse(
            challenge_id=str(challenge_id),
            questions=questions,
            time_limit_seconds=challenge.time_limit_seconds,
            max_attempts=challenge.max_attempts,
            started_at=datetime.utcnow().isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/{challenge_id}/mcq/submit",
    response_model=MCQSubmitResponse,
    summary="Submit MCQ Answers",
    description="Submit answers with anti-cheat detection. Rate limited to 5 attempts per minute.",
    responses={
        429: {"description": "Rate limit exceeded or max attempts reached"},
        403: {"description": "Suspicious activity detected"},
    }
)
async def submit_mcq_answers(
    challenge_id: UUID,
    body: MCQSubmitRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> MCQSubmitResponse:
    """Submit MCQ answers."""
    try:
        user_id = UUID(current_user["id"])
        
        # Parse client info
        client_info = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "started_at": datetime.fromisoformat(body.started_at) if body.started_at else None,
        }
        
        # Convert answers format
        answers = [
            {
                "question_id": a.question_id,
                "selected_option_ids": a.selected_option_ids,
                "time_spent_seconds": a.time_spent_seconds
            }
            for a in body.answers
        ]
        
        # Submit
        result: SubmissionResult = await mcq_service.submit_answers(
            challenge_id, user_id, answers, client_info
        )
        
        if not result.success:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            if "not found" in result.message.lower():
                status_code = status.HTTP_404_NOT_FOUND
            raise HTTPException(
                status_code=status_code,
                detail=result.message
            )
        
        # Build answer details
        answer_details = []
        for qid, is_correct in result.correct_answers.items():
            detail = MCQCorrectAnswerInfo(
                question_id=str(qid),
                is_correct=is_correct
            )
            answer_details.append(detail)
        
        # Check for suspicious activity
        anti_cheat_flags = []
        if result.anti_cheat_result:
            anti_cheat_flags = result.anti_cheat_result.reasons
            
            # If highly suspicious, could return 403
            if result.anti_cheat_result.is_suspicious:
                # Log but still accept - admin can review later
                pass
        
        return MCQSubmitResponse(
            success=True,
            score=float(result.score),
            total_possible=float(result.total_possible),
            passed=result.passed,
            time_exceeded=result.time_exceeded,
            answers=answer_details,
            anti_cheat_flags=anti_cheat_flags,
            message=result.message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Submission failed: {str(e)}"
        )


@router.get(
    "/{challenge_id}/mcq/results",
    response_model=MCQResultResponse,
    summary="Get MCQ Results",
    description="Get detailed results including correct answers if show_correct_after_submit is enabled.",
)
async def get_mcq_results(
    challenge_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> MCQResultResponse:
    """Get MCQ results for user."""
    try:
        user_id = UUID(current_user["id"])
        results = await mcq_service.get_results(challenge_id, user_id)
        
        if "error" in results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=results["error"]
            )
        
        return MCQResultResponse(**results)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Admin Endpoints

@router.post(
    "/{challenge_id}/admin/mcq/questions",
    status_code=status.HTTP_201_CREATED,
    summary="Add MCQ Question (Admin)",
    description="Add a question with options to an MCQ challenge.",
)
async def add_mcq_question(
    challenge_id: UUID,
    body: MCQQuestionCreateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> Dict[str, Any]:
    """Add question to MCQ challenge (admin only)."""
    # Implementation would add question to challenge
    raise NotImplementedError("Admin endpoint to be implemented")


@router.patch(
    "/{challenge_id}/admin/mcq/config",
    summary="Update MCQ Config (Admin)",
    description="Update MCQ challenge configuration.",
)
async def update_mcq_config(
    challenge_id: UUID,
    body: MCQConfigUpdateRequest,
    current_user: Annotated[dict, Depends(require_admin)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> Dict[str, Any]:
    """Update MCQ configuration (admin only)."""
    # Implementation would update challenge config
    raise NotImplementedError("Admin endpoint to be implemented")


@router.delete(
    "/{challenge_id}/admin/mcq/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete MCQ Question (Admin)",
)
async def delete_mcq_question(
    challenge_id: UUID,
    question_id: UUID,
    current_user: Annotated[dict, Depends(require_admin)],
    mcq_service: Annotated[MCQService, Depends(get_mcq_service)],
) -> None:
    """Delete MCQ question (admin only)."""
    pass
