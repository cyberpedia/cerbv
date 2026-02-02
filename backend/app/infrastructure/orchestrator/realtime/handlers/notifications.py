"""
Notifications Handler

Manages real-time notifications with:
- Multiple channels (in-app, email, push, webhook)
- Priority levels (urgent bypasses DND)
- Digest mode (batch notifications)
- First blood, challenge unlock, team invite, announcement types
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID, uuid4

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

logger = structlog.get_logger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    FIRST_BLOOD = "first_blood"
    CHALLENGE_UNLOCK = "challenge_unlock"
    CHALLENGE_SOLVE = "challenge_solve"
    TEAM_INVITE = "team_invite"
    TEAM_JOIN = "team_join"
    ANNOUNCEMENT = "announcement"
    SYSTEM = "system"
    SCORE_UPDATE = "score_update"
    ACHIEVEMENT = "achievement"


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
class Notification:
    """Notification object."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: UUID
    type: str = NotificationType.SYSTEM.value
    title: str = ""
    message: str = ""
    priority: str = NotificationPriority.NORMAL.value
    channels: List[str] = field(default_factory=lambda: [NotificationChannel.IN_APP.value])
    data: Dict[str, Any] = field(default_factory=dict)
    read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    action_url: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class DigestConfig:
    """Configuration for notification digest batching."""
    enabled: bool = False
    interval_minutes: int = 60
    max_notifications_per_digest: int = 20
    quiet_hours_start: Optional[int] = None  # Hour of day (0-23)
    quiet_hours_end: Optional[int] = None


class NotificationsHandler:
    """
    Handles real-time notifications with multi-channel delivery.
    
    Features:
    - Multiple notification types
    - Priority-based delivery
    - Digest mode for batching
    - Do Not Disturb (DND) support
    - Webhook integrations
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        digest_config: Optional[DigestConfig] = None,
        webhook_secret: Optional[str] = None,
    ):
        self.db_manager = db_manager
        self.cache = cache_manager
        self.digest_config = digest_config or DigestConfig()
        self.webhook_secret = webhook_secret
        
        # User preferences cache
        self._preferences: Dict[UUID, Dict[str, Any]] = {}
        
        # Notification queues per user
        self._digest_queues: Dict[UUID, List[Notification]] = {}
        
        # DND schedules
        self._dnd_users: Set[UUID] = set()
        
        # Webhook callbacks
        self._webhook_handlers: List[Callable] = []
        
        # Background tasks
        self._digest_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("NotificationsHandler initialized")
    
    async def start(self) -> None:
        """Start background tasks."""
        self._running = True
        
        if self.digest_config.enabled:
            self._digest_task = asyncio.create_task(self._digest_worker())
        
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        
        logger.info("NotificationsHandler started")
    
    async def stop(self) -> None:
        """Stop background tasks."""
        self._running = False
        
        if self._digest_task:
            self._digest_task.cancel()
            try:
                await self._digest_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("NotificationsHandler stopped")
    
    # =========================================================================
    # Notification Creation
    # =========================================================================
    
    async def create_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: List[NotificationChannel] = None,
        data: Dict[str, Any] = None,
        action_url: str = None,
        icon: str = None,
        expires_at: datetime = None,
    ) -> Notification:
        """
        Create and dispatch a notification.
        
        Args:
            user_id: Target user ID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level
            channels: Delivery channels
            data: Additional data
            action_url: URL for user action
            icon: Icon identifier
            expires_at: Expiration timestamp
            
        Returns:
            Created notification
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            priority=priority.value,
            channels=[c.value for c in channels] if channels else [NotificationChannel.IN_APP.value],
            data=data or {},
            action_url=action_url,
            icon=icon,
            expires_at=expires_at,
        )
        
        # Check DND
        if await self._is_in_dnd(user_id):
            if priority != NotificationPriority.URGENT:
                # Queue for later delivery
                await self._queue_notification(notification)
                return notification
            # Urgent notifications bypass DND
        
        # Save to database
        await self._save_notification(notification)
        
        # Dispatch to channels
        await self._dispatch_notification(notification)
        
        return notification
    
    async def create_first_blood_notification(
        self,
        user_id: UUID,
        challenge_id: UUID,
        challenge_name: str,
        points: int,
        team_name: Optional[str] = None,
    ) -> Notification:
        """Create first blood notification."""
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.FIRST_BLOOD.value,
            title="First Blood! 🩸",
            message=f"You secured the first blood on **{challenge_name}** for {points} points!",
            priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
            data={
                "challenge_id": str(challenge_id),
                "challenge_name": challenge_name,
                "points": points,
                "team_name": team_name,
            },
            icon="trophy",
        )
    
    async def create_challenge_unlock_notification(
        self,
        user_id: UUID,
        challenge_id: UUID,
        challenge_name: str,
        prerequisite_name: str = None,
    ) -> Notification:
        """Create challenge unlock notification."""
        message = f"**{challenge_name}** is now unlocked!"
        if prerequisite_name:
            message += f"\n\nPrerequisite: {prerequisite_name}"
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CHALLENGE_UNLOCK.value,
            title="Challenge Unlocked",
            message=message,
            priority=NotificationPriority.NORMAL,
            channels=[NotificationChannel.IN_APP],
            data={
                "challenge_id": str(challenge_id),
                "challenge_name": challenge_name,
            },
            icon="unlock",
        )
    
    async def create_team_invite_notification(
        self,
        user_id: UUID,
        inviter_id: UUID,
        inviter_name: str,
        team_id: UUID,
        team_name: str,
    ) -> Notification:
        """Create team invite notification."""
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.TEAM_INVITE.value,
            title="Team Invite",
            message=f"**{inviter_name}** has invited you to join **{team_name}**",
            priority=NotificationPriority.NORMAL,
            channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            data={
                "inviter_id": str(inviter_id),
                "inviter_name": inviter_name,
                "team_id": str(team_id),
                "team_name": team_name,
            },
            icon="users",
            action_url=f"/teams/{team_id}/join",
        )
    
    async def create_announcement_notification(
        self,
        user_ids: List[UUID],
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> List[Notification]:
        """Create announcement notification for multiple users."""
        notifications = []
        
        for user_id in user_ids:
            notification = await self.create_notification(
                user_id=user_id,
                notification_type=NotificationType.ANNOUNCEMENT.value,
                title=title,
                message=message,
                priority=priority,
                channels=[NotificationChannel.IN_APP],
                icon="announcement",
            )
            notifications.append(notification)
        
        return notifications
    
    # =========================================================================
    # Notification Dispatch
    # =========================================================================
    
    async def _dispatch_notification(
        self,
        notification: Notification,
    ) -> None:
        """Dispatch notification to all channels."""
        tasks = []
        
        for channel in notification.channels:
            if channel == NotificationChannel.IN_APP.value:
                tasks.append(self._dispatch_in_app(notification))
            elif channel == NotificationChannel.EMAIL.value:
                tasks.append(self._dispatch_email(notification))
            elif channel == NotificationChannel.PUSH.value:
                tasks.append(self._dispatch_push(notification))
            elif channel == NotificationChannel.WEBHOOK.value:
                tasks.append(self._dispatch_webhook(notification))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _dispatch_in_app(
        self,
        notification: Notification,
    ) -> None:
        """Dispatch in-app notification via WebSocket."""
        # This would integrate with the realtime server
        # Handled by the caller
        logger.debug(
            "In-app notification",
            notification_id=notification.id,
            user_id=str(notification.user_id),
        )
    
    async def _dispatch_email(
        self,
        notification: Notification,
    ) -> None:
        """Queue email notification."""
        # Queue to email service (RabbitMQ, Redis, etc.)
        await self.cache.redis_client.lpush(
            "email_queue",
            notification.model_dump_json(),
        )
        logger.debug(
            "Email notification queued",
            notification_id=notification.id,
        )
    
    async def _dispatch_push(
        self,
        notification: Notification,
    ) -> None:
        """Queue push notification."""
        # Queue to push notification service
        await self.cache.redis_client.lpush(
            "push_queue",
            notification.model_dump_json(),
        )
        logger.debug(
            "Push notification queued",
            notification_id=notification.id,
        )
    
    async def _dispatch_webhook(
        self,
        notification: Notification,
    ) -> None:
        """Send webhook notification."""
        for handler in self._webhook_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(notification)
                else:
                    handler(notification)
            except Exception as e:
                logger.error("Webhook handler error", error=str(e))
    
    def add_webhook_handler(
        self,
        handler: Callable[[Notification], None],
    ) -> None:
        """Add a webhook handler."""
        self._webhook_handlers.append(handler)
    
    # =========================================================================
    # Digest Mode
    # =========================================================================
    
    async def _queue_notification(
        self,
        notification: Notification,
    ) -> None:
        """Queue notification for digest delivery."""
        user_id = notification.user_id
        
        if user_id not in self._digest_queues:
            self._digest_queues[user_id] = []
        
        self._digest_queues[user_id].append(notification)
        
        # Trim queue to max size
        if len(self._digest_queues[user_id]) > self.digest_config.max_notifications_per_digest:
            self._digest_queues[user_id] = self._digest_queues[user_id][
                -self.digest_config.max_notifications_per_digest:
            ]
    
    async def _digest_worker(self) -> None:
        """Background task to send notification digests."""
        while self._running:
            try:
                await asyncio.sleep(self.digest_config.interval_minutes * 60)
                
                # Check quiet hours
                if self._is_quiet_hours():
                    continue
                
                # Send digests
                for user_id, notifications in list(self._digest_queues.items()):
                    if notifications:
                        await self._send_digest(user_id, notifications)
                        self._digest_queues[user_id] = []
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Digest worker error", error=str(e))
    
    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        if not self.digest_config.quiet_hours_start or not self.digest_config.quiet_hours_end:
            return False
        
        current_hour = datetime.utcnow().hour
        
        if self.digest_config.quiet_hours_start <= self.digest_config.quiet_hours_end:
            return self.digest_config.quiet_hours_start <= current_hour < self.digest_config.quiet_hours_end
        else:
            # Quiet hours span midnight
            return current_hour >= self.digest_config.quiet_hours_start or current_hour < self.digest_config.quiet_hours_end
    
    async def _send_digest(
        self,
        user_id: UUID,
        notifications: List[Notification],
    ) -> None:
        """Send a notification digest to a user."""
        if not notifications:
            return
        
        # Group notifications by type
        grouped = {}
        for n in notifications:
            if n.type not in grouped:
                grouped[n.type] = []
            grouped[n.type].append(n)
        
        # Create digest notification
        summary = self._generate_digest_summary(grouped)
        
        digest_notification = Notification(
            user_id=user_id,
            type="digest",
            title="Notification Digest",
            message=summary,
            priority=NotificationPriority.LOW,
            channels=[NotificationChannel.IN_APP.value],
            data={
                "notifications": [n.model_dump() for n in notifications],
                "grouped": {
                    k: len(v) for k, v in grouped.items()
                },
            },
        )
        
        await self._save_notification(digest_notification)
        await self._dispatch_in_app(digest_notification)
    
    def _generate_digest_summary(
        self,
        grouped: Dict[str, List[Notification]],
    ) -> str:
        """Generate a summary string for the digest."""
        lines = ["You have new notifications:"]
        
        type_labels = {
            NotificationType.FIRST_BLOOD.value: "First Bloods",
            NotificationType.CHALLENGE_UNLOCK.value: "Unlocked Challenges",
            NotificationType.CHALLENGE_SOLVE.value: "Challenge Solves",
            NotificationType.TEAM_INVITE.value: "Team Invites",
            NotificationType.ANNOUNCEMENT.value: "Announcements",
            NotificationType.SYSTEM.value: "System Messages",
        }
        
        for type_, notifications in grouped.items():
            label = type_labels.get(type_, type_)
            count = len(notifications)
            lines.append(f"• {count} {label}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # DND Management
    # =========================================================================
    
    async def set_dnd(
        self,
        user_id: UUID,
        enabled: bool,
        expires_at: datetime = None,
    ) -> None:
        """Set Do Not Disturb for a user."""
        if enabled:
            self._dnd_users.add(user_id)
            # Cache expiration
            if expires_at:
                await self.cache.redis_client.setex(
                    f"dnd:{user_id}",
                    int((expires_at - datetime.utcnow()).total_seconds()),
                    "1",
                )
        else:
            self._dnd_users.discard(user_id)
            await self.cache.redis_client.delete(f"dnd:{user_id}")
        
        logger.info("DND updated", user_id=str(user_id), enabled=enabled)
    
    async def _is_in_dnd(self, user_id: UUID) -> bool:
        """Check if user is in DND mode."""
        if user_id in self._dnd_users:
            return True
        
        # Check Redis
        in_dnd = await self.cache.redis_client.get(f"dnd:{user_id}")
        if in_dnd == "1":
            self._dnd_users.add(user_id)
            return True
        
        return False
    
    # =========================================================================
    # User Preferences
    # =========================================================================
    
    async def get_user_preferences(
        self,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """Get user notification preferences."""
        if user_id in self._preferences:
            return self._preferences[user_id]
        
        # Load from database/cache
        prefs = await self.cache.redis_client.hgetall(
            f"notification_prefs:{user_id}",
        )
        
        if not prefs:
            # Default preferences
            prefs = {
                "email_enabled": True,
                "push_enabled": True,
                "webhook_enabled": False,
                "digest_enabled": False,
                "dnd_enabled": False,
                "quiet_hours_start": 22,
                "quiet_hours_end": 8,
                "priority_notifications": True,
            }
        
        self._preferences[user_id] = prefs
        return prefs
    
    async def update_user_preferences(
        self,
        user_id: UUID,
        preferences: Dict[str, Any],
    ) -> None:
        """Update user notification preferences."""
        self._preferences[user_id] = {
            **await self.get_user_preferences(user_id),
            **preferences,
        }
        
        # Persist to Redis
        await self.cache.redis_client.hset(
            f"notification_prefs:{user_id}",
            self._preferences[user_id],
        )
        
        logger.info("Preferences updated", user_id=str(user_id))
    
    # =========================================================================
    # Database Operations
    # =========================================================================
    
    async def _save_notification(
        self,
        notification: Notification,
    ) -> None:
        """Save notification to database."""
        # Insert into notifications table
        await self.cache.redis_client.lpush(
            f"notifications:{notification.user_id}",
            notification.model_dump_json(),
        )
        
        # Trim to last 100 notifications
        await self.cache.redis_client.ltrim(
            f"notifications:{notification.user_id}",
            0,
            99,
        )
    
    async def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        unread_only: bool = False,
    ) -> List[Notification]:
        """Get notifications for a user."""
        key = f"notifications:{user_id}"
        notifications = await self.cache.redis_client.lrange(key, 0, limit - 1)
        
        result = []
        for n in notifications:
            notification = Notification(**n)
            if not unread_only or not notification.read:
                result.append(notification)
        
        return result
    
    async def mark_as_read(
        self,
        user_id: UUID,
        notification_id: str,
    ) -> bool:
        """Mark a notification as read."""
        key = f"notifications:{user_id}"
        notifications = await self.cache.redis_client.lrange(key, 0, -1)
        
        for i, n in enumerate(notifications):
            if n.get("id") == notification_id:
                n["read"] = True
                await self.cache.redis_client.lset(key, i, n)
                return True
        
        return False
    
    async def mark_all_read(
        self,
        user_id: UUID,
    ) -> int:
        """Mark all notifications as read."""
        key = f"notifications:{user_id}"
        notifications = await self.cache.redis_client.lrange(key, 0, -1)
        
        count = 0
        for i, n in enumerate(notifications):
            if not n.get("read", False):
                n["read"] = True
                await self.cache.redis_client.lset(key, i, n)
                count += 1
        
        return count
    
    # =========================================================================
    # Cleanup Worker
    # =========================================================================
    
    async def _cleanup_worker(self) -> None:
        """Background task to clean up expired notifications."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up old notifications from database
                cutoff = datetime.utcnow() - timedelta(days=30)
                
                # This would be a database cleanup operation
                logger.debug("Notification cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Cleanup worker error", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            "running": self._running,
            "digest_enabled": self.digest_config.enabled,
            "digest_interval_minutes": self.digest_config.interval_minutes,
            "dnd_users_count": len(self._dnd_users),
            "pending_digest_notifications": sum(len(q) for q in self._digest_queues.values()),
            "webhook_handlers_count": len(self._webhook_handlers),
        }
