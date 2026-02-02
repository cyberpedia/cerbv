"""
Server-Sent Events (SSE) Endpoints

Provides one-way broadcast capabilities for:
- Public leaderboard updates
- Live score feeds
- Announcements
- System status broadcasts
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

logger = structlog.get_logger(__name__)

sse_router = APIRouter()


# ============================================================================
# SSE Event Publisher
# ============================================================================


class SSEPublisher:
    """
    Server-Sent Events publisher for one-way broadcasts.
    
    Features:
    - Topic-based subscriptions
    - Redis-backed for multi-instance support
    - Automatic reconnection handling
    - Heartbeat keepalive
    """
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self._subscriptions: Dict[str, set] = {}
        self._heartbeat_interval = 30  # seconds
        self._running = False
        
        logger.info("SSEPublisher initialized")
    
    async def start(self) -> None:
        """Start the publisher."""
        self._running = True
        logger.info("SSEPublisher started")
    
    async def stop(self) -> None:
        """Stop the publisher."""
        self._running = False
        logger.info("SSEPublisher stopped")
    
    async def publish(
        self,
        topic: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> int:
        """
        Publish an event to a topic.
        
        Args:
            topic: Topic name
            event_type: Event type for SSE
            data: Event data
            
        Returns:
            Number of subscribers notified
        """
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Store in Redis for durability
        await self.cache.redis_client.lpush(
            f"sse:{topic}",
            json.dumps(message),
        )
        
        # Trim to last 100 messages
        await self.cache.redis_client.ltrim(f"sse:{topic}", 0, 99)
        
        # Publish to subscribers
        count = 0
        if topic in self._subscriptions:
            for queue in self._subscriptions[topic]:
                try:
                    await queue.put(message)
                    count += 1
                except Exception:
                    pass
        
        return count
    
    async def subscribe(
        self,
        topic: str,
        last_event_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Subscribe to a topic and yield events.
        
        Args:
            topic: Topic name
            last_event_id: Last event ID for replay
            
        Yields:
            Event dictionaries
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        # Register subscription
        if topic not in self._subscriptions:
            self._subscriptions[topic] = set()
        self._subscriptions[topic].add(queue)
        
        try:
            # Send missed messages if last_event_id provided
            if last_event_id:
                async for event in self._get_missed_messages(topic, last_event_id):
                    yield event
            
            # Main event loop with heartbeat
            while self._running:
                try:
                    # Wait for message with timeout for heartbeat
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=self._heartbeat_interval,
                    )
                    yield message
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {
                        "type": "heartbeat",
                        "data": {"timestamp": datetime.utcnow().isoformat()},
                    }
                    
        finally:
            # Unregister subscription
            self._subscriptions[topic].discard(queue)
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]
    
    async def _get_missed_messages(
        self,
        topic: str,
        last_event_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get missed messages since last_event_id."""
        messages = await self.cache.redis_client.lrange(f"sse:{topic}", 0, -1)
        
        # Parse event ID to get timestamp
        try:
            last_ts = datetime.fromisoformat(last_event_id)
        except ValueError:
            last_ts = None
        
        for msg_json in messages:
            msg = json.loads(msg_json)
            msg_ts = datetime.fromisoformat(msg.get("timestamp", ""))
            
            if last_ts and msg_ts <= last_ts:
                continue
            
            yield msg


# Global publisher instance
_sse_publisher: Optional[SSEPublisher] = None


def get_sse_publisher() -> SSEPublisher:
    """Get or create SSE publisher."""
    global _sse_publisher
    if _sse_publisher is None:
        raise RuntimeError("SSE publisher not initialized")
    return _sse_publisher


# ============================================================================
# SSE Endpoints
# ============================================================================


@sse_router.get("/events/leaderboard")
async def leaderboard_events(
    request: Request,
    anonymous: bool = Query(False, description="Mask team names"),
):
    """
    Server-Sent Events stream for leaderboard updates.
    
    Provides real-time leaderboard score updates.
    """
    async def event_generator():
        publisher = get_sse_publisher()
        
        try:
            async for event in publisher.subscribe("leaderboard"):
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                # Apply anonymous mode
                if anonymous and event.get("data"):
                    event["data"] = _anonymize_leaderboard(event["data"])
                
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                    "id": event.get("id"),
                }
        except Exception as e:
            logger.exception("Leaderboard SSE error", error=str(e))
    
    return EventSourceResponse(event_generator())


@sse_router.get("/events/announcements")
async def announcement_events(
    request: Request,
):
    """
    Server-Sent Events stream for game announcements.
    
    Provides real-time announcements from organizers.
    """
    async def event_generator():
        publisher = get_sse_publisher()
        
        try:
            async for event in publisher.subscribe("announcements"):
                if await request.is_disconnected():
                    break
                
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                    "id": event.get("id"),
                }
        except Exception as e:
            logger.exception("Announcements SSE error", error=str(e))
    
    return EventSourceResponse(event_generator())


@sse_router.get("/events/status")
async def status_events(
    request: Request,
):
    """
    Server-Sent Events stream for system status.
    
    Provides periodic system health and status updates.
    """
    async def event_generator():
        publisher = get_sse_publisher()
        
        try:
            async for event in publisher.subscribe("status"):
                if await request.is_disconnected():
                    break
                
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                    "id": event.get("id"),
                }
        except Exception as e:
            logger.exception("Status SSE error", error=str(e))
    
    return EventSourceResponse(event_generator())


@sse_router.get("/events/ad/{game_id}")
async def ad_events(
    request: Request,
    game_id: UUID,
):
    """
    Server-Sent Events stream for AD game updates.
    
    Provides real-time AD game tick and service status updates.
    """
    topic = f"ad:{game_id}"
    
    async def event_generator():
        publisher = get_sse_publisher()
        
        try:
            async for event in publisher.subscribe(topic):
                if await request.is_disconnected():
                    break
                
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                    "id": event.get("id"),
                }
        except Exception as e:
            logger.exception("AD SSE error", error=str(e))
    
    return EventSourceResponse(event_generator())


# ============================================================================
# Helper Functions
# ============================================================================


def _anonymize_leaderboard(data: Dict[str, Any]) -> Dict[str, Any]:
    """Anonymize leaderboard data."""
    if "entries" in data:
        for entry in data["entries"]:
            entry["team_name"] = f"Team {entry.get('team_id', '???')[:8]}"
            if "members" in entry.get("members", []):
                for member in entry["members"]:
                    member["username"] = f"Player {member.get('user_id', '???')[:8]}"
    
    return data


# ============================================================================
# Publisher Management
# ============================================================================


async def init_sse_publisher(cache_manager: CacheManager) -> SSEPublisher:
    """Initialize the SSE publisher."""
    global _sse_publisher
    _sse_publisher = SSEPublisher(cache_manager)
    await _sse_publisher.start()
    return _sse_publisher


async def shutdown_sse_publisher() -> None:
    """Shutdown the SSE publisher."""
    global _sse_publisher
    if _sse_publisher:
        await _sse_publisher.stop()
        _sse_publisher = None
