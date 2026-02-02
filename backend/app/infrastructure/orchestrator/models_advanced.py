"""
Advanced Challenge Models - Data classes for AD, KOTH, Programming Battles, and Hardware Labs
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


# ============================================================================
# Attack-Defense (AD) Models
# ============================================================================

class ADGameStatus(str, Enum):
    """AD game lifecycle statuses."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class ADFlagStatus(str, Enum):
    """Status of a flag in AD game."""
    ACTIVE = "active"
    CAPTURED = "captured"
    EXPIRED = "expired"


@dataclass
class ADGameConfig:
    """Configuration for an AD game."""
    tick_duration: int = 300  # seconds (5 minutes)
    total_ticks: int = 48  # 4 hours total (48 * 5min)
    flag_lifetime_ticks: int = 3  # flags valid for 3 ticks
    sla_points_per_tick: int = 100
    offense_points_per_flag: int = 500
    defense_points_per_flag: int = 100
    team_count: int = 0
    service_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_duration": self.tick_duration,
            "total_ticks": self.total_ticks,
            "flag_lifetime_ticks": self.flag_lifetime_ticks,
            "sla_points_per_tick": self.sla_points_per_tick,
            "offense_points_per_flag": self.offense_points_per_flag,
            "defense_points_per_flag": self.defense_points_per_flag,
            "team_count": self.team_count,
            "service_ids": self.service_ids,
        }


@dataclass
class ADGame:
    """Represents an active Attack-Defense game."""
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    name: str = ""
    config: ADGameConfig = field(default_factory=ADGameConfig)
    current_tick: int = 0
    status: ADGameStatus = ADGameStatus.PENDING
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "name": self.name,
            "config": self.config.to_dict(),
            "current_tick": self.current_tick,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ADFlag:
    """Represents a flag in an AD game."""
    id: UUID = field(default_factory=uuid4)
    game_id: UUID = field(default_factory=uuid4)
    tick: int = 0
    service_id: str = ""
    team_id: UUID = field(default_factory=uuid4)
    flag_hash: str = ""
    status: ADFlagStatus = ADFlagStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "game_id": str(self.game_id),
            "tick": self.tick,
            "service_id": self.service_id,
            "team_id": str(self.team_id),
            "flag_hash": self.flag_hash,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ADSubmission:
    """Represents a flag submission in an AD game."""
    id: UUID = field(default_factory=uuid4)
    game_id: UUID = field(default_factory=uuid4)
    attacker_team_id: UUID = field(default_factory=uuid4)
    victim_team_id: UUID = field(default_factory=uuid4)
    service_id: str = ""
    flag_hash: str = ""
    tick: int = 0
    is_valid: bool = False
    points_awarded: int = 0
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "game_id": str(self.game_id),
            "attacker_team_id": str(self.attacker_team_id),
            "victim_team_id": str(self.victim_team_id),
            "service_id": self.service_id,
            "flag_hash": self.flag_hash,
            "tick": self.tick,
            "is_valid": self.is_valid,
            "points_awarded": self.points_awarded,
            "submitted_at": self.submitted_at.isoformat(),
        }


@dataclass
class ADScore:
    """Represents team score at a specific tick."""
    team_id: UUID = field(default_factory=uuid4)
    game_id: UUID = field(default_factory=uuid4)
    tick: int = 0
    sla_points: int = 0
    offense_points: int = 0
    defense_points: int = 0
    total_score: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": str(self.team_id),
            "game_id": str(self.game_id),
            "tick": self.tick,
            "sla_points": self.sla_points,
            "offense_points": self.offense_points,
            "defense_points": self.defense_points,
            "total_score": self.total_score,
            "last_updated": self.last_updated.isoformat(),
        }


# ============================================================================
# King of the Hill (KOTH) Models
# ============================================================================

class KOTHStatus(str, Enum):
    """KOTH challenge status."""
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"


@dataclass
class KOTHOwnership:
    """Represents current ownership of a KOTH box."""
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    team_id: Optional[UUID] = None
    owned_since: Optional[datetime] = None
    last_checked: datetime = field(default_factory=datetime.utcnow)
    proof_token: str = ""
    is_contested: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "owned_since": self.owned_since.isoformat() if self.owned_since else None,
            "last_checked": self.last_checked.isoformat(),
            "proof_token": self.proof_token,
            "is_contested": self.is_contested,
        }
    
    def duration_seconds(self) -> Optional[float]:
        """Get duration of ownership in seconds."""
        if self.owned_since and self.team_id:
            return (self.last_checked - self.owned_since).total_seconds()
        return None


@dataclass
class KOTHOwnershipLog:
    """Log of ownership changes."""
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    previous_team_id: Optional[UUID] = None
    new_team_id: Optional[UUID] = None
    change_time: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""  # e.g., "captured", "disconnect", "timeout"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "previous_team_id": str(self.previous_team_id) if self.previous_team_id else None,
            "new_team_id": str(self.new_team_id) if self.new_team_id else None,
            "change_time": self.change_time.isoformat(),
            "reason": self.reason,
        }


# ============================================================================
# Programming Battle Models
# ============================================================================

class ProgrammingLanguage(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    CPP = "cpp"
    JAVA = "java"
    RUST = "rust"
    GO = "go"
    JAVASCRIPT = "javascript"
    RUBY = "ruby"


class JudgeStatus(str, Enum):
    """Status of a programming submission."""
    PENDING = "pending"
    COMPILING = "compiling"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"


@dataclass
class TestCase:
    """A test case for a programming problem."""
    id: UUID = field(default_factory=uuid4)
    problem_id: str = ""
    input_data: str = ""
    expected_output: str = ""
    is_sample: bool = False
    points: int = 1
    time_limit_ms: int = 1000
    memory_limit_mb: int = 64
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "problem_id": self.problem_id,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "is_sample": self.is_sample,
            "points": self.points,
            "time_limit_ms": self.time_limit_ms,
            "memory_limit_mb": self.memory_limit_mb,
        }


@dataclass
class ProgrammingSubmission:
    """Represents a programming code submission."""
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    team_id: Optional[UUID] = None
    problem_id: str = ""
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    code: str = ""
    status: JudgeStatus = JudgeStatus.PENDING
    score: int = 0
    max_score: int = 0
    execution_time_ms: int = 0
    memory_usage_mb: int = 0
    error_message: Optional[str] = None
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    judged_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "problem_id": self.problem_id,
            "language": self.language.value,
            "code": self.code,
            "status": self.status.value,
            "score": self.score,
            "max_score": self.max_score,
            "execution_time_ms": self.execution_time_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "error_message": self.error_message,
            "test_results": self.test_results,
            "submitted_at": self.submitted_at.isoformat(),
            "judged_at": self.judged_at.isoformat() if self.judged_at else None,
        }


@dataclass
class TestResult:
    """Result of running a single test case."""
    test_case_id: UUID = field(default_factory=uuid4)
    passed: bool = False
    execution_time_ms: int = 0
    memory_usage_mb: int = 0
    output: str = ""
    expected_output: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_case_id": str(self.test_case_id),
            "passed": self.passed,
            "execution_time_ms": self.execution_time_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "output": self.output,
            "expected_output": self.expected_output,
            "error": self.error,
        }


# ============================================================================
# Hardware Lab Models
# ============================================================================

class HardwareStatus(str, Enum):
    """Status of hardware equipment."""
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class EquipmentType(str, Enum):
    """Types of hardware equipment."""
    OSCILLOSCOPE = "oscilloscope"
    LOGIC_ANALYZER = "logic_analyzer"
    SDR = "sdr"  # Software Defined Radio
    MULTIMETER = "multimeter"
    POWER_SUPPLY = "power_supply"
    WORKBENCH = "workbench"


@dataclass
class HardwareEquipment:
    """Represents a piece of hardware equipment."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    equipment_type: EquipmentType = EquipmentType.OSCILLOSCOPE
    status: HardwareStatus = HardwareStatus.AVAILABLE
    connection_string: str = ""  # USB/IP address, network URL, etc.
    capabilities: List[str] = field(default_factory=list)
    current_session_id: Optional[UUID] = None
    maintenance_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "equipment_type": self.equipment_type.value,
            "status": self.status.value,
            "connection_string": self.connection_string,
            "capabilities": self.capabilities,
            "current_session_id": str(self.current_session_id) if self.current_session_id else None,
            "maintenance_mode": self.maintenance_mode,
        }


@dataclass
class HardwareSession:
    """Represents a reservation session for hardware equipment."""
    id: UUID = field(default_factory=uuid4)
    equipment_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    team_id: Optional[UUID] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    reserved_end_time: datetime = field(default_factory=datetime.utcnow)
    status: HardwareStatus = HardwareStatus.RESERVED
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    stream_url: Optional[str] = None
    access_granted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "equipment_id": str(self.equipment_id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "reserved_end_time": self.reserved_end_time.isoformat(),
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "stream_url": self.stream_url,
            "access_granted": self.access_granted,
        }
    
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status in [HardwareStatus.RESERVED, HardwareStatus.IN_USE]
    
    def is_idle(self, idle_threshold_seconds: int = 900) -> bool:
        """Check if session is idle (no heartbeat)."""
        if not self.is_active():
            return False
        idle_duration = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return idle_duration > idle_threshold_seconds


@dataclass
class HardwareConfig:
    """Configuration for hardware equipment."""
    session_duration_minutes: int = 120  # 2 hours
    idle_timeout_seconds: int = 900  # 15 minutes
    max_concurrent_sessions_per_user: int = 1
    reset_script: Optional[str] = None
    safety_limits: Dict[str, float] = field(default_factory=lambda: {
        "max_voltage": 5.0,
        "max_current_ma": 500.0,
    })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_duration_minutes": self.session_duration_minutes,
            "idle_timeout_seconds": self.idle_timeout_seconds,
            "max_concurrent_sessions_per_user": self.max_concurrent_sessions_per_user,
            "reset_script": self.reset_script,
            "safety_limits": self.safety_limits,
        }
