"""
GDPR Compliance Service for data export, deletion, and retention policies.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import csv
from io import StringIO


class DeletionStatus(str, Enum):
    """Status of a deletion request."""
    PENDING = "pending"
    VERIFIED = "verified"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExportStatus(str, Enum):
    """Status of a data export request."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class DataExportRequest:
    """Represents a user data export request."""
    id: UUID
    user_id: UUID
    status: ExportStatus
    file_path: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "download_url": self.download_url,
        }


@dataclass
class DeletionRequest:
    """Represents a user account deletion request."""
    id: UUID
    user_id: UUID
    status: DeletionStatus
    grace_end: datetime
    verification_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status.value,
            "grace_end": self.grace_end.isoformat(),
            "verification_hash": self.verification_hash[:8] + "...",  # Truncated for display
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "reason": self.reason,
            "days_remaining": max(0, (self.grace_end - datetime.now(timezone.utc)).days),
        }


class RetentionPolicy:
    """
    Configurable retention policies for different data types.
    """
    
    def __init__(self):
        self.policies = {
            "session_logs": {
                "retention_days": 30,
                "anonymize_after": None,
                "delete_after": 90,
            },
            "solves": {
                "retention_days": 730,  # 2 years
                "anonymize_after": 180,  # 6 months - remove user association
                "delete_after": None,
            },
            "audit_logs": {
                "retention_days": 2555,  # 7 years
                "anonymize_after": None,
                "delete_after": None,
            },
            "user_data": {
                "retention_days": None,  # Until deleted
                "anonymize_after": None,
                "delete_after": None,
            },
        }
    
    def get_policy(self, data_type: str) -> Dict[str, Optional[int]]:
        """Get retention policy for a data type."""
        return self.policies.get(data_type, {
            "retention_days": None,
            "anonymize_after": None,
            "delete_after": None,
        })
    
    def set_policy(
        self, 
        data_type: str, 
        retention_days: Optional[int] = None,
        anonymize_after: Optional[int] = None,
        delete_after: Optional[int] = None
    ):
        """Set a retention policy for a data type."""
        self.policies[data_type] = {
            "retention_days": retention_days,
            "anonymize_after": anonymize_after,
            "delete_after": delete_after,
        }


class GDPRService:
    """
    Service for GDPR compliance - handles data exports, deletions, and retention.
    """
    
    # Grace period before deletion is enforced
    DELETION_GRACE_DAYS = 30
    
    # Export file expiration
    EXPORT_EXPIRY_DAYS = 7
    
    def __init__(
        self,
        session,
        storage_path: str = "/tmp/exports",
        base_url: str = "https://cerb.example.com"
    ):
        self.session = session
        self.storage_path = storage_path
        self.base_url = base_url
        self.retention = RetentionPolicy()
    
    def request_data_export(self, user_id: UUID) -> DataExportRequest:
        """
        Create a new data export request for a user.
        
        Args:
            user_id: The user's UUID
            
        Returns:
            DataExportRequest with request details
        """
        request = DataExportRequest(
            id=uuid4(),
            user_id=user_id,
            status=ExportStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.EXPORT_EXPIRY_DAYS),
        )
        
        # Store in database (simplified - in real implementation, save to DB)
        # self.session.add(request)
        # self.session.commit()
        
        return request
    
    def process_data_export(self, request_id: UUID) -> DataExportRequest:
        """
        Process a data export request - gathers all user data.
        
        Args:
            request_id: The export request ID
            
        Returns:
            Updated DataExportRequest with file path
        """
        # In real implementation: fetch from DB
        # request = self.session.query(DataExportRequest).filter_by(id=request_id).first()
        
        request.status = ExportStatus.PROCESSING
        
        # Gather user data
        export_data = {
            "export_metadata": {
                "request_id": str(request_id),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "gdpr_compliant": True,
            },
            "user_profile": self._get_user_profile(request.user_id),
            "solves": self._get_user_solves(request.user_id),
            "submissions": self._get_user_submissions(request.user_id),
            "hints_used": self._get_user_hints(request.user_id),
            "session_history": self._get_user_sessions(request.user_id),
        }
        
        # Write JSON export
        json_path = f"{self.storage_path}/export_{request_id}.json"
        self._write_json_export(json_path, export_data)
        
        # Write CSV summary
        csv_path = f"{self.storage_path}/export_{request_id}_summary.csv"
        self._write_csv_export(csv_path, export_data)
        
        request.file_path = json_path
        request.status = ExportStatus.READY
        request.download_url = f"{self.base_url}/api/v1/user/export/{request_id}/download"
        
        # Save to database
        # self.session.commit()
        
        return request
    
    def _get_user_profile(self, user_id: UUID) -> Dict[str, Any]:
        """Get user export."""
        # In real implementation: profile data for query database
        return {
            "user_id": str(user_id),
            "email": "***redacted***",
            "username": "***redacted***",
            "created_at": "***redacted***",
            "profile": {},
        }
    
    def _get_user_solves(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get solve history for export."""
        # In real implementation: query solves table
        return []
    
    def _get_user_submissions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get submission history for export."""
        # In real implementation: query submissions table
        return []
    
    def _get_user_hints(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get hint usage for export."""
        # In real implementation: query hints usage table
        return []
    
    def _get_user_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get session history for export."""
        # In real implementation: query sessions table
        return []
    
    def _write_json_export(self, path: str, data: Dict[str, Any]):
        """Write JSON export file."""
        # In real implementation: write to file system
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _write_csv_export(self, path: str, data: Dict[str, Any]):
        """Write CSV summary export file."""
        # Create CSV from solves
        solves = data.get("solves", [])
        
        if not solves:
            return
        
        output = StringIO()
        if solves:
            writer = csv.DictWriter(output, fieldnames=solves[0].keys())
            writer.writeheader()
            writer.writerows(solves)
        
        with open(path, 'w') as f:
            f.write(output.getvalue())
    
    def request_account_deletion(
        self, 
        user_id: UUID,
        verification_email: str,
        reason: Optional[str] = None
    ) -> DeletionRequest:
        """
        Create a new deletion request with grace period.
        
        Args:
            user_id: The user's UUID
            verification_email: Email for verification
            reason: Optional reason for deletion
            
        Returns:
            DeletionRequest with verification details
        """
        # Generate verification hash
        hash_input = f"{user_id}:{verification_email}:{datetime.now(timezone.utc).isoformat()}"
        verification_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        request = DeletionRequest(
            id=uuid4(),
            user_id=user_id,
            status=DeletionStatus.PENDING,
            grace_end=datetime.now(timezone.utc) + timedelta(days=self.DELETION_GRACE_DAYS),
            verification_hash=verification_hash,
            reason=reason,
        )
        
        # Store in database
        # self.session.add(request)
        # self.session.commit()
        
        return request
    
    def verify_deletion_request(self, request_id: UUID, verification_hash: str) -> bool:
        """
        Verify a deletion request's verification hash.
        
        Args:
            request_id: The deletion request ID
            verification_hash: Hash provided by user
            
        Returns:
            True if verification successful
        """
        # In real implementation: query database
        # request = self.session.query(DeletionRequest).filter_by(id=request_id).first()
        # return request and request.verification_hash == verification_hash
        return False
    
    def cancel_deletion_request(self, request_id: UUID, user_id: UUID) -> bool:
        """
        Cancel a deletion request within grace period.
        
        Args:
            request_id: The deletion request ID
            user_id: The user's ID (for authorization)
            
        Returns:
            True if cancelled successfully
        """
        # In real implementation: query and update database
        return True
    
    def process_deletion(self, request_id: UUID) -> DeletionRequest:
        """
        Process a deletion request after grace period.
        Performs soft delete followed by hard delete/anonymization.
        
        Args:
            request_id: The deletion request ID
            
        Returns:
            Updated DeletionRequest
        """
        # In real implementation: query database
        # request = self.session.query(DeletionRequest).filter_by(id=request_id).first()
        
        request.status = DeletionStatus.PROCESSING
        
        # Step 1: Anonymize solves (keep stats, remove user association)
        self._anonymize_user_solves(request.user_id)
        
        # Step 2: Soft delete user profile
        self._soft_delete_user(request.user_id)
        
        # Step 3: Schedule hard delete for later (or perform immediately)
        # For GDPR: we typically keep anonymized data for stats
        
        request.status = DeletionStatus.COMPLETED
        request.completed_at = datetime.now(timezone.utc)
        
        # self.session.commit()
        
        return request
    
    def _anonymize_user_solves(self, user_id: UUID):
        """
        Anonymize user's solve data - set user_id to NULL, keep stats.
        This maintains competition integrity while removing PII.
        """
        # In real implementation: UPDATE solves SET user_id = NULL WHERE user_id = ?
        # Keep: challenge_id, solved_at, points, but remove who solved it
        pass
    
    def _soft_delete_user(self, user_id: UUID):
        """
        Soft delete user account - mark as deleted, remove PII.
        """
        # In real implementation: UPDATE users SET deleted = true, email = NULL, username = NULL
        pass
    
    def get_retention_summary(self) -> Dict[str, Any]:
        """
        Get summary of current retention policies and data counts.
        
        Returns:
            Dictionary with retention summary
        """
        return {
            "policies": self.retention.policies,
            "expiring_soon": {
                "session_logs": 0,
                "audit_logs": 0,
            },
            "data_subjects_pending_deletion": 0,
            "exports_pending": 0,
        }
    
    def run_retention_check(self) -> Dict[str, int]:
        """
        Run daily retention check - anonymize and delete old data.
        
        Returns:
            Dictionary with counts of processed items
        """
        results = {
            "anonymized_solves": 0,
            "deleted_sessions": 0,
            "archived_audit_logs": 0,
            "failed": 0,
        }
        
        # Get policy for solves
        solve_policy = self.retention.get_policy("solves")
        
        if solve_policy.get("anonymize_after"):
            # Anonymize solves older than anonymize_after days
            cutoff = datetime.now(timezone.utc) - timedelta(days=solve_policy["anonymize_after"])
            # results["anonymized_solves"] = self._anonymize_old_solves(cutoff)
            pass
        
        # Get policy for sessions
        session_policy = self.retention.get_policy("session_logs")
        
        if session_policy.get("delete_after"):
            # Delete sessions older than delete_after days
            cutoff = datetime.now(timezone.utc) - timedelta(days=session_policy["delete_after"])
            # results["deleted_sessions"] = self._delete_old_sessions(cutoff)
            pass
        
        return results
    
    def _anonymize_old_solves(self, cutoff: datetime) -> int:
        """Anonymize solves older than cutoff date."""
        # In real implementation: UPDATE solves SET user_id = NULL WHERE solved_at < cutoff
        return 0
    
    def _delete_old_sessions(self, cutoff: datetime) -> int:
        """Delete sessions older than cutoff date."""
        # In real implementation: DELETE FROM sessions WHERE created_at < cutoff
        return 0
