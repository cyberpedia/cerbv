"""
Attack-Defense Tick Scheduler

Manages AD game tick scheduling with:
- Cron-like tick intervals (default 300s)
- Flag rotation broadcasting
- Service status updates
- Real-time score calculations
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

logger = structlog.get_logger(__name__)


class ADTickScheduler:
    """
    Attack-Defense Game Tick Scheduler.
    
    Manages the tick-based gameplay with:
    - Scheduled tick broadcasts
    - Flag rotation
    - Service health checks
    - Real-time scoring
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        tick_duration_seconds: int = 300,  # 5 minutes default
        flag_rotation_interval: int = 3,  # Rotate flags every N ticks
    ):
        self.db_manager = db_manager
        self.cache = cache_manager
        self.tick_duration = tick_duration_seconds
        self.flag_rotation_interval = flag_rotation_interval
        
        # Game state
        self._current_tick = 0
        self._game_start_time: Optional[datetime] = None
        self._game_end_time: Optional[datetime] = None
        self._game_paused = False
        self._services: Dict[str, Dict[str, Any]] = {}
        self._flags: Dict[str, str] = {}
        
        # Scheduler state
        self._running = False
        self._tick_task: Optional[asyncio.Task] = None
        self._tick_countdown_task: Optional[asyncio.Task] = None
        
        # Event callbacks
        self._on_tick_callbacks: List[Callable] = []
        self._on_flag_rotation_callbacks: List[Callable] = []
        self._on_service_status_callbacks: List[Callable] = []
        
        # Score cache
        self._scores: Dict[str, int] = {}
        
        logger.info("ADTickScheduler initialized", tick_duration=self.tick_duration)
    
    async def start(self, game_duration_hours: int = 8) -> None:
        """Start the AD game scheduler."""
        if self._running:
            return
        
        self._running = True
        self._game_start_time = datetime.utcnow()
        self._game_end_time = self._game_start_time + timedelta(hours=game_duration_hours)
        
        # Store game times
        await self.cache.redis_client.set("ad_game_start", self._game_start_time.isoformat())
        await self.cache.redis_client.set("ad_game_end", self._game_end_time.isoformat())
        
        # Start tick scheduler
        self._tick_task = asyncio.create_task(self._tick_loop())
        
        # Start countdown updater
        self._tick_countdown_task = asyncio.create_task(self._countdown_loop())
        
        logger.info(
            "ADTickScheduler started",
            start_time=self._game_start_time.isoformat(),
            end_time=self._game_end_time.isoformat(),
        )
    
    async def stop(self) -> None:
        """Stop the AD game scheduler."""
        self._running = False
        
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
        
        if self._tick_countdown_task:
            self._tick_countdown_task.cancel()
            try:
                await self._tick_countdown_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ADTickScheduler stopped")
    
    async def pause(self) -> None:
        """Pause the game."""
        self._game_paused = True
        await self.cache.redis_client.set("ad_game_paused", "true")
        logger.info("AD game paused")
    
    async def resume(self) -> None:
        """Resume the game."""
        self._game_paused = False
        await self.cache.redis_client.delete("ad_game_paused")
        logger.info("AD game resumed")
    
    # =========================================================================
    # Tick Management
    # =========================================================================
    
    async def _tick_loop(self) -> None:
        """Main tick loop."""
        while self._running:
            try:
                # Wait for tick duration
                await asyncio.sleep(self.tick_duration)
                
                if not self._game_paused:
                    # Check if game should end
                    if datetime.utcnow() >= self._game_end_time:
                        await self._end_game()
                        break
                    
                    # Increment tick
                    self._current_tick += 1
                    
                    # Store current tick
                    await self.cache.redis_client.set("ad_current_tick", str(self._current_tick))
                    
                    # Execute tick
                    await self._execute_tick()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Tick loop error", error=str(e))
                await asyncio.sleep(5)
    
    async def _countdown_loop(self) -> None:
        """Update countdown timer periodically."""
        while self._running:
            try:
                if self._game_end_time and not self._game_paused:
                    remaining = (self._game_end_time - datetime.utcnow()).total_seconds()
                    if remaining > 0:
                        await self.cache.redis_client.setex(
                            "ad_time_remaining",
                            int(remaining),
                            str(int(remaining)),
                        )
                
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Countdown loop error", error=str(e))
    
    async def _execute_tick(self) -> None:
        """Execute a tick: calculate scores, check services, rotate flags."""
        logger.info("Executing tick", tick=self._current_tick)
        
        # Calculate scores
        scores = await self._calculate_scores()
        
        # Check service status
        service_status = await self._check_services()
        
        # Flag rotation
        if self._current_tick % self.flag_rotation_interval == 0:
            await self._rotate_flags()
        
        # Broadcast tick event
        tick_data = {
            "tick_number": self._current_tick,
            "scores": scores,
            "services": service_status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Invoke callbacks
        for callback in self._on_tick_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tick_data)
                else:
                    callback(tick_data)
            except Exception as e:
                logger.exception("Tick callback error", error=str(e))
        
        logger.debug("Tick executed", tick=self._current_tick)
    
    async def _end_game(self) -> None:
        """End the game and broadcast final results."""
        logger.info("AD game ended")
        
        final_scores = await self._calculate_scores()
        
        # Sort by score
        sorted_scores = sorted(
            final_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        results = {
            "final_scores": sorted_scores,
            "game_duration_ticks": self._current_tick,
            "ended_at": datetime.utcnow().isoformat(),
        }
        
        # Store final results
        await self.cache.redis_client.set("ad_final_results", str(results))
        
        # Invoke callbacks
        for callback in self._on_tick_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback({"type": "game_end", "data": results})
                else:
                    callback({"type": "game_end", "data": results})
            except Exception as e:
                logger.exception("Game end callback error", error=str(e))
    
    # =========================================================================
    # Score Calculation
    # =========================================================================
    
    async def _calculate_scores(self) -> Dict[str, int]:
        """
        Calculate scores for all teams.
        
        Score formula:
        - Defense points: Points for keeping services up
        - Attack points: Points for capturing flags
        - SLA penalty: Points lost for service downtime
        """
        scores: Dict[str, int] = {}
        
        # Get all active teams
        team_ids = await self.cache.redis_client.smembers("active_teams")
        
        for team_id in team_ids:
            defense_score = 0
            attack_score = 0
            sla_penalty = 0
            
            # Calculate from service status
            for service_id, service in self._services.items():
                team_service_key = f"service:{service_id}:team:{team_id}"
                is_up = await self.cache.redis_client.get(f"{team_service_key}:up")
                
                if is_up == "true":
                    defense_score += service.get("defense_points", 10)
                else:
                    # SLA penalty
                    downtime = await self.cache.redis_client.get(f"{team_service_key}:downtime")
                    sla_penalty += int(downtime or 0) * service.get("sla_penalty_per_minute", 1)
            
            # Get attack points from flag captures
            captures = await self.cache.redis_client.lrange(
                f"flag_captures:team:{team_id}",
                0,
                -1,
            )
            attack_score = len(captures) * 100  # 100 points per flag
            
            total = max(0, defense_score + attack_score - sla_penalty)
            scores[team_id] = total
        
        self._scores = scores
        return scores
    
    def get_team_score(self, team_id: str) -> Optional[int]:
        """Get a specific team's score."""
        return self._scores.get(team_id)
    
    # =========================================================================
    # Service Management
    # =========================================================================
    
    async def register_service(
        self,
        service_id: str,
        name: str,
        port: int,
        defense_points: int = 100,
        sla_penalty_per_minute: int = 10,
    ) -> None:
        """Register a service for the game."""
        self._services[service_id] = {
            "name": name,
            "port": port,
            "defense_points": defense_points,
            "sla_penalty_per_minute": sla_penalty_per_minute,
        }
        
        # Store in Redis
        await self.cache.redis_client.hset(
            "ad_services",
            service_id,
            str({
                "name": name,
                "port": port,
                "defense_points": defense_points,
            }),
        )
        
        logger.info("Service registered", service_id=service_id, name=name)
    
    async def unregister_service(self, service_id: str) -> None:
        """Unregister a service."""
        if service_id in self._services:
            del self._services[service_id]
            await self.cache.redis_client.hdel("ad_services", service_id)
            logger.info("Service unregistered", service_id=service_id)
    
    async def _check_services(self) -> List[Dict[str, Any]]:
        """
        Check status of all registered services.
        
        Returns:
            List of service status updates
        """
        statuses = []
        
        for service_id, service in self._services.items():
            status = {
                "service_id": service_id,
                "name": service["name"],
                "status": "unknown",
                "teams_up": 0,
                "teams_total": len(await self.cache.redis_client.smembers("active_teams")),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Get team-specific service status
            team_statuses = await self.cache.redis_client.hgetall(
                f"service_status:{service_id}",
            )
            
            up_count = sum(1 for v in team_statuses.values() if v == "up")
            status["teams_up"] = up_count
            status["status"] = "healthy" if up_count == status["teams_total"] else "degraded"
            
            statuses.append(status)
            
            # Update service status in Redis
            await self.cache.redis_client.hset(
                f"ad_service_status",
                service_id,
                str(status),
            )
        
        # Invoke callbacks
        for callback in self._on_service_status_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(statuses)
                else:
                    callback(statuses)
            except Exception as e:
                logger.exception("Service status callback error", error=str(e))
        
        return statuses
    
    async def update_service_status(
        self,
        service_id: str,
        team_id: str,
        is_up: bool,
    ) -> None:
        """Update a team's service status."""
        status = "up" if is_up else "down"
        
        await self.cache.redis_client.hset(
            f"service_status:{service_id}",
            team_id,
            status,
        )
        
        logger.debug(
            "Service status updated",
            service_id=service_id,
            team_id=team_id,
            status=status,
        )
    
    # =========================================================================
    # Flag Management
    # =========================================================================
    
    async def _rotate_flags(self) -> None:
        """Rotate all active flags."""
        logger.info("Rotating flags", tick=self._current_tick)
        
        # Generate new flags
        new_flags: List[Dict[str, Any]] = []
        
        for service_id in self._services.keys():
            # Generate new flag
            new_flag = f"FLAG-{UUID.uuid4().hex[:32]}"
            old_flag = self._flags.get(service_id)
            
            self._flags[service_id] = new_flag
            
            new_flags.append({
                "service_id": service_id,
                "old_flag_hash": hash(old_flag) if old_flag else None,
                "new_flag": new_flag,
                "rotated_at": datetime.utcnow().isoformat(),
            })
            
            # Store flag in Redis for validation
            await self.cache.redis_client.set(
                f"ad_flag:{service_id}:current",
                new_flag,
            )
            
            # Store flag history
            await self.cache.redis_client.lpush(
                f"ad_flag_history:{service_id}",
                str({
                    "flag": new_flag,
                    "tick": self._current_tick,
                    "timestamp": datetime.utcnow().isoformat(),
                }),
            )
        
        # Broadcast flag rotation
        rotation_data = {
            "tick": self._current_tick,
            "flags": new_flags,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        for callback in self._on_flag_rotation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(rotation_data)
                else:
                    callback(rotation_data)
            except Exception as e:
                logger.exception("Flag rotation callback error", error=str(e))
    
    async def submit_flag(
        self,
        team_id: str,
        service_id: str,
        flag: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Submit a captured flag.
        
        Returns:
            Result with success status and points
        """
        # Validate flag
        current_flag = await self.cache.redis_client.get(
            f"ad_flag:{service_id}:current",
        )
        
        if not current_flag:
            return {
                "valid": False,
                "message": "No active flag for this service",
            }
        
        if flag != current_flag:
            # Check if it's a recently expired flag
            flag_history = await self.cache.redis_client.lrange(
                f"ad_flag_history:{service_id}",
                0,
                10,
            )
            
            for hist in flag_history:
                hist_data = eval(hist)
                if hist_data.get("flag") == flag:
                    return {
                        "valid": False,
                        "message": "Flag has already expired",
                    }
            
            return {
                "valid": False,
                "message": "Invalid flag",
            }
        
        # Check if already submitted by this team
        already_submitted = await self.cache.redis_client.sismember(
            f"ad_flag_submissions:{service_id}",
            team_id,
        )
        
        if already_submitted:
            return {
                "valid": False,
                "message": "Flag already submitted by your team",
            }
        
        # Record submission
        await self.cache.redis_client.sadd(
            f"ad_flag_submissions:{service_id}",
            team_id,
        )
        
        await self.cache.redis_client.lpush(
            f"flag_captures:team:{team_id}",
            str({
                "service_id": service_id,
                "flag": flag,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
            }),
        )
        
        # Award points
        points = 100  # Base flag capture points
        
        logger.info(
            "Flag submitted",
            team_id=team_id,
            service_id=service_id,
            points=points,
        )
        
        return {
            "valid": True,
            "message": "Flag captured!",
            "points": points,
            "service_id": service_id,
        }
    
    # =========================================================================
    # Callbacks
    # =========================================================================
    
    def on_tick(self, callback: Callable) -> None:
        """Register a callback for tick events."""
        self._on_tick_callbacks.append(callback)
    
    def on_flag_rotation(self, callback: Callable) -> None:
        """Register a callback for flag rotation events."""
        self._on_flag_rotation_callbacks.append(callback)
    
    def on_service_status(self, callback: Callable) -> None:
        """Register a callback for service status changes."""
        self._on_service_status_callbacks.append(callback)
    
    # =========================================================================
    # State Access
    # =========================================================================
    
    async def get_game_state(self) -> Dict[str, Any]:
        """Get current game state."""
        return {
            "current_tick": self._current_tick,
            "start_time": self._game_start_time.isoformat() if self._game_start_time else None,
            "end_time": self._game_end_time.isoformat() if self._game_end_time else None,
            "paused": self._game_paused,
            "services_count": len(self._services),
            "scores": self._scores,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "running": self._running,
            "current_tick": self._current_tick,
            "tick_duration_seconds": self.tick_duration,
            "services_count": len(self._services),
            "paused": self._game_paused,
        }
