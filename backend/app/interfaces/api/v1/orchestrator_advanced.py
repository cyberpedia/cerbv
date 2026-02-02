"""
Advanced Orchestrator API Endpoints

API endpoints for:
- Attack-Defense (AD) games
- King of the Hill (KOTH)
- Programming Battles
- Hardware Lab reservations
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

from app.infrastructure.orchestrator.models_advanced import (
    EquipmentType,
    HardwareStatus,
    JudgeStatus,
    ProgrammingLanguage,
)

router = APIRouter(prefix="/orchestrator", tags=["Advanced Orchestrator"])


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

# --- Attack-Defense Models ---

class ADGameCreateRequest(BaseModel):
    challenge_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    team_ids: List[UUID]
    service_ids: List[str] = Field(..., min_length=1)
    tick_duration: int = Field(default=300, ge=60, le=600)
    total_ticks: int = Field(default=48, ge=1, le=200)


class ADGameResponse(BaseModel):
    id: UUID
    challenge_id: UUID
    name: str
    current_tick: int
    status: str
    started_at: Optional[datetime]
    config: dict


class ADFlagSubmitRequest(BaseModel):
    game_id: UUID
    flag: str = Field(..., min_length=10, max_length=255)


class ADFlagSubmitResponse(BaseModel):
    valid: bool
    points_awarded: int = 0
    service_id: Optional[str] = None
    victim_team_id: Optional[UUID] = None


class ADScoreboardEntry(BaseModel):
    team_id: UUID
    team_name: str
    sla_points: int
    offense_points: int
    defense_points: int
    total_score: int
    rank: int


class ADScoreboardResponse(BaseModel):
    game_id: UUID
    current_tick: int
    scores: List[ADScoreboardEntry]


# --- KOTH Models ---

class KOTHStartRequest(BaseModel):
    challenge_id: UUID
    team_ids: List[UUID]
    duration_minutes: int = Field(default=60, ge=10, le=480)


class KOTHKingResponse(BaseModel):
    challenge_id: UUID
    team_id: UUID
    team_name: str
    ownership_duration_seconds: float
    score: int


class KOTHLeaderboardEntry(BaseModel):
    team_id: UUID
    team_name: str
    score: int
    is_current_king: bool


class KOTHLeaderboardResponse(BaseModel):
    challenge_id: UUID
    entries: List[KOTHLeaderboardEntry]


# --- Programming Models ---

class ProgrammingSubmitRequest(BaseModel):
    problem_id: str = Field(..., min_length=1, max_length=100)
    language: ProgrammingLanguage
    code: str = Field(..., min_length=1, max_length=100000)


class ProgrammingSubmitResponse(BaseModel):
    submission_id: UUID
    status: JudgeStatus
    queued: bool = True


class ProgrammingResultResponse(BaseModel):
    submission_id: UUID
    status: JudgeStatus
    score: int
    max_score: int
    execution_time_ms: int
    memory_usage_mb: int
    test_results: List[dict]
    error_message: Optional[str] = None


# --- Hardware Models ---

class HardwareReserveRequest(BaseModel):
    equipment_id: UUID
    team_id: Optional[UUID] = None


class HardwareReserveResponse(BaseModel):
    session_id: UUID
    equipment_id: UUID
    status: HardwareStatus
    reserved_end_time: datetime
    position_in_queue: Optional[int] = None


class HardwareAccessResponse(BaseModel):
    session_id: UUID
    stream_url: str
    connection_string: str
    capabilities: List[str]
    expires_at: datetime


class HardwareSessionResponse(BaseModel):
    session_id: UUID
    equipment_id: UUID
    equipment_name: str
    status: HardwareStatus
    reserved_end_time: datetime
    stream_url: Optional[str]
    is_idle: bool


class HardwareListResponse(BaseModel):
    equipment: List[dict]
    available_count: int


# ============================================================================
# Helper Functions
# ============================================================================

def get_services(request: Request):
    """Get services from request state."""
    return (
        request.state.ad_manager,
        request.state.koth_manager,
        request.state.programming_judge,
        request.state.hardware_lab,
    )


# ============================================================================
# Attack-Defense Endpoints
# ============================================================================

@router.post("/ad/create", response_model=ADGameResponse, status_code=201)
async def create_ad_game(
    request: ADGameCreateRequest,
    req: Request,
):
    """Create a new Attack-Defense game."""
    ad_manager = req.state.ad_manager
    
    game = await ad_manager.create_game(
        challenge_id=request.challenge_id,
        name=request.name,
        team_ids=request.team_ids,
        service_ids=request.service_ids,
        tick_duration=request.tick_duration,
    )
    
    return ADGameResponse(
        id=game.id,
        challenge_id=game.challenge_id,
        name=game.name,
        current_tick=game.current_tick,
        status=game.status.value,
        started_at=game.started_at,
        config=game.config.to_dict(),
    )


@router.post("/ad/{game_id}/start")
async def start_ad_game(
    game_id: UUID,
    req: Request,
):
    """Start an AD game."""
    ad_manager = req.state.ad_manager
    success = await ad_manager.start_game(game_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to start game. Game may not exist or already be running.",
        )
    return {"status": "started", "game_id": str(game_id)}


@router.post("/ad/{game_id}/stop")
async def stop_ad_game(
    game_id: UUID,
    req: Request,
):
    """Stop an AD game."""
    ad_manager = req.state.ad_manager
    success = await ad_manager.stop_game(game_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to stop game.",
        )
    return {"status": "stopped", "game_id": str(game_id)}


@router.post("/ad/submit_flag", response_model=ADFlagSubmitResponse)
async def submit_ad_flag(
    request: ADFlagSubmitRequest,
    attacker_team_id: UUID,  # Would come from auth
    req: Request,
):
    """Submit a captured flag in an AD game."""
    ad_manager = req.state.ad_manager
    
    submission = await ad_manager.submit_flag(
        game_id=request.game_id,
        attacker_team_id=attacker_team_id,
        flag=request.flag,
    )
    
    return ADFlagSubmitResponse(
        valid=submission.is_valid,
        points_awarded=submission.points_awarded,
        service_id=submission.service_id if submission.is_valid else None,
        victim_team_id=submission.victim_team_id if submission.is_valid else None,
    )


@router.get("/ad/{game_id}/scoreboard", response_model=ADScoreboardResponse)
async def get_ad_scoreboard(
    game_id: UUID,
    req: Request,
):
    """Get real-time AD game scoreboard."""
    ad_manager = req.state.ad_manager
    scores = await ad_manager.get_scoreboard(game_id)
    
    entries = []
    for rank, score in enumerate(scores, 1):
        entries.append(ADScoreboardEntry(
            team_id=UUID(score["team_id"]),
            team_name=score["team_name"],
            sla_points=score["sla_points"],
            offense_points=score["offense_points"],
            defense_points=score["defense_points"],
            total_score=score["total_score"],
            rank=rank,
        ))
    
    game = ad_manager._active_games.get(game_id)
    current_tick = game.current_tick if game else 0
    
    return ADScoreboardResponse(
        game_id=game_id,
        current_tick=current_tick,
        scores=entries,
    )


# ============================================================================
# King of the Hill Endpoints
# ============================================================================

@router.post("/koth/start", status_code=201)
async def start_koth(
    request: KOTHStartRequest,
    req: Request,
):
    """Start a King of the Hill challenge."""
    koth_manager = req.state.koth_manager
    success = await koth_manager.start_koth(
        challenge_id=request.challenge_id,
        team_ids=request.team_ids,
        duration_minutes=request.duration_minutes,
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to start KOTH challenge.",
        )
    
    return {"status": "started", "challenge_id": str(request.challenge_id)}


@router.post("/koth/{challenge_id}/stop")
async def stop_koth(
    challenge_id: UUID,
    req: Request,
):
    """Stop a KOTH challenge."""
    koth_manager = req.state.koth_manager
    success = await koth_manager.stop_koth(challenge_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to stop KOTH challenge.",
        )
    return {"status": "stopped", "challenge_id": str(challenge_id)}


@router.get("/koth/{challenge_id}/king", response_model=KOTHKingResponse)
async def get_koth_king(
    challenge_id: UUID,
    req: Request,
):
    """Get the current king of the hill."""
    koth_manager = req.state.koth_manager
    king = await koth_manager.get_current_king(challenge_id)
    
    if not king:
        raise HTTPException(
            status_code=404,
            detail="No current king. KOTH may not be active.",
        )
    
    return KOTHKingResponse(
        challenge_id=UUID(king["challenge_id"]),
        team_id=UUID(king["team_id"]),
        team_name=king["team_name"],
        ownership_duration_seconds=king["ownership_duration_seconds"],
        score=king["score"],
    )


@router.get("/koth/{challenge_id}/leaderboard", response_model=KOTHLeaderboardResponse)
async def get_koth_leaderboard(
    challenge_id: UUID,
    req: Request,
):
    """Get KOTH leaderboard."""
    koth_manager = req.state.koth_manager
    scores = await koth_manager.get_leaderboard(challenge_id)
    
    entries = []
    for score in scores:
        entries.append(KOTHLeaderboardEntry(
            team_id=UUID(score["team_id"]),
            team_name=score["team_name"],
            score=score["score"],
            is_current_king=score.get("is_current_king", False),
        ))
    
    return KOTHLeaderboardResponse(
        challenge_id=challenge_id,
        entries=entries,
    )


@router.get("/koth/{challenge_id}/history")
async def get_koth_history(
    challenge_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    req: Request,
):
    """Get ownership change history."""
    koth_manager = req.state.koth_manager
    history = await koth_manager.get_ownership_history(challenge_id, limit)
    return {"challenge_id": str(challenge_id), "history": history}


# ============================================================================
# Programming Battle Endpoints
# ============================================================================

@router.post("/programming/submit", response_model=ProgrammingSubmitResponse)
async def submit_programming(
    request: ProgrammingSubmitRequest,
    req: Request,
    user_id: UUID,  # Would come from auth
    team_id: Optional[UUID] = None,  # Would come from auth
):
    """Submit code for programming challenge judging."""
    judge = req.state.programming_judge
    
    submission = await judge.submit(
        user_id=user_id,
        team_id=team_id,
        problem_id=request.problem_id,
        language=request.language,
        code=request.code,
    )
    
    return ProgrammingSubmitResponse(
        submission_id=submission.id,
        status=submission.status,
        queued=True,
    )


@router.get("/programming/submission/{submission_id}", response_model=ProgrammingResultResponse)
async def get_submission_result(
    submission_id: UUID,
    req: Request,
):
    """Get the result of a programming submission."""
    judge = req.state.programming_judge
    submission = await judge.get_submission(submission_id)
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return ProgrammingResultResponse(
        submission_id=submission.id,
        status=submission.status,
        score=submission.score,
        max_score=submission.max_score,
        execution_time_ms=submission.execution_time_ms,
        memory_usage_mb=submission.memory_usage_mb,
        test_results=submission.test_results,
        error_message=submission.error_message,
    )


@router.get("/programming/problem/{problem_id}/submissions")
async def get_problem_submissions(
    problem_id: str,
    req: Request,
    user_id: UUID,  # Would come from auth
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get user's submissions for a problem."""
    judge = req.state.programming_judge
    submissions = await judge.get_user_submissions(user_id, problem_id, limit)
    return {"problem_id": problem_id, "submissions": [s.to_dict() for s in submissions]}


@router.get("/programming/problem/{problem_id}/leaderboard")
async def get_problem_leaderboard(
    problem_id: str,
    req: Request,
    limit: int = Query(default=10, ge=1, le=100),
):
    """Get leaderboard for a programming problem."""
    judge = req.state.programming_judge
    leaderboard = await judge.get_problem_leaderboard(problem_id, limit)
    return {"problem_id": problem_id, "leaderboard": leaderboard}


# ============================================================================
# Hardware Lab Endpoints
# ============================================================================

@router.get("/hardware/equipment", response_model=HardwareListResponse)
async def list_hardware(
    equipment_type: Optional[EquipmentType] = None,
    req: Request,
):
    """List available hardware equipment."""
    lab = req.state.hardware_lab
    equipment = await lab.list_available_equipment(equipment_type)
    
    return HardwareListResponse(
        equipment=[eq.to_dict() for eq in equipment],
        available_count=len(equipment),
    )


@router.post("/hardware/reserve", response_model=HardwareReserveResponse)
async def reserve_hardware(
    request: HardwareReserveRequest,
    user_id: UUID,  # Would come from auth
    req: Request,
):
    """Reserve hardware equipment."""
    lab = req.state.hardware_lab
    
    try:
        session = await lab.reserve_equipment(
            equipment_id=request.equipment_id,
            user_id=user_id,
            team_id=request.team_id,
        )
        
        return HardwareReserveResponse(
            session_id=session.id,
            equipment_id=session.equipment_id,
            status=session.status,
            reserved_end_time=session.reserved_end_time,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hardware/session/{session_id}/access", response_model=HardwareAccessResponse)
async def grant_session_access(
    session_id: UUID,
    req: Request,
):
    """Get access to a reserved session (starts video stream, connects to hardware)."""
    lab = req.state.hardware_lab
    
    try:
        access_info = await lab.grant_session_access(session_id)
        
        return HardwareAccessResponse(
            session_id=UUID(access_info["session_id"]),
            stream_url=access_info["stream_url"],
            connection_string=access_info["connection_string"],
            capabilities=access_info["capabilities"],
            expires_at=datetime.fromisoformat(access_info["expires_at"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hardware/session/{session_id}/heartbeat")
async def send_heartbeat(
    session_id: UUID,
    req: Request,
):
    """Send heartbeat to keep session active."""
    lab = req.state.hardware_lab
    success = await lab.send_heartbeat(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok"}


@router.post("/hardware/session/{session_id}/extend")
async def extend_session(
    session_id: UUID,
    req: Request,
    additional_minutes: int = Query(default=30, ge=1, le=120),
):
    """Extend a hardware session."""
    lab = req.state.hardware_lab
    success = await lab.extend_session(session_id, additional_minutes)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to extend session.",
        )
    return {"status": "extended", "additional_minutes": additional_minutes}


@router.post("/hardware/session/{session_id}/end")
async def end_session(
    session_id: UUID,
    req: Request,
):
    """End a hardware session."""
    lab = req.state.hardware_lab
    success = await lab.end_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ended"}


@router.get("/hardware/sessions/my", response_model=List[HardwareSessionResponse])
async def get_my_sessions(
    req: Request,
    user_id: UUID,  # Would come from auth
    active_only: bool = True,
):
    """Get user's hardware sessions."""
    lab = req.state.hardware_lab
    sessions = await lab.list_user_sessions(user_id, active_only)
    
    results = []
    for session in sessions:
        equipment = await lab.get_equipment(session.equipment_id)
        results.append(HardwareSessionResponse(
            session_id=session.id,
            equipment_id=session.equipment_id,
            equipment_name=equipment.name if equipment else "Unknown",
            status=session.status,
            reserved_end_time=session.reserved_end_time,
            stream_url=session.stream_url,
            is_idle=session.is_idle(lab.config.idle_timeout_seconds),
        ))
    
    return results


@router.get("/hardware/equipment/{equipment_id}/queue")
async def get_equipment_queue(
    equipment_id: UUID,
    req: Request,
):
    """Get the reservation queue for equipment."""
    lab = req.state.hardware_lab
    queue = await lab.get_session_queue(equipment_id)
    return {"equipment_id": str(equipment_id), "queue": queue}


@router.post("/hardware/equipment/{equipment_id}/status")
async def set_equipment_status(
    equipment_id: UUID,
    status: HardwareStatus,
    req: Request,
):
    """Set equipment status (maintenance, offline, etc.)."""
    lab = req.state.hardware_lab
    success = await lab.set_equipment_status(equipment_id, status)
    
    if not success:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return {"status": "updated"}
