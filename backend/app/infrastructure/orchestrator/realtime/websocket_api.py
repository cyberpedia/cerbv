"""
WebSocket API Endpoints

FastAPI WebSocket endpoints for real-time communications:
- Connection handling with JWT authentication
- Room subscriptions
- Event broadcasting
- Rate limiting enforcement
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.core.config import Settings, get_settings
from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager
from app.infrastructure.orchestrator.realtime.middleware.auth import WSAuthMiddleware
from app.infrastructure.orchestrator.realtime.server import (
    EventMessage,
    EventType,
    RealtimeServer,
    UserInfo,
    get_realtime_server,
)

logger = structlog.get_logger(__name__)

ws_router = APIRouter()


# ============================================================================
# WebSocket Connection Manager
# ============================================================================


class WebSocketManager:
    """Manages WebSocket connections and routing."""
    
    def __init__(
        self,
        realtime_server: RealtimeServer,
        auth_middleware: WSAuthMiddleware,
    ):
        self.realtime = realtime_server
        self.auth = auth_middleware
        self._connection_tasks: Dict[str, Any] = {}
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        rooms: Optional[List[str]] = None,
    ) -> None:
        """
        Handle a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            token: JWT token for authentication
            rooms: Initial rooms to subscribe to
        """
        connection_id = None
        
        try:
            # Authenticate connection
            state = await self.auth.authenticate_connection(websocket, token)
            
            if state.is_anonymous and not token:
                # Anonymous connection - no auth required
                user_info = UserInfo(
                    user_id=UUID(state.connection_id),
                    username=f"anon_{state.connection_id[:8]}",
                    is_anonymous=True,
                )
            else:
                # Authenticated connection
                user_info = UserInfo(
                    user_id=UUID(state.user_id) if state.user_id else UUID(state.connection_id),
                    username=state.username or f"user_{state.connection_id[:8]}",
                    team_id=UUID(state.team_id) if state.team_id else None,
                    role=state.role,
                    is_anonymous=state.is_anonymous,
                )
            
            # Register connection
            connection_id = await self.realtime.register_connection(
                websocket,
                user_info,
                rooms,
            )
            
            # Update connection state
            state.connection_id = connection_id
            
            # Handle messages
            await self._handle_messages(websocket, state, user_info)
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected", connection_id=connection_id)
        except Exception as e:
            logger.exception("WebSocket error", error=str(e))
        finally:
            if connection_id:
                await self.realtime.unregister_connection(
                    websocket,
                    user_info.user_id,
                )
    
    async def _handle_messages(
        self,
        websocket: WebSocket,
        state: Any,
        user_info: UserInfo,
    ) -> None:
        """Handle incoming WebSocket messages."""
        while True:
            try:
                # Wait for message with heartbeat
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                
                # Update last activity
                state.last_activity = datetime.utcnow().isoformat()
                
                # Validate message size
                is_valid, error = self.auth.validate_payload_size(message)
                if not is_valid:
                    await websocket.send_json({
                        "type": "error",
                        "message": error,
                    })
                    continue
                
                # Parse and process message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
                    continue
                
                # Process based on type
                await self._process_message(websocket, state, user_info, data)
                
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.exception("Message handling error", error=str(e))
                break
    
    async def _process_message(
        self,
        websocket: WebSocket,
        state: Any,
        user_info: UserInfo,
        data: Dict[str, Any],
    ) -> None:
        """Process an incoming message."""
        msg_type = data.get("type")
        
        # Rate limiting
        allowed, retry_after = self.auth.check_rate_limit(state.connection_id, msg_type)
        if not allowed:
            await websocket.send_json({
                "type": "error",
                "message": "Rate limit exceeded",
                "retry_after": retry_after,
            })
            return
        
        if msg_type == "subscribe":
            await self._handle_subscribe(websocket, state, user_info, data)
        
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(websocket, state, user_info, data)
        
        elif msg_type == "ping":
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        elif msg_type == "challenge_attempt":
            await self._handle_challenge_attempt(websocket, state, user_info, data)
        
        elif msg_type == "set_presence":
            await self._handle_presence(websocket, state, data)
        
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            })
    
    async def _handle_subscribe(
        self,
        websocket: WebSocket,
        state: Any,
        user_info: UserInfo,
        data: Dict[str, Any],
    ) -> None:
        """Handle room subscription."""
        channels = data.get("channels", [])
        subscribed = []
        failed = []
        
        for channel in channels:
            # Check authorization
            if self.auth.validate_room_access(state, channel):
                await self.realtime._join_room(websocket, channel, user_info.username)
                state.subscribed_rooms.append(channel)
                subscribed.append(channel)
            else:
                failed.append(channel)
        
        await websocket.send_json({
            "type": "subscribed",
            "channels": subscribed,
            "failed": failed,
        })
    
    async def _handle_unsubscribe(
        self,
        websocket: WebSocket,
        state: Any,
        user_info: UserInfo,
        data: Dict[str, Any],
    ) -> None:
        """Handle room unsubscription."""
        channels = data.get("channels", [])
        
        for channel in channels:
            if channel in self.realtime._connections:
                self.realtime._connections[channel].discard(websocket)
            
            if channel in state.subscribed_rooms:
                state.subscribed_rooms.remove(channel)
        
        await websocket.send_json({
            "type": "unsubscribed",
            "channels": channels,
        })
    
    async def _handle_challenge_attempt(
        self,
        websocket: WebSocket,
        state: Any,
        user_info: UserInfo,
        data: Dict[str, Any],
    ) -> None:
        """Handle challenge submission attempt."""
        if user_info.is_anonymous:
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required",
            })
            return
        
        # Validate message
        is_valid, error = self.auth.validate_message_schema(data, "challenge_attempt")
        if not is_valid:
            await websocket.send_json({
                "type": "error",
                "message": error,
            })
            return
        
        # Emit event for processing
        event = EventMessage(
            type=EventType.CHALLENGE_ATTEMPT.value,
            channel="challenges",
            data={
                "user_id": str(user_info.user_id),
                "team_id": str(user_info.team_id) if user_info.team_id else None,
                "challenge_id": data.get("challenge_id"),
                "submission": data.get("submission"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        # Send acknowledgment
        await websocket.send_json({
            "type": "challenge_attempt_received",
            "challenge_id": data.get("challenge_id"),
            "status": "pending",
        })
    
    async def _handle_presence(
        self,
        websocket: WebSocket,
        state: Any,
        data: Dict[str, Any],
    ) -> None:
        """Handle presence update."""
        status = data.get("status", "online")
        
        await websocket.send_json({
            "type": "presence_updated",
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        })


import asyncio


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@ws_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    rooms: Optional[str] = Query(None),
):
    """
    Main WebSocket endpoint for real-time communications.
    
    Query Parameters:
        token: JWT authentication token
        rooms: Comma-separated list of initial rooms to subscribe to
    
    Message Types:
        - subscribe: Subscribe to rooms
        - unsubscribe: Unsubscribe from rooms
        - ping: Heartbeat
        - challenge_attempt: Submit a challenge solution
        - set_presence: Update presence status
    """
    await websocket.accept()
    
    # Parse rooms
    room_list = rooms.split(",") if rooms else []
    
    # Get managers
    realtime = get_realtime_server()
    settings = get_settings()
    auth = WSAuthMiddleware(settings)
    
    manager = WebSocketManager(realtime, auth)
    
    await manager.handle_connection(websocket, token, room_list)


@ws_router.websocket("/ws/admin")
async def websocket_admin_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for admin monitoring.
    
    Requires admin authentication token.
    
    Provides:
        - Active users updates
        - Real-time solve statistics
        - System health metrics
    """
    await websocket.accept()
    
    realtime = get_realtime_server()
    settings = get_settings()
    auth = WSAuthMiddleware(settings)
    
    # Authenticate
    state = await auth.authenticate_connection(websocket, token)
    
    if state.role not in ["admin", "superadmin"]:
        await websocket.send_json({
            "type": "error",
            "message": "Admin access required",
        })
        await websocket.close()
        return
    
    # Subscribe to admin room
    manager = WebSocketManager(realtime, auth)
    await manager.handle_connection(websocket, token, ["admin", "global"])


@ws_router.websocket("/ws/ad/{game_id}")
async def websocket_ad_endpoint(
    websocket: WebSocket,
    game_id: UUID,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for AD game updates.
    
    Path Parameters:
        game_id: AD game UUID
    
    Provides:
        - Tick updates
        - Flag rotation events
        - Service status updates
    """
    await websocket.accept()
    
    realtime = get_realtime_server()
    settings = get_settings()
    auth = WSAuthMiddleware(settings)
    
    manager = WebSocketManager(realtime, auth)
    
    # Subscribe to game-specific room
    room_list = [f"ad:{game_id}", "global"]
    
    await manager.handle_connection(websocket, token, room_list)


# ============================================================================
# HTTP Endpoints for WebSocket Management
# ============================================================================


@ws_router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    realtime = get_realtime_server()
    return realtime.get_connection_stats()


@ws_router.get("/ws/presence/{room_id}")
async def get_room_presence(room_id: str):
    """Get presence information for a room."""
    realtime = get_realtime_server()
    return await realtime.get_room_presence(room_id)


@ws_router.post("/ws/freeze-leaderboard")
async def freeze_leaderboard():
    """Freeze the leaderboard."""
    realtime = get_realtime_server()
    await realtime.freeze_leaderboard()
    return {"status": "frozen"}


@ws_router.post("/ws/unfreeze-leaderboard")
async def unfreeze_leaderboard():
    """Unfreeze the leaderboard."""
    realtime = get_realtime_server()
    await realtime.unfreeze_leaderboard()
    return {"status": "unfrozen"}


@ws_router.post("/ws/anonymous-mode/{enabled}")
async def set_anonymous_mode(enabled: bool):
    """Enable or disable anonymous mode."""
    realtime = get_realtime_server()
    realtime.set_anonymous_mode(enabled)
    return {"anonymous_mode": enabled}


# ============================================================================
# Health Check
# ============================================================================


@ws_router.get("/ws/health")
async def websocket_health():
    """WebSocket server health check."""
    realtime = get_realtime_server()
    return await realtime.health_check()
