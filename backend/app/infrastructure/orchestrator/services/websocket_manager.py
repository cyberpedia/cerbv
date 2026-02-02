"""
WebSocket Event Manager for Real-time Updates

Handles WebSocket connections and broadcasts events for:
- AD game ticks
- KOTH ownership changes
- Programming submission results
- Hardware session updates
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

import structlog

from app.infrastructure.cache import CacheManager

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self._connections: Dict[str, Set[Any]] = {}  # channel -> connections
        self._user_connections: Dict[UUID, Set[Any]] = {}  # user_id -> connections
        self._team_connections: Dict[UUID, Set[Any]] = {}  # team_id -> connections
        self._running = False
        self._subscription_task: Optional[asyncio.Task] = None
        
        # Event handlers
        self._handlers: Dict[str, Callable] = {}
    
    async def start(self) -> None:
        """Start the connection manager."""
        self._running = True
        self._subscription_task = asyncio.create_task(self._subscribe_to_events())
        logger.info("WebSocket Connection Manager started")
    
    async def stop(self) -> None:
        """Stop the connection manager."""
        self._running = False
        
        if self._subscription_task:
            self._subscription_task.cancel()
            try:
                await self._subscription_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for connections in self._connections.values():
            for conn in connections:
                await self._close_connection(conn)
        
        logger.info("WebSocket Connection Manager stopped")
    
    async def connect(
        self,
        websocket: Any,
        user_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        # Add to global connections
        channel = "global"
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)
        
        # Add to user-specific connections
        if user_id:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(websocket)
        
        # Add to team-specific connections
        if team_id:
            if team_id not in self._team_connections:
                self._team_connections[team_id] = set()
            self._team_connections[team_id].add(websocket)
        
        logger.info(
            "WebSocket connected",
            user_id=str(user_id) if user_id else "anonymous",
            team_id=str(team_id) if team_id else "none",
        )
        
        # Start listening for messages
        asyncio.create_task(self._handle_messages(websocket, user_id, team_id))
    
    async def disconnect(
        self,
        websocket: Any,
        user_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None,
    ) -> None:
        """Handle WebSocket disconnection."""
        # Remove from global connections
        channel = "global"
        if channel in self._connections:
            self._connections[channel].discard(websocket)
        
        # Remove from user connections
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]
        
        # Remove from team connections
        if team_id and team_id in self._team_connections:
            self._team_connections[team_id].discard(websocket)
            if not self._team_connections[team_id]:
                del self._team_connections[team_id]
        
        logger.info(
            "WebSocket disconnected",
            user_id=str(user_id) if user_id else "anonymous",
        )
    
    async def subscribe(self, websocket: Any, channels: List[str]) -> None:
        """Subscribe a connection to specific channels."""
        for channel in channels:
            if channel not in self._connections:
                self._connections[channel] = set()
            self._connections[channel].add(websocket)
        
        await self._send_json(websocket, {
            "type": "subscribed",
            "channels": channels,
        })
    
    async def unsubscribe(self, websocket: Any, channels: List[str]) -> None:
        """Unsubscribe a connection from channels."""
        for channel in channels:
            if channel in self._connections:
                self._connections[channel].discard(websocket)
        
        await self._send_json(websocket, {
            "type": "unsubscribed",
            "channels": channels,
        })
    
    async def broadcast(
        self,
        event_type: str,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        team_id: Optional[UUID] = None,
    ) -> None:
        """
        Broadcast an event to connected clients.
        
        Args:
            event_type: Type of event (e.g., "ad.new_tick")
            data: Event data
            channels: Specific channels to broadcast to
            team_id: Optional team ID for team-specific broadcast
        """
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Determine target connections
        target_connections: Set[Any] = set()
        
        if channels:
            for channel in channels:
                if channel in self._connections:
                    target_connections.update(self._connections[channel])
        else:
            # Broadcast to all connections
            for connections in self._connections.values():
                target_connections.update(connections)
        
        # Filter by team if specified
        if team_id and team_id in self._team_connections:
            target_connections = target_connections.intersection(
                self._team_connections[team_id]
            )
        
        # Send to all target connections
        for conn in target_connections:
            await self._send_json(conn, message)
        
        logger.debug(
            "Broadcast event",
            event_type=event_type,
            recipient_count=len(target_connections),
        )
    
    async def send_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Send an event to a specific user."""
        if user_id not in self._user_connections:
            return
        
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        for conn in self._user_connections[user_id]:
            await self._send_json(conn, message)
    
    async def _handle_messages(
        self,
        websocket: Any,
        user_id: Optional[UUID],
        team_id: Optional[UUID],
    ) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in websocket:
                if isinstance(message, str):
                    await self._process_message(websocket, message, user_id, team_id)
        except Exception as e:
            logger.exception("Error handling WebSocket messages", error=str(e))
        finally:
            await self.disconnect(websocket, user_id, team_id)
    
    async def _process_message(
        self,
        websocket: Any,
        message: str,
        user_id: Optional[UUID],
        team_id: Optional[UUID],
    ) -> None:
        """Process an incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                channels = data.get("channels", [])
                await self.subscribe(websocket, channels)
            
            elif msg_type == "unsubscribe":
                channels = data.get("channels", [])
                await self.unsubscribe(websocket, channels)
            
            elif msg_type == "ping":
                await self._send_json(websocket, {"type": "pong"})
            
            else:
                logger.warning("Unknown message type", msg_type=msg_type)
                
        except json.JSONDecodeError:
            await self._send_json(websocket, {
                "type": "error",
                "message": "Invalid JSON",
            })
    
    async def _subscribe_to_events(self) -> None:
        """Subscribe to Redis pub/sub for distributed events."""
        pubsub = self.cache.redis_client.pubsub() if hasattr(self.cache, 'redis_client') else None
        
        if not pubsub:
            return
        
        # Subscribe to event channels
        channels = [
            "ws:events:ad.*",
            "ws:events:koth.*",
            "ws:events:programming.*",
            "ws:events:hardware.*",
        ]
        
        await pubsub.subscribe(*channels)
        
        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    event_type = message["channel"].replace("ws:events:", "")
                    data = json.loads(message["data"])
                    
                    # Broadcast to WebSocket connections
                    await self.broadcast(event_type, data)
                    
            except Exception as e:
                logger.exception("Error in event subscription loop", error=str(e))
                await asyncio.sleep(1)
    
    async def _send_json(self, websocket: Any, data: Dict[str, Any]) -> None:
        """Send JSON data to a WebSocket."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.debug("Failed to send WebSocket message", error=str(e))
    
    async def _close_connection(self, websocket: Any) -> None:
        """Close a WebSocket connection."""
        try:
            await websocket.close()
        except Exception:
            pass
    
    def get_connection_count(self) -> Dict[str, int]:
        """Get connection statistics."""
        return {
            "total": sum(len(c) for c in self._connections.values()),
            "global": len(self._connections.get("global", set())),
            "user_count": len(self._user_connections),
            "team_count": len(self._team_connections),
        }


# ============================================================================
# Event Helper Functions
# ============================================================================

async def emit_ad_event(
    manager: ConnectionManager,
    event_type: str,
    game_id: UUID,
    data: Dict[str, Any],
) -> None:
    """Emit an AD game event."""
    full_event = f"ad.{event_type}"
    channels = [f"ad:{game_id}", "ad:all"]
    await manager.broadcast(full_event, data, channels=channels)


async def emit_koth_event(
    manager: ConnectionManager,
    event_type: str,
    challenge_id: UUID,
    data: Dict[str, Any],
) -> None:
    """Emit a KOTH event."""
    full_event = f"koth.{event_type}"
    channels = [f"koth:{challenge_id}", "koth:all"]
    await manager.broadcast(full_event, data, channels=channels)


async def emit_programming_event(
    manager: ConnectionManager,
    event_type: str,
    submission_id: UUID,
    data: Dict[str, Any],
) -> None:
    """Emit a programming submission event."""
    full_event = f"programming.{event_type}"
    # Send to specific user if user_id is in data
    if "user_id" in data:
        await manager.send_to_user(
            UUID(data["user_id"]),
            full_event,
            {"submission_id": str(submission_id), **data},
        )
    # Also broadcast to programming channel
    await manager.broadcast(full_event, data, channels=["programming:all"])


async def emit_hardware_event(
    manager: ConnectionManager,
    event_type: str,
    equipment_id: UUID,
    data: Dict[str, Any],
) -> None:
    """Emit a hardware lab event."""
    full_event = f"hardware.{event_type}"
    channels = [f"hardware:{equipment_id}", "hardware:all"]
    await manager.broadcast(full_event, data, channels=channels)
