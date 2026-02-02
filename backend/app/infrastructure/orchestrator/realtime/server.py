"""
Real-Time Event Bus and WebSocket Server

Central hub for all real-time communications including:
- Live leaderboards and score updates
- Notifications (first blood, unlocks, announcements)
- Admin monitoring dashboards
- Attack-Defense tick updates
- Container log streaming
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class EventType(str, Enum):
    """Enumeration of real-time event types."""
    # Leaderboard events
    LEADERBOARD_UPDATE = "leaderboard.update"
    LEADERBOARD_DIFF = "leaderboard.diff"
    LEADERBOARD_FREEZE = "leaderboard.freeze"
    LEADERBOARD_UNFREEZE = "leaderboard.unfreeze"
    
    # Challenge events
    CHALLENGE_SOLVE = "challenge.solve"
    CHALLENGE_FIRST_BLOOD = "challenge.first_blood"
    CHALLENGE_UNLOCK = "challenge.unlock"
    CHALLENGE_ATTEMPT = "challenge.attempt"
    
    # Notification events
    NOTIFICATION = "notification"
    NOTIFICATION_BULK = "notification.bulk"
    ANNOUNCEMENT = "announcement"
    
    # Admin events
    ADMIN_ACTIVE_USERS = "admin.active_users"
    ADMIN_SOLVES = "admin.solves"
    ADMIN_SYSTEM_STATUS = "admin.system_status"
    
    # AD Game events
    AD_TICK = "ad.tick"
    AD_FLAG_ROTATION = "ad.flag_rotation"
    AD_SERVICE_STATUS = "ad.service_status"
    AD_SCORE_CALC = "ad.score_calc"
    
    # Container logs
    CONTAINER_LOG = "container.log"
    
    # System events
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    WEBHOOK = "webhook"


@dataclass
class UserInfo:
    """Information about a connected user."""
    user_id: UUID
    username: str
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    role: str = "player"
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_anonymous: bool = False


@dataclass
class RateLimitConfig:
    """Rate limiting configuration per event type."""
    events_per_second: int = 10
    burst_limit: int = 50
    window_seconds: int = 60


@dataclass
class EventMessage:
    """Standard event message format."""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: str = ""
    channel: str = "global"
    priority: str = NotificationPriority.NORMAL.value
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "cerb"
    version: str = "1.0"


# ============================================================================
# Connection Manager with Redis Adapter
# ============================================================================


class RealtimeServer:
    """
    Central real-time server managing WebSocket connections and event routing.
    
    Features:
    - Room-based subscriptions (team-room, challenge-room)
    - Broadcast vs targeted emissions
    - Presence detection
    - Rate limiting
    - Message durability via Redis
    - Horizontal scaling via Redis Adapter
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.redis: Optional[Redis] = None
        self.pubsub: Optional[PubSub] = None
        self._running = False
        self._subscriptions_task: Optional[asyncio.Task] = None
        
        # Connection storage
        self._connections: Dict[str, Set[Any]] = {}  # room_id -> connections
        self._user_connections: Dict[UUID, Set[Any]] = {}  # user_id -> connections
        self._user_info: Dict[UUID, UserInfo] = {}  # user_id -> info
        self._presence: Dict[str, Set[str]] = {}  # room_id -> usernames
        
        # Rate limiting
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_config = {
            EventType.CHALLENGE_ATTEMPT.value: RateLimitConfig(events_per_second=5, burst_limit=20),
            EventType.NOTIFICATION.value: RateLimitConfig(events_per_second=20, burst_limit=100),
            EventType.CONTAINER_LOG.value: RateLimitConfig(events_per_second=100, burst_limit=500),
        }
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Message backlog for reconnection
        self._message_backlog: Dict[str, List[EventMessage]] = {}
        self._backlog_max_size = 1000
        
        # Scoreboard freeze state
        self._scoreboard_frozen = False
        self._cached_leaderboard: Optional[Dict[str, Any]] = None
        self._freeze_started: Optional[datetime] = None
        
        # Anonymous mode
        self._anonymous_mode = False
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("RealtimeServer initialized")
    
    async def connect(self, redis_url: Optional[str] = None) -> None:
        """Connect to Redis for pub/sub and scaling."""
        redis_url = redis_url or self.settings.redis_url
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        await self.redis.ping()
        logger.info("Connected to Redis", url=redis_url)
        
        # Subscribe to event channels
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(
            "realtime:leaderboard",
            "realtime:notifications",
            "realtime:admin",
            "realtime:ad",
            "realtime:logs",
        )
        
        self._subscriptions_task = asyncio.create_task(self._handle_redis_messages())
    
    async def disconnect(self) -> None:
        """Disconnect from Redis and cleanup."""
        self._running = False
        
        if self._subscriptions_task:
            self._subscriptions_task.cancel()
            try:
                await self._subscriptions_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        if self.redis:
            await self.redis.close()
        
        logger.info("RealtimeServer disconnected")
    
    async def start(self) -> None:
        """Start the server."""
        self._running = True
        logger.info("RealtimeServer started")
    
    async def stop(self) -> None:
        """Stop the server."""
        await self.disconnect()
        logger.info("RealtimeServer stopped")
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    async def register_connection(
        self,
        websocket: Any,
        user_info: UserInfo,
        rooms: Optional[List[str]] = None,
    ) -> str:
        """
        Register a new WebSocket connection.
        
        Returns:
            connection_id: Unique identifier for this connection
        """
        connection_id = str(uuid4())
        
        async with self._lock:
            # Store user info
            self._user_info[user_info.user_id] = user_info
            
            # Add to user connections
            if user_info.user_id not in self._user_connections:
                self._user_connections[user_info.user_id] = set()
            self._user_connections[user_info.user_id].add(websocket)
            
            # Add to global room
            await self._join_room(websocket, "global", user_info.username)
            
            # Add to requested rooms
            if rooms:
                for room in rooms:
                    await self._join_room(websocket, room, user_info.username)
            
            # Add to team room if applicable
            if user_info.team_id and not user_info.is_anonymous:
                team_room = f"team:{user_info.team_id}"
                await self._join_room(websocket, team_room, user_info.username)
            
            logger.info(
                "Connection registered",
                connection_id=connection_id,
                user_id=str(user_info.user_id),
                rooms=rooms or [],
            )
        
        return connection_id
    
    async def unregister_connection(
        self,
        websocket: Any,
        user_id: UUID,
    ) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            # Remove from user connections
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(websocket)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]
                    
                    # Remove user info
                    if user_id in self._user_info:
                        del self._user_info[user_id]
            
            # Remove from all rooms
            for room_id, connections in list(self._connections.items()):
                if websocket in connections:
                    connections.discard(websocket)
                    
                    # Update presence
                    if room_id in self._presence:
                        # Remove user from presence (need to track per-user)
                        pass
            
            logger.info("Connection unregistered", user_id=str(user_id))
    
    async def _join_room(
        self,
        websocket: Any,
        room_id: str,
        username: str,
    ) -> None:
        """Add connection to a room."""
        if room_id not in self._connections:
            self._connections[room_id] = set()
        self._connections[room_id].add(websocket)
        
        if room_id not in self._presence:
            self._presence[room_id] = set()
        self._presence[room_id].add(username)
    
    # =========================================================================
    # Event Broadcasting
    # =========================================================================
    
    async def broadcast(
        self,
        event: EventMessage,
        rooms: Optional[List[str]] = None,
        exclude_user: Optional[UUID] = None,
    ) -> int:
        """
        Broadcast an event to connected clients.
        
        Args:
            event: EventMessage to broadcast
            rooms: Specific rooms to broadcast to (None = all)
            exclude_user: User ID to exclude from broadcast
            
        Returns:
            Number of clients that received the event
        """
        message = event.model_dump_json()
        
        # Determine target connections
        target_connections: Set[Any] = set()
        
        if rooms:
            for room in rooms:
                if room in self._connections:
                    target_connections.update(self._connections[room])
        else:
            for connections in self._connections.values():
                target_connections.update(connections)
        
        # Exclude specific user
        if exclude_user and exclude_user in self._user_connections:
            user_conns = self._user_connections[exclude_user]
            target_connections = target_connections - user_conns
        
        # Send to all target connections
        sent_count = 0
        for conn in target_connections:
            try:
                await conn.send_text(message)
                sent_count += 1
            except Exception as e:
                logger.debug("Failed to send to connection", error=str(e))
        
        # Store in Redis for scaling
        if self.redis and event.priority != NotificationPriority.LOW.value:
            channel = f"realtime:{event.type.split('.')[0]}"
            await self.redis.publish(channel, message)
        
        logger.debug(
            "Broadcast event",
            event_type=event.type,
            recipient_count=sent_count,
        )
        
        return sent_count
    
    async def send_to_user(
        self,
        user_id: UUID,
        event: EventMessage,
    ) -> bool:
        """Send an event to a specific user."""
        if user_id not in self._user_connections:
            return False
        
        message = event.model_dump_json()
        sent = False
        
        for conn in self._user_connections[user_id]:
            try:
                await conn.send_text(message)
                sent = True
            except Exception as e:
                logger.debug("Failed to send to user", error=str(e))
        
        return sent
    
    async def send_to_room(
        self,
        room_id: str,
        event: EventMessage,
    ) -> int:
        """Send an event to all users in a room."""
        if room_id not in self._connections:
            return 0
        
        return await self.broadcast(event, rooms=[room_id])
    
    # =========================================================================
    # Leaderboard Specific Methods
    # =========================================================================
    
    async def update_leaderboard(
        self,
        leaderboard_data: Dict[str, Any],
        diff_mode: bool = True,
    ) -> None:
        """
        Update the leaderboard and broadcast to all clients.
        
        Args:
            leaderboard_data: Full or diff leaderboard data
            diff_mode: If True, compute and send only changed positions
        """
        if self._scoreboard_frozen:
            # Store update for later
            self._cached_leaderboard = {
                "data": leaderboard_data,
                "timestamp": datetime.utcnow().isoformat(),
            }
            return
        
        if diff_mode:
            event = EventMessage(
                type=EventType.LEADERBOARD_DIFF.value,
                channel="leaderboard",
                data=leaderboard_data,
            )
        else:
            event = EventMessage(
                type=EventType.LEADERBOARD_UPDATE.value,
                channel="leaderboard",
                data=leaderboard_data,
            )
        
        await self.broadcast(event, rooms=["leaderboard", "global"])
    
    async def freeze_leaderboard(self) -> None:
        """Freeze the leaderboard (stop updates, show cached data)."""
        self._scoreboard_frozen = True
        self._freeze_started = datetime.utcnow()
        
        event = EventMessage(
            type=EventType.LEADERBOARD_FREEZE.value,
            channel="leaderboard",
            data={
                "frozen": True,
                "timestamp": self._freeze_started.isoformat(),
            },
        )
        
        await self.broadcast(event, rooms=["leaderboard", "global"])
        logger.info("Leaderboard frozen")
    
    async def unfreeze_leaderboard(self) -> None:
        """Unfreeze the leaderboard and broadcast all pending updates."""
        self._scoreboard_frozen = False
        
        event = EventMessage(
            type=EventType.LEADERBOARD_UNFREEZE.value,
            channel="leaderboard",
            data={
                "frozen": False,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        await self.broadcast(event, rooms=["leaderboard", "global"])
        
        # Send cached updates
        if self._cached_leaderboard:
            await self.update_leaderboard(self._cached_leaderboard["data"])
            self._cached_leaderboard = None
        
        logger.info("Leaderboard unfrozen")
    
    def set_anonymous_mode(self, enabled: bool) -> None:
        """Enable or disable anonymous mode (mask names in transit)."""
        self._anonymous_mode = enabled
    
    def anonymize_leaderboard(self, leaderboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask team/user names for anonymous mode."""
        if not self._anonymous_mode:
            return leaderboard_data
        
        # Create anonymized copy
        anonymized = leaderboard_data.copy()
        
        if "entries" in anonymized:
            for entry in anonymized["entries"]:
                entry["team_name"] = f"Team {entry.get('team_id', '???')[:8]}"
                if "members" in entry:
                    for member in entry["members"]:
                        member["username"] = f"Player {member.get('user_id', '???')[:8]}"
        
        return anonymized
    
    # =========================================================================
    # Notification Methods
    # =========================================================================
    
    async def send_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: str = "info",
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: List[NotificationChannel] = None,
        data: Dict[str, Any] = None,
    ) -> None:
        """Send a notification to a specific user."""
        event = EventMessage(
            type=EventType.NOTIFICATION.value,
            channel="notifications",
            priority=priority.value,
            data={
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "channels": [c.value for c in channels] if channels else [NotificationChannel.IN_APP.value],
                "data": data or {},
            },
        )
        
        await self.send_to_user(user_id, event)
    
    async def broadcast_notification(
        self,
        title: str,
        message: str,
        notification_type: str = "announcement",
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: List[NotificationChannel] = None,
        target_rooms: List[str] = None,
        exclude_users: List[UUID] = None,
    ) -> None:
        """Broadcast a notification to multiple rooms."""
        event = EventMessage(
            type=EventType.ANNOUNCEMENT.value if notification_type == "announcement" else EventType.NOTIFICATION.value,
            channel="notifications",
            priority=priority.value,
            data={
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "channels": [c.value for c in channels] if channels else [NotificationChannel.IN_APP.value],
            },
        )
        
        exclude = exclude_users or []
        await self.broadcast(event, rooms=target_rooms, exclude_user=exclude[0] if exclude else None)
    
    async def emit_first_blood(
        self,
        challenge_id: UUID,
        challenge_name: str,
        solver_id: UUID,
        solver_name: str,
        team_id: Optional[UUID],
        team_name: Optional[str],
    ) -> None:
        """Broadcast first blood notification."""
        event = EventMessage(
            type=EventType.CHALLENGE_FIRST_BLOOD.value,
            channel="notifications",
            priority=NotificationPriority.HIGH.value,
            data={
                "challenge_id": str(challenge_id),
                "challenge_name": challenge_name,
                "solver_id": str(solver_id),
                "solver_name": solver_name,
                "team_id": str(team_id) if team_id else None,
                "team_name": team_name,
            },
        )
        
        await self.broadcast(event, rooms=["notifications", "global", f"challenge:{challenge_id}"])
    
    async def emit_challenge_solve(
        self,
        challenge_id: UUID,
        user_id: UUID,
        team_id: Optional[UUID],
        points: int,
        is_first_blood: bool = False,
    ) -> None:
        """Emit challenge solve event."""
        event_data = {
            "challenge_id": str(challenge_id),
            "user_id": str(user_id),
            "team_id": str(team_id) if team_id else None,
            "points": points,
            "is_first_blood": is_first_blood,
        }
        
        # Broadcast to admin
        admin_event = EventMessage(
            type=EventType.ADMIN_SOLVES.value,
            channel="admin",
            data=event_data,
        )
        await self.broadcast(admin_event, rooms=["admin"])
        
        # Broadcast to team
        if team_id:
            team_event = EventMessage(
                type=EventType.CHALLENGE_SOLVE.value,
                channel="challenges",
                data=event_data,
            )
            await self.broadcast(team_event, rooms=[f"team:{team_id}"])
        
        # Broadcast to global (for leaderboard)
        if is_first_blood:
            await self.emit_first_blood(
                challenge_id,
                "",  # challenge_name
                user_id,
                "",  # solver_name
                team_id,
                "",  # team_name
            )
    
    # =========================================================================
    # Admin Monitoring Methods
    # =========================================================================
    
    async def get_active_users(self) -> List[UserInfo]:
        """Get list of active users."""
        return list(self._user_info.values())
    
    async def get_room_presence(self, room_id: str) -> Dict[str, Any]:
        """Get presence information for a room."""
        presence = self._presence.get(room_id, set())
        return {
            "room_id": room_id,
            "user_count": len(presence),
            "users": list(presence),
        }
    
    async def broadcast_admin_stats(self) -> None:
        """Broadcast admin statistics to monitoring clients."""
        stats = {
            "active_connections": sum(len(c) for c in self._connections.values()),
            "active_users": len(self._user_connections),
            "rooms": {
                room_id: len(connections)
                for room_id, connections in self._connections.items()
            },
            "memory_usage": 0,  # Can be filled with actual metrics
            "uptime": time.time(),
        }
        
        event = EventMessage(
            type=EventType.ADMIN_SYSTEM_STATUS.value,
            channel="admin",
            data=stats,
        )
        
        await self.broadcast(event, rooms=["admin"])
    
    # =========================================================================
    # Attack-Defense Game Methods
    # =========================================================================
    
    async def broadcast_ad_tick(
        self,
        tick_number: int,
        tick_duration: int,
        scores: Dict[str, Any],
    ) -> None:
        """Broadcast AD game tick update."""
        event = EventMessage(
            type=EventType.AD_TICK.value,
            channel="ad",
            priority=NotificationPriority.HIGH.value,
            data={
                "tick_number": tick_number,
                "tick_duration": tick_duration,
                "scores": scores,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        await self.broadcast(event, rooms=["ad", "global"])
    
    async def broadcast_flag_rotation(
        self,
        flags: List[Dict[str, Any]],
    ) -> None:
        """Broadcast flag rotation event."""
        event = EventMessage(
            type=EventType.AD_FLAG_ROTATION.value,
            channel="ad",
            priority=NotificationPriority.URGENT.value,
            data={
                "flags": flags,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        await self.broadcast(event, rooms=["ad", "global"])
    
    async def broadcast_service_status(
        self,
        services: List[Dict[str, Any]],
    ) -> None:
        """Broadcast service status update."""
        event = EventMessage(
            type=EventType.AD_SERVICE_STATUS.value,
            channel="ad",
            data={
                "services": services,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        await self.broadcast(event, rooms=["ad"])
    
    # =========================================================================
    # Container Log Streaming
    # =========================================================================
    
    async def stream_container_log(
        self,
        container_id: str,
        log_data: Dict[str, Any],
        target_rooms: List[str],
    ) -> None:
        """Stream container logs to specified rooms."""
        event = EventMessage(
            type=EventType.CONTAINER_LOG.value,
            channel="logs",
            data={
                "container_id": container_id,
                "logs": log_data.get("logs", ""),
                "timestamp": log_data.get("timestamp", datetime.utcnow().isoformat()),
            },
        )
        
        await self.broadcast(event, rooms=target_rooms)
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    
    async def check_rate_limit(
        self,
        user_id: UUID,
        event_type: str,
    ) -> bool:
        """
        Check if an event is rate limited for a user.
        
        Returns:
            True if allowed, False if rate limited
        """
        config = self._rate_limit_config.get(event_type, RateLimitConfig())
        key = f"{user_id}:{event_type}"
        
        async with self._lock:
            now = time.time()
            window_start = now - config.window_seconds
            
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
            if rate_data["count"] >= config.burst_limit:
                return False
            
            rate_data["count"] += 1
            return True
    
    # =========================================================================
    # Redis Pub/Sub Handling
    # =========================================================================
    
    async def _handle_redis_messages(self) -> None:
        """Handle incoming messages from Redis pub/sub."""
        while self._running:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                
                if message and message["type"] == "message":
                    channel = message["channel"]
                    data = json.loads(message["data"])
                    
                    # Parse event type from channel
                    event_type = f"redis.{channel.replace('realtime:', '')}"
                    
                    # Broadcast to WebSocket connections
                    event = EventMessage(
                        type=event_type,
                        data=data,
                    )
                    await self.broadcast(event)
                    
            except Exception as e:
                logger.exception("Error handling Redis message", error=str(e))
                await asyncio.sleep(1)
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def add_event_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """Add an event handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def _invoke_handlers(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Invoke all handlers for an event type."""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.exception("Error in event handler", error=str(e))
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": sum(len(c) for c in self._connections.values()),
            "total_users": len(self._user_connections),
            "rooms": {
                room_id: len(connections)
                for room_id, connections in self._connections.items()
            },
            "scoreboard_frozen": self._scoreboard_frozen,
            "anonymous_mode": self._anonymous_mode,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the realtime server."""
        return {
            "status": "healthy" if self._running else "unhealthy",
            "redis_connected": self.redis is not None,
            "connections": self.get_connection_stats(),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

realtime_server: Optional[RealtimeServer] = None


def get_realtime_server() -> RealtimeServer:
    """Get or create the realtime server singleton."""
    global realtime_server
    if realtime_server is None:
        realtime_server = RealtimeServer()
    return realtime_server
