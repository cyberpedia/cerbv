"""
Cerberus CTF Platform - Security Domain Services
Password hashing, flag verification, and security utilities
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Optional, Tuple

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError


@dataclass
class PasswordPolicy:
    """Password policy configuration."""
    min_length: int = 12
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"


class PasswordService:
    """
    Password hashing service using Argon2id.
    
    Argon2id is the recommended algorithm for password hashing,
    providing resistance against both GPU and side-channel attacks.
    """
    
    def __init__(
        self,
        time_cost: int = 2,
        memory_cost: int = 65536,  # 64 MB
        parallelism: int = 4,
    ):
        """
        Initialize password hasher with secure defaults.
        
        Args:
            time_cost: Number of iterations
            memory_cost: Memory usage in KiB
            parallelism: Number of parallel threads
        """
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,  # Argon2id
        )
        self._policy = PasswordPolicy()
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2id.
        
        Args:
            password: Plain text password
            
        Returns:
            Argon2id hash string
        """
        return self._hasher.hash(password)
    
    def verify_password(self, password: str, hash_value: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            hash_value: Stored Argon2id hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            self._hasher.verify(hash_value, password)
            return True
        except VerifyMismatchError:
            return False
    
    def needs_rehash(self, hash_value: str) -> bool:
        """
        Check if a hash needs to be rehashed with updated parameters.
        
        Args:
            hash_value: Existing hash to check
            
        Returns:
            True if rehashing is recommended
        """
        return self._hasher.check_needs_rehash(hash_value)
    
    def validate_password(self, password: str) -> Tuple[bool, list[str]]:
        """
        Validate password against policy.
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []
        
        if len(password) < self._policy.min_length:
            errors.append(f"Password must be at least {self._policy.min_length} characters")
        
        if self._policy.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self._policy.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self._policy.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if self._policy.require_special:
            if not any(c in self._policy.special_chars for c in password):
                errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors


class FlagService:
    """
    Flag verification service using HMAC-SHA256.
    
    Provides secure flag generation and verification with
    timing-attack resistant comparison.
    """
    
    def __init__(self, secret_key: str, prefix: str = "CERB{", suffix: str = "}"):
        """
        Initialize flag service.
        
        Args:
            secret_key: Secret key for HMAC operations
            prefix: Flag prefix (e.g., "CERB{")
            suffix: Flag suffix (e.g., "}")
        """
        self._secret_key = secret_key.encode()
        self._prefix = prefix
        self._suffix = suffix
    
    def generate_static_flag(self, challenge_id: str, flag_content: str) -> str:
        """
        Generate a static flag with proper formatting.
        
        Args:
            challenge_id: Challenge identifier
            flag_content: Flag content (without prefix/suffix)
            
        Returns:
            Formatted flag string
        """
        return f"{self._prefix}{flag_content}{self._suffix}"
    
    def generate_dynamic_flag(self, challenge_id: str, user_id: str) -> str:
        """
        Generate a per-user dynamic flag using HMAC.
        
        Args:
            challenge_id: Challenge identifier
            user_id: User identifier
            
        Returns:
            Dynamic flag unique to user
        """
        data = f"{challenge_id}:{user_id}".encode()
        signature = hmac.new(self._secret_key, data, hashlib.sha256).hexdigest()[:32]
        return f"{self._prefix}{signature}{self._suffix}"
    
    def verify_flag(
        self,
        submitted: str,
        expected: str,
        case_sensitive: bool = True,
    ) -> bool:
        """
        Verify a submitted flag using constant-time comparison.
        
        Args:
            submitted: User-submitted flag
            expected: Expected flag value
            case_sensitive: Whether comparison is case-sensitive
            
        Returns:
            True if flags match
        """
        if not case_sensitive:
            submitted = submitted.lower()
            expected = expected.lower()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(submitted.encode(), expected.encode())
    
    def verify_dynamic_flag(
        self,
        submitted: str,
        challenge_id: str,
        user_id: str,
    ) -> bool:
        """
        Verify a dynamic flag for a specific user.
        
        Args:
            submitted: User-submitted flag
            challenge_id: Challenge identifier
            user_id: User identifier
            
        Returns:
            True if flag is valid for this user
        """
        expected = self.generate_dynamic_flag(challenge_id, user_id)
        return self.verify_flag(submitted, expected)
    
    def extract_flag_content(self, flag: str) -> Optional[str]:
        """
        Extract content from a formatted flag.
        
        Args:
            flag: Full flag string
            
        Returns:
            Flag content without prefix/suffix, or None if invalid format
        """
        if not flag.startswith(self._prefix) or not flag.endswith(self._suffix):
            return None
        
        return flag[len(self._prefix):-len(self._suffix)]


class TokenService:
    """Service for generating secure tokens."""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """Generate a hex-encoded random token."""
        return secrets.token_hex(length)
    
    @staticmethod
    def generate_numeric_code(length: int = 6) -> str:
        """Generate a numeric code (e.g., for 2FA)."""
        return "".join(str(secrets.randbelow(10)) for _ in range(length))


class RequestSigningService:
    """
    Request signing service for API authentication.
    
    Uses HMAC-SHA256 to sign requests and verify signatures.
    """
    
    def __init__(self, secret_key: str):
        """
        Initialize signing service.
        
        Args:
            secret_key: Secret key for HMAC operations
        """
        self._secret_key = secret_key.encode()
    
    def sign_request(
        self,
        method: str,
        path: str,
        timestamp: str,
        body: str = "",
    ) -> str:
        """
        Generate signature for a request.
        
        Args:
            method: HTTP method
            path: Request path
            timestamp: ISO timestamp
            body: Request body (empty for GET)
            
        Returns:
            HMAC-SHA256 signature
        """
        message = f"{method}\n{path}\n{timestamp}\n{body}".encode()
        return hmac.new(self._secret_key, message, hashlib.sha256).hexdigest()
    
    def verify_signature(
        self,
        signature: str,
        method: str,
        path: str,
        timestamp: str,
        body: str = "",
        max_age_seconds: int = 300,
    ) -> bool:
        """
        Verify a request signature.
        
        Args:
            signature: Provided signature
            method: HTTP method
            path: Request path
            timestamp: ISO timestamp
            body: Request body
            max_age_seconds: Maximum age of valid signature
            
        Returns:
            True if signature is valid and not expired
        """
        from datetime import datetime, timezone
        
        # Check timestamp freshness
        try:
            request_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = (now - request_time).total_seconds()
            
            if abs(age) > max_age_seconds:
                return False
        except ValueError:
            return False
        
        # Verify signature
        expected = self.sign_request(method, path, timestamp, body)
        return hmac.compare_digest(signature, expected)
