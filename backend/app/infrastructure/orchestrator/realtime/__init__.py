"""
Real-Time Infrastructure Module

Provides WebSocket and SSE-based real-time communications for:
- Live leaderboards and score updates
- Notifications (first blood, unlocks, announcements)
- Admin monitoring dashboards
- Attack-Defense game updates
- Container log streaming
"""

from app.infrastructure.orchestrator.realtime.server import (
    EventMessage,
    EventType,
    NotificationChannel,
    NotificationPriority,
    RealtimeServer,
    UserInfo,
    get_realtime_server,
)

from app.infrastructure.orchestrator.realtime.handlers.admin import AdminHandler
from app.infrastructure.orchestrator.realtime.handlers.leaderboard import LeaderboardHandler
from app.infrastructure.orchestrator.realtime.handlers.notifications import (
    Notification,
    NotificationChannel as NotifChannel,
    NotificationPriority as NotifPriority,
    NotificationType,
    NotificationsHandler,
)

from app.infrastructure.orchestrator.realtime.middleware.auth import (
    WSAuthMiddleware,
    WSConnectionState,
)

from app.infrastructure.orchestrator.realtime.ad_scheduler import ADTickScheduler
from app.infrastructure.orchestrator.realtime.sse import (
    SSEPublisher,
    get_sse_publisher,
    sse_router,
)

from app.infrastructure.orchestrator.realtime.websocket_api import (
    WebSocketManager,
    ws_router,
)

__all__ = [
    # Server
    "RealtimeServer",
    "get_realtime_server",
    "EventMessage",
    "EventType",
    "UserInfo",
    "NotificationChannel",
    "NotificationPriority",
    
    # Handlers
    "AdminHandler",
    "LeaderboardHandler",
    "NotificationsHandler",
    "Notification",
    "NotificationType",
    
    # Middleware
    "WSAuthMiddleware",
    "WSConnectionState",
    
    # AD Scheduler
    "ADTickScheduler",
    
    # SSE
    "SSEPublisher",
    "get_sse_publisher",
    "sse_router",
    
    # WebSocket API
    "WebSocketManager",
    "ws_router",
]
