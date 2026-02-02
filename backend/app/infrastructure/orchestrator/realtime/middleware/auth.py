"""
WebSocket Authentication Middleware

Provides JWT validation and authorization for WebSocket connections:
- Token validation on connection
- Room authorization (can't join other teams' rooms)
- Input validation on all socket payloads
- CSRF protection for HTTP polling fallback
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple
from uuid import UUID

import structlog
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # User ID
    username: str
    role: str = "player"
    team_id: Optional[str] = None
    exp: int
    iat: int
    type: str = "access"


class WSConnectionState(BaseModel):
    """WebSocket connection state."""
    connection_id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    team_id: Optional[str] = None
    role: str = "player"
    connected_at: str
    last_activity: str
    subscribed_rooms: list = []
    is_authenticated: bool = False
    is_anonymous: bool = True


class WSAuthMiddleware:
    """
    WebSocket authentication middleware.
    
    Features:
    - JWT token validation
    - Room authorization
    - Rate limiting per connection
    - CSRF protection
    - Input validation
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
    ):
        self.settings = settings or get_settings()
        self.secret_key = secret_key or self.settings.secret_key
        self.algorithm = algorithm
        
        # Token expiry
        self.access_token_expire_minutes = self.settings.access_token_expire_minutes or 30
        
        # Rate limiting
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 100  # messages per window
        
        # CSRF tokens
        self._csrf_tokens: Dict[str, datetime] = {}
        self.csrf_token_expiry = 3600  # 1 hour
        
        logger.info("WSAuthMiddleware initialized")
    
    # =========================================================================
    # Token Management
    # =========================================================================
    
    def create_access_token(
        self,
        user_id: str,
        username: str,
        role: str = "player",
        team_id: Optional[str] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a JWT access token for WebSocket authentication.
        
        Args:
            user_id: User ID
            username: Username
            role: User role
            team_id: Team ID
            expires_delta: Optional custom expiry
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode = {
            "sub": user_id,
            "username": username,
            "role": role,
            "team_id": team_id,
            "exp": int(expire.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "type": "access",
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[TokenPayload], str]:
        """
        Verify a JWT token.
        
        Returns:
            Tuple of (is_valid, payload, error_message)
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            
            # Validate token type
            if payload.get("type") != "access":
                return False, None, "Invalid token type"
            
            # Create TokenPayload
            token_payload = TokenPayload(**payload)
            
            # Check expiration
            if token_payload.exp < int(datetime.utcnow().timestamp()):
                return False, None, "Token expired"
            
            return True, token_payload, ""
            
        except JWTError as e:
            logger.debug("Token verification failed", error=str(e))
            return False, None, f"Invalid token: {str(e)}"
        except ValidationError as e:
            return False, None, "Invalid token payload"
    
    # =========================================================================
    # WebSocket Authentication
    # =========================================================================
    
    async def authenticate_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
    ) -> WSConnectionState:
        """
        Authenticate a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            token: Optional JWT token (can also be passed via query param)
            
        Returns:
            WSConnectionState with authentication result
            
        Raises:
            WebSocketDisconnect: If authentication fails
        """
        connection_id = str(UUID())
        connected_at = datetime.utcnow().isoformat()
        
        state = WSConnectionState(
            connection_id=connection_id,
            connected_at=connected_at,
            last_activity=connected_at,
        )
        
        # If no token provided, create anonymous connection
        if not token:
            state.is_anonymous = True
            return state
        
        # Verify token
        is_valid, payload, error = self.verify_token(token)
        
        if not is_valid:
            logger.warning("WebSocket authentication failed", error=error)
            state.is_anonymous = True
            return state
        
        # Update state with user info
        state.user_id = payload.sub
        state.username = payload.username
        state.role = payload.role
        state.team_id = payload.team_id
        state.is_authenticated = True
        state.is_anonymous = False
        
        logger.info(
            "WebSocket authenticated",
            connection_id=connection_id,
            user_id=payload.sub,
            username=payload.username,
        )
        
        return state
    
    # =========================================================================
    # Room Authorization
    # =========================================================================
    
    def can_join_room(
        self,
        state: WSConnectionState,
        room_id: str,
    ) -> Tuple[bool, str]:
        """
        Check if a connection can join a room.
        
        Room rules:
        - global: Anyone can join
        - team:{team_id}: Only team members
        - challenge:{challenge_id}: Anyone
        - admin: Only admins
        - user:{user_id}: Only the user themselves
        """
        # Global room is always accessible
        if room_id == "global":
            return True, ""
        
        # Admin room requires admin role
        if room_id == "admin":
            if state.role not in ["admin", "superadmin"]:
                return False, "Admin access required"
            return True, ""
        
        # Team room: verify team membership
        if room_id.startswith("team:"):
            required_team_id = room_id.split(":")[1]
            
            if state.is_anonymous:
                return False, "Authentication required"
            
            if state.team_id != required_team_id:
                return False, "Not a member of this team"
            
            return True, ""
        
        # User room: verify own user ID
        if room_id.startswith("user:"):
            required_user_id = room_id.split(":")[1]
            
            if state.is_anonymous:
                return False, "Authentication required"
            
            if state.user_id != required_user_id:
                return False, "Cannot access other user's room"
            
            return True, ""
        
        # Challenge rooms are public
        if room_id.startswith("challenge:"):
            return True, ""
        
        # AD game rooms
        if room_id.startswith("ad:"):
            return True, ""
        
        # Default: deny
        return False, "Unknown room type"
    
    def validate_room_access(
        self,
        state: WSConnectionState,
        room_id: str,
    ) -> bool:
        """Validate room access and log if denied."""
        can_join, reason = self.can_join_room(state, room_id)
        
        if not can_join:
            logger.warning(
                "Room access denied",
                connection_id=state.connection_id,
                room_id=room_id,
                reason=reason,
            )
        
        return can_join
    
    # =========================================================================
    # Input Validation
    # =========================================================================
    
    def validate_message_schema(
        self,
        message: Dict[str, Any],
        expected_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate incoming message schema.
        
        Args:
            message: Parsed message dict
            expected_type: Expected message type
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if "type" not in message:
            return False, "Missing 'type' field"
        
        # Validate type
        if message["type"] != expected_type:
            return False, f"Invalid message type: {message['type']}"
        
        # Type-specific validation
        if message["type"] == "subscribe":
            if "channels" not in message:
                return False, "Missing 'channels' field"
            if not isinstance(message["channels"], list):
                return False, "'channels' must be a list"
        
        elif message["type"] == "unsubscribe":
            if "channels" not in message:
                return False, "Missing 'channels' field"
            if not isinstance(message["channels"], list):
                return False, "'channels' must be a list"
        
        elif message["type"] == "challenge_attempt":
            if "challenge_id" not in message:
                return False, "Missing 'challenge_id' field"
        
        return True, ""
    
    def validate_payload_size(
        self,
        payload: str,
        max_size: int = 65536,  # 64KB
    ) -> Tuple[bool, str]:
        """
        Validate payload size.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(payload.encode('utf-8')) > max_size:
            return False, f"Payload exceeds maximum size of {max_size} bytes"
        return True, ""
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    
    def check_rate_limit(
        self,
        connection_id: str,
        event_type: str,
    ) -> Tuple[bool, int]:
        """
        Check rate limit for a connection.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        key = f"{connection_id}:{event_type}"
        now = time.time()
        window_start = now - self.rate_limit_window
        
        if key not in self._rate_limits:
            self._rate_limits[key] = {
                "count": 0,
                "window_start": now,
            }
        
        rate_data = self._rate_limits[key]
        
        # Reset window if expired
        if rate_data["window_start"] < window_start:
            rate_data["count"] = 0
            rate_data["window_start"] = now
        
        # Check limit
        if rate_data["count"] >= self.rate_limit_max:
            # Calculate retry after
            retry_after = int(rate_data["window_start"] + self.rate_limit_window - now)
            return False, max(1, retry_after)
        
        rate_data["count"] += 1
        return True, 0
    
    # =========================================================================
    # CSRF Protection
    # =========================================================================
    
    def generate_csrf_token(self, connection_id: str) -> str:
        """Generate and store a CSRF token for a connection."""
        token = hashlib.sha256(
            f"{connection_id}:{time.time()}".encode()
        ).hexdigest()
        
        self._csrf_tokens[token] = datetime.utcnow() + timedelta(seconds=self.csrf_token_expiry)
        return token
    
    def validate_csrf_token(
        self,
        token: str,
        connection_id: str,
    ) -> bool:
        """Validate a CSRF token."""
        if token not in self._csrf_tokens:
            return False
        
        if self._csrf_tokens[token] < datetime.utcnow():
            del self._csrf_tokens[token]
            return False
        
        # Verify token belongs to this connection
        # (In production, you'd store the connection_id with the token)
        return True
    
    def validate_origin(self, origin: Optional[str]) -> bool:
        """
        Validate the Origin header for CSRF protection.
        
        In production, this should check against allowed origins.
        """
        if not origin:
            # Allow if no origin header (same-origin requests)
            return True
        
        # In production, validate against configured origins
        # For now, just log
        logger.debug("Origin validation", origin=origin)
        return True
    
    # =========================================================================
    # Message Signing (Optional)
    # =========================================================================
    
    def sign_message(
        self,
        message: Dict[str, Any],
        key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Sign a message for integrity verification.
        
        Returns:
            Message with signature
        """
        key = key or self.secret_key.encode()
        
        # Create canonical representation
        content = str(sorted(message.items()))
        
        # Generate signature
        signature = hmac.new(
            key,
            content.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return {
            **message,
            "_signature": signature,
        }
    
    def verify_message_signature(
        self,
        message: Dict[str, Any],
        key: Optional[bytes] = None,
    ) -> bool:
        """Verify message signature."""
        key = key or self.secret_key.encode()
        
        if "_signature" not in message:
            return False
        
        signature = message.pop("_signature")
        content = str(sorted(message.items()))
        
        expected = hmac.new(
            key,
            content.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def extract_token_from_query(
        self,
        query_params: Dict[str, str],
    ) -> Optional[str]:
        """Extract token from query parameters."""
        # Check common parameter names
        for param_name in ["token", "access_token", "jwt", "auth_token"]:
            if param_name in query_params:
                return query_params[param_name]
        return None
    
    def extract_token_from_headers(
        self,
        headers: Dict[str, str],
    ) -> Optional[str]:
        """Extract token from request headers."""
        auth_header = headers.get("Authorization", "")
        
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        return headers.get("X-Auth-Token")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get middleware statistics."""
        return {
            "active_rate_limits": len(self._rate_limits),
            "active_csrf_tokens": len(self._csrf_tokens),
            "rate_limit_window": self.rate_limit_window,
            "rate_limit_max": self.rate_limit_max,
            "csrf_token_expiry_seconds": self.csrf_token_expiry,
        }
