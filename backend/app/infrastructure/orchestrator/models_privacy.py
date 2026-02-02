"""
Privacy and GDPR database models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class PrivacyMode(str, Enum):
    """Privacy mode for the competition."""
    FULL = "full"
    ANONYMOUS = "anonymous"
    STEALTH = "stealth"
    DELAYED = "delayed"


class ExportStatus(str, Enum):
    """Status of data export request."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"


class DeletionStatus(str, Enum):
    """Status of deletion request."""
    PENDING = "pending"
    VERIFIED = "verified"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class PlatformPrivacySettings:
    """
    Platform-wide privacy settings.
    This would typically be stored in a settings/configuration table.
    """
    id: UUID = field(default_factory=uuid4)
    privacy_mode: PrivacyMode = PrivacyMode.FULL
    delayed_minutes: int = 15
    reveal_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    updated_by: Optional[UUID] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "privacy_mode": self.privacy_mode.value,
            "delayed_minutes": self.delayed_minutes,
            "reveal_time": self.reveal_time.isoformat() if self.reveal_time else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_by": str(self.updated_by) if self.updated_by else None,
        }


@dataclass
class UserDataExport:
    """
    Tracks user data export requests.
    """
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    status: ExportStatus = ExportStatus.PENDING
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "file_path": self.file_path,
            "download_url": self.download_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class DeletionRequest:
    """
    Tracks user account deletion requests with grace period.
    """
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    status: DeletionStatus = DeletionStatus.PENDING
    verification_hash: str = ""
    grace_end: Optional[datetime] = None
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "verification_hash": self.verification_hash[:8] + "..." if self.verification_hash else None,
            "grace_end": self.grace_end.isoformat() if self.grace_end else None,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class RetentionPolicy:
    """
    Configurable retention policy for data types.
    """
    id: UUID = field(default_factory=uuid4)
    data_type: str = ""  # session_logs, solves, audit_logs, user_data
    retention_days: Optional[int] = None  # How long to keep
    anonymize_after: Optional[int] = None  # Days after which to anonymize (remove PII)
    delete_after: Optional[int] = None  # Days after which to hard delete
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "data_type": self.data_type,
            "retention_days": self.retention_days,
            "anonymize_after": self.anonymize_after,
            "delete_after": self.delete_after,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PrivacyAuditLog:
    """
    Audit log for privacy-related actions.
    """
    id: UUID = field(default_factory=uuid4)
    action: str = ""  # privacy_mode_changed, export_requested, deletion_requested, etc.
    actor_id: Optional[UUID] = None  # User who performed action
    target_id: Optional[UUID] = None  # Affected user/resource
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "action": self.action,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "target_id": str(self.target_id) if self.target_id else None,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DelayedDisclosure:
    """
    Tracks delayed scoreboard disclosures.
    """
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    team_id: UUID = field(default_factory=uuid4)
    scheduled_reveal: datetime = field(default_factory=datetime.utcnow)
    revealed: bool = False
    revealed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "team_id": str(self.team_id),
            "scheduled_reveal": self.scheduled_reveal.isoformat(),
            "revealed": self.revealed,
            "revealed_at": self.revealed_at.isoformat() if self.revealed_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class UserSkillRadar:
    """
    Cached user skill profile by category.
    Only stores derived metrics, never individual solve data.
    """
    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    category_scores: Dict[str, float] = field(default_factory=dict)  # category -> score 0-100
    overall_score: float = 0.0
    strong_categories: List[str] = field(default_factory=list)
    weak_categories: List[str] = field(default_factory=list)
    solve_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "category_scores": self.category_scores,
            "overall_score": self.overall_score,
            "strong_categories": self.strong_categories,
            "weak_categories": self.weak_categories,
            "solve_count": self.solve_count,
            "last_updated": self.last_updated.isoformat(),
        }
