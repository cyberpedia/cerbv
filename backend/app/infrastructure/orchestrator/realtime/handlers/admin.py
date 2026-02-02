"""
Admin Handler

Manages admin monitoring dashboards with:
- Active users tracking
- Real-time solve statistics
- System health monitoring
- Game state updates
- Audit logging
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

logger = structlog.get_logger(__name__)


class AdminHandler:
    """
    Handles admin monitoring and dashboard data.
    
    Provides real-time statistics for:
    - Active users and connections
    - Solve rates and trends
    - System health metrics
    - Game state monitoring
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        stats_history_size: int = 1000,
    ):
        self.db_manager = db_manager
        self.cache = cache_manager
        self.stats_history_size = stats_history_size
        
        # Statistics storage
        self._active_users: Set[UUID] = set()
        self._connection_history: List[Dict[str, Any]] = []
        self._solve_history: List[Dict[str, Any]] = []
        self._system_stats_history: List[Dict[str, Any]] = []
        
        # Monitoring tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("AdminHandler initialized")
    
    async def start(self) -> None:
        """Start background monitoring tasks."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_worker())
        logger.info("AdminHandler started")
    
    async def stop(self) -> None:
        """Stop background monitoring tasks."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AdminHandler stopped")
    
    # =========================================================================
    # Active Users
    # =========================================================================
    
    async def register_active_user(
        self,
        user_id: UUID,
        username: str,
        team_id: Optional[UUID] = None,
        role: str = "player",
    ) -> None:
        """Register a user as active."""
        self._active_users.add(user_id)
        
        # Store in Redis for distributed tracking
        await self.cache.redis_client.hset(
            "active_users",
            str(user_id),
            username,
        )
        
        await self._record_connection_event("connect", user_id, username, team_id, role)
    
    async def unregister_active_user(
        self,
        user_id: UUID,
    ) -> None:
        """Unregister an active user."""
        self._active_users.discard(user_id)
        
        await self.cache.redis_client.hdel("active_users", str(user_id))
        
        # Get username for history
        username = await self.cache.redis_client.hget("user_usernames", str(user_id))
        await self._record_connection_event("disconnect", user_id, username)
    
    async def get_active_users(self) -> List[Dict[str, Any]]:
        """Get list of active users with details."""
        users = []
        
        for user_id in self._active_users:
            user_data = await self.cache.redis_client.hgetall(f"user:{user_id}")
            if user_data:
                users.append({
                    "user_id": str(user_id),
                    "username": user_data.get("username"),
                    "team_id": user_data.get("team_id"),
                    "role": user_data.get("role"),
                    "connected_at": user_data.get("connected_at"),
                    "last_activity": user_data.get("last_activity"),
                })
        
        return users
    
    async def get_active_users_count(self) -> int:
        """Get count of active users."""
        # Try Redis first for distributed count
        redis_count = await self.cache.redis_client.hlen("active_users")
        if redis_count > 0:
            return redis_count
        return len(self._active_users)
    
    async def _record_connection_event(
        self,
        event_type: str,
        user_id: UUID,
        username: str,
        team_id: Optional[UUID] = None,
        role: str = "player",
    ) -> None:
        """Record connection event to history."""
        event = {
            "type": event_type,
            "user_id": str(user_id),
            "username": username,
            "team_id": str(team_id) if team_id else None,
            "role": role,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self._connection_history.append(event)
        
        # Trim history
        if len(self._connection_history) > self.stats_history_size:
            self._connection_history = self._connection_history[-self.stats_history_size:]
        
        # Store in Redis for distribution
        await self.cache.redis_client.lpush(
            "connection_history",
            event,
        )
    
    # =========================================================================
    # Solve Statistics
    # =========================================================================
    
    async def record_solve(
        self,
        user_id: UUID,
        team_id: Optional[UUID],
        challenge_id: UUID,
        points: int,
        is_first_blood: bool = False,
    ) -> None:
        """Record a challenge solve."""
        event = {
            "user_id": str(user_id),
            "team_id": str(team_id) if team_id else None,
            "challenge_id": str(challenge_id),
            "points": points,
            "is_first_blood": is_first_blood,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self._solve_history.append(event)
        
        # Trim history
        if len(self._solve_history) > self.stats_history_size:
            self._solve_history = self._solve_history[-self.stats_history_size:]
        
        # Store in Redis
        await self.cache.redis_client.lpush(
            "solve_history",
            event,
        )
        
        # Update counters
        await self.cache.redis_client.incr("total_solves")
        if is_first_blood:
            await self.cache.redis_client.incr("total_first_bloods")
    
    async def get_solve_stats(
        self,
        time_range_hours: int = 24,
    ) -> Dict[str, Any]:
        """Get solve statistics for a time range."""
        cutoff = datetime.utcnow() - timedelta(hours=time_range_hours)
        
        # Filter solves by time range
        recent_solves = [
            s for s in self._solve_history
            if datetime.fromisoformat(s["timestamp"]) > cutoff
        ]
        
        # Group by hour
        hourly_solves: Dict[str, int] = {}
        for solve in recent_solves:
            hour = solve["timestamp"][:13]  # YYYY-MM-DDTHH
            hourly_solves[hour] = hourly_solves.get(hour, 0) + 1
        
        # Calculate statistics
        total_points = sum(s["points"] for s in recent_solves)
        first_bloods = sum(1 for s in recent_solves if s["is_first_blood"])
        
        return {
            "total_solves": len(recent_solves),
            "total_points": total_points,
            "first_bloods": first_bloods,
            "hourly_breakdown": hourly_solves,
            "time_range_hours": time_range_hours,
        }
    
    async def get_challenge_solve_counts(self) -> Dict[str, int]:
        """Get solve count per challenge."""
        counts = {}
        
        for solve in self._solve_history:
            challenge_id = solve["challenge_id"]
            counts[challenge_id] = counts.get(challenge_id, 0) + 1
        
        return counts
    
    # =========================================================================
    # System Health
    # =========================================================================
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        # Get Redis stats
        info = await self.cache.redis_client.info("stats")
        
        # Get memory usage
        memory = await self.cache.redis_client.info("memory")
        
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "redis": {
                "connected_clients": info.get("connected_clients", 0),
                "total_connections_received": info.get("total_connections_received", 0),
                "ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
                "used_memory": memory.get("used_memory", 0),
                "used_memory_human": memory.get("used_memory_human", "0"),
            },
            "active_users": await self.get_active_users_count(),
            "recent_solves": len(self._solve_history),
            "connection_events": len(self._connection_history),
        }
        
        # Record to history
        self._system_stats_history.append(stats)
        if len(self._system_stats_history) > self.stats_history_size:
            self._system_stats_history = self._system_stats_history[-self.stats_history_size:]
        
        return stats
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        stats = await self.get_system_stats()
        
        # Check thresholds
        memory_mb = stats["redis"]["used_memory"] / (1024 * 1024)
        
        health = {
            "status": "healthy",
            "checks": {
                "redis": "ok",
                "memory": "ok" if memory_mb < 512 else "warning",
                "connections": "ok",
            },
            "details": stats,
        }
        
        # Determine overall status
        if health["checks"].get("memory") == "warning":
            health["status"] = "degraded"
        
        return health
    
    # =========================================================================
    # Game State
    # =========================================================================
    
    async def get_game_state(self) -> Dict[str, Any]:
        """Get current game state for admin dashboard."""
        return {
            "start_time": await self.cache.redis_client.get("game_start_time"),
            "end_time": await self.cache.redis_client.get("game_end_time"),
            "paused": await self.cache.redis_client.get("game_paused") == "true",
            "scoreboard_frozen": await self.cache.redis_client.get("scoreboard_frozen") == "true",
            "anonymous_mode": await self.cache.redis_client.get("anonymous_mode") == "true",
            "current_tick": await self.cache.redis_client.get("ad_current_tick"),
            "teams_count": await self.cache.redis_client.scard("active_teams"),
            "challenges_count": await self.cache.redis_client.scard("active_challenges"),
        }
    
    async def update_game_state(
        self,
        updates: Dict[str, Any],
    ) -> None:
        """Update game state."""
        for key, value in updates.items():
            if value is None:
                await self.cache.redis_client.delete(f"game_{key}")
            else:
                await self.cache.redis_client.set(f"game_{key}", str(value))
        
        logger.info("Game state updated", updates=updates)
    
    # =========================================================================
    # Audit Log
    # =========================================================================
    
    async def log_admin_action(
        self,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: str,
        details: Dict[str, Any] = None,
    ) -> None:
        """Log an admin action for audit."""
        log_entry = {
            "admin_id": str(admin_id),
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": None,  # Should be passed from request context
        }
        
        # Store in Redis list with expiration
        await self.cache.redis_client.lpush(
            "admin_audit_log",
            log_entry,
        )
        
        # Trim to last 10000 entries
        await self.cache.redis_client.ltrim("admin_audit_log", 0, 9999)
        
        logger.info(
            "Admin action logged",
            admin_id=str(admin_id),
            action=action,
            target_type=target_type,
        )
    
    async def get_audit_log(
        self,
        limit: int = 100,
        admin_id: Optional[UUID] = None,
        action_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        logs = await self.cache.redis_client.lrange("admin_audit_log", 0, limit - 1)
        
        # Filter if needed
        if admin_id:
            logs = [l for l in logs if l.get("admin_id") == str(admin_id)]
        if action_type:
            logs = [l for l in logs if l.get("action") == action_type]
        
        return logs
    
    # =========================================================================
    # Monitoring Worker
    # =========================================================================
    
    async def _monitor_worker(self) -> None:
        """Background worker for periodic monitoring tasks."""
        while self._running:
            try:
                # Record system stats every minute
                await self.get_system_stats()
                
                # Update active users list from Redis
                redis_users = await self.cache.redis_client.hgetall("active_users")
                self._active_users = {UUID(u) for u in redis_users.keys()}
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Monitor worker error", error=str(e))
                await asyncio.sleep(5)
    
    # =========================================================================
    # Dashboard Data
    # =========================================================================
    
    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get summary data for admin dashboard."""
        return {
            "system": await self.get_system_stats(),
            "health": await self.get_system_health(),
            "game": await self.get_game_state(),
            "solves_24h": await self.get_solve_stats(24),
            "active_users": await self.get_active_users_count(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def get_solves_timeline(
        self,
        time_range_hours: int = 24,
        granularity_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """Get timeline of solves for graphing."""
        cutoff = datetime.utcnow() - timedelta(hours=time_range_hours)
        
        # Group solves by time bucket
        timeline: Dict[str, Dict[str, Any]] = {}
        
        for solve in self._solve_history:
            solve_time = datetime.fromisoformat(solve["timestamp"])
            if solve_time < cutoff:
                continue
            
            # Calculate bucket
            bucket_minute = (solve_time.minute // granularity_minutes) * granularity_minutes
            bucket_key = solve_time.replace(
                minute=bucket_minute,
                second=0,
                microsecond=0,
            ).isoformat()
            
            if bucket_key not in timeline:
                timeline[bucket_key] = {
                    "timestamp": bucket_key,
                    "solves": 0,
                    "points": 0,
                    "first_bloods": 0,
                }
            
            timeline[bucket_key]["solves"] += 1
            timeline[bucket_key]["points"] += solve["points"]
            if solve["is_first_blood"]:
                timeline[bucket_key]["first_bloods"] += 1
        
        return sorted(timeline.values(), key=lambda x: x["timestamp"])
    
    async def get_challenge_difficulty_stats(self) -> Dict[str, Any]:
        """Get challenge difficulty statistics."""
        # Group challenges by solve count
        solve_counts = await self.get_challenge_solve_counts()
        
        easy = sum(1 for c in solve_counts.values() if c >= 10)
        medium = sum(1 for c in solve_counts.values() if 1 <= c < 10)
        hard = sum(1 for c in solve_counts.values() if c == 0)
        
        return {
            "easy_solves": easy,
            "medium_solves": medium,
            "hard_solves": hard,
            "unsolved": hard,
            "total_challenges": len(solve_counts),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            "running": self._running,
            "active_users_count": len(self._active_users),
            "connection_history_size": len(self._connection_history),
            "solve_history_size": len(self._solve_history),
            "system_stats_history_size": len(self._system_stats_history),
        }
