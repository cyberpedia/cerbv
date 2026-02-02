"""
Cerberus CTF Platform - User Domain Entities
Pure domain objects with no external dependencies
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class UserRole(str, Enum):
    """User role enumeration with hierarchical permissions."""
    SUPER_ADMIN = "super_admin"  # Platform owner, can manage admins
    ADMIN = "admin"              # CTF organizer, full challenge access
    ORGANIZER = "organizer"      # Can create/edit challenges
    PLAYER = "player"            # Standard participant
    BANNED = "banned"            # Suspended account


@dataclass
class UserId:
    """Value object for user identifier."""
    value: UUID = field(default_factory=uuid4)
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __hash__(self) -> int:
        return hash(self.value)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, UserId):
            return self.value == other.value
        return False


@dataclass
class Email:
    """Value object for email with validation."""
    value: str
    
    def __post_init__(self) -> None:
        if not self._is_valid_email(self.value):
            raise ValueError(f"Invalid email format: {self.value}")
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value.lower())
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Email):
            return self.value.lower() == other.value.lower()
        return False


@dataclass
class Username:
    """Value object for username with validation."""
    value: str
    
    MIN_LENGTH = 3
    MAX_LENGTH = 50
    
    def __post_init__(self) -> None:
        if not self._is_valid_username(self.value):
            raise ValueError(
                f"Username must be {self.MIN_LENGTH}-{self.MAX_LENGTH} characters, "
                "alphanumeric with underscores and hyphens only"
            )
    
    @staticmethod
    def _is_valid_username(username: str) -> bool:
        """Validate username format."""
        import re
        if not (Username.MIN_LENGTH <= len(username) <= Username.MAX_LENGTH):
            return False
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, username))
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value.lower())


@dataclass
class PasswordHash:
    """Value object for password hash (never stores plaintext)."""
    value: str
    
    def __post_init__(self) -> None:
        if not self.value.startswith("$argon2"):
            raise ValueError("Password must be hashed with Argon2")
    
    def __str__(self) -> str:
        return "[REDACTED]"
    
    def __repr__(self) -> str:
        return "PasswordHash([REDACTED])"


@dataclass
class User:
    """
    User aggregate root.
    
    Contains all user-related business logic and invariants.
    """
    id: UserId
    username: Username
    email: Email
    password_hash: PasswordHash
    role: UserRole
    
    # Profile
    display_name: Optional[str] = None
    country_code: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Team association
    team_id: Optional[UUID] = None
    
    # Security state
    email_verified: bool = False
    two_factor_enabled: bool = False
    two_factor_secret: Optional[str] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    def is_active(self) -> bool:
        """Check if user account is active."""
        return (
            self.deleted_at is None
            and self.role != UserRole.BANNED
            and not self.is_locked()
        )
    
    def is_locked(self) -> bool:
        """Check if account is temporarily locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN)
    
    def is_super_admin(self) -> bool:
        """Check if user is super admin."""
        return self.role == UserRole.SUPER_ADMIN
    
    def can_manage_challenges(self) -> bool:
        """Check if user can create/edit challenges."""
        return self.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ORGANIZER)
    
    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 30) -> None:
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
    
    def record_successful_login(self) -> None:
        """Record a successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.utcnow()
    
    def verify_email(self) -> None:
        """Mark email as verified."""
        self.email_verified = True
        self.updated_at = datetime.utcnow()
    
    def enable_two_factor(self, secret: str) -> None:
        """Enable two-factor authentication."""
        self.two_factor_enabled = True
        self.two_factor_secret = secret
        self.updated_at = datetime.utcnow()
    
    def disable_two_factor(self) -> None:
        """Disable two-factor authentication."""
        self.two_factor_enabled = False
        self.two_factor_secret = None
        self.updated_at = datetime.utcnow()
    
    def change_role(self, new_role: UserRole, changed_by: "User") -> None:
        """
        Change user role with authorization check.
        
        Args:
            new_role: The new role to assign
            changed_by: The user making the change
            
        Raises:
            PermissionError: If the changing user lacks permission
        """
        # Only super admins can create other admins
        if new_role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            if not changed_by.is_super_admin():
                raise PermissionError("Only super admins can assign admin roles")
        
        # Admins can assign organizer/player roles
        if not changed_by.is_admin():
            raise PermissionError("Only admins can change user roles")
        
        self.role = new_role
        self.updated_at = datetime.utcnow()
    
    def soft_delete(self) -> None:
        """Soft delete the user account."""
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def restore(self) -> None:
        """Restore a soft-deleted account."""
        self.deleted_at = None
        self.updated_at = datetime.utcnow()


@dataclass
class Team:
    """Team aggregate for team-based CTFs."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    invite_code: str = ""
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        if not self.invite_code:
            import secrets
            self.invite_code = secrets.token_urlsafe(24)
    
    def regenerate_invite_code(self) -> str:
        """Generate a new invite code."""
        import secrets
        self.invite_code = secrets.token_urlsafe(24)
        self.updated_at = datetime.utcnow()
        return self.invite_code
    
    def is_active(self) -> bool:
        """Check if team is active."""
        return self.deleted_at is None
