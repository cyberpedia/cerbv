"""
Attack-Defense (AD) Manager Service

Manages tick-based Attack-Defense CTF games with:
- Tick scheduling and synchronization
- Deterministic flag generation using HMAC-SHA256
- Service health checking
- SLA, Offense, and Defense scoring
"""

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

from ..models_advanced import (
    ADGame,
    ADGameConfig,
    ADGameStatus,
    ADFlag,
    ADFlagStatus,
    ADScore,
    ADSubmission,
)

logger = structlog.get_logger(__name__)


class FlagGenerator:
    """Generates deterministic per-service-team flags using HMAC-SHA256."""
    
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key
    
    def generate_flag(
        self,
        game_id: UUID,
        service_id: str,
        team_id: UUID,
        tick: int,
    ) -> str:
        """
        Generate a deterministic flag for a specific game, service, team, and tick.
        
        Args:
            game_id: The AD game UUID
            service_id: The service identifier
            team_id: The team UUID
            tick: The current game tick
            
        Returns:
            The generated flag string (e.g., "FLAG{service_team_tick_hash}")
        """
        # Create deterministic input
        input_data = f"{game_id}:{service_id}:{team_id}:{tick}"
        
        # Generate HMAC-SHA256 hash
        flag_hash = hmac.new(
            self.secret_key,
            input_data.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        
        # Format flag with prefix
        return f"FLAG{{{service_id}_{str(team_id)[:8]}_{tick}_{flag_hash}}}"
    
    def verify_flag(
        self,
        flag: str,
        game_id: UUID,
        service_id: str,
        team_id: UUID,
        tick: int,
    ) -> bool:
        """
        Verify if a flag matches the expected format and hash.
        
        Args:
            flag: The submitted flag
            game_id: The AD game UUID
            service_id: The service identifier
            team_id: The team UUID
            tick: The current game tick
            
        Returns:
            True if the flag is valid
        """
        try:
            # Parse flag format: FLAG{service_team_tick_hash}
            if not flag.startswith("FLAG{") or not flag.endswith("}"):
                return False
            
            content = flag[5:-1]  # Remove FLAG{ and }
            parts = content.split("_")
            
            if len(parts) != 4:
                return False
            
            submitted_service = parts[0]
            submitted_team = parts[1]
            submitted_tick = int(parts[2])
            submitted_hash = parts[3]
            
            # Verify components
            if submitted_service != service_id:
                return False
            if submitted_tick != tick:
                return False
            if submitted_team != str(team_id)[:8]:
                return False
            
            # Verify hash
            expected_flag = self.generate_flag(game_id, service_id, team_id, tick)
            return hmac.compare_digest(flag, expected_flag)
            
        except (ValueError, IndexError):
            return False


class BaseChecker:
    """Base class for service checkers."""
    
    def check_service(self, team_id: UUID, connection_info: Dict) -> bool:
        """
        Check if a service is healthy for a team.
        
        Args:
            team_id: The team UUID
            connection_info: Connection details (host, port, etc.)
            
        Returns:
            True if service is healthy
        """
        raise NotImplementedError
    
    def put_flag(
        self,
        team_id: UUID,
        flag: str,
        tick: int,
        connection_info: Dict,
    ) -> bool:
        """
        Place a flag in the service for SLA verification.
        
        Args:
            team_id: The team UUID
            flag: The flag to place
            tick: The current tick
            connection_info: Connection details
            
        Returns:
            True if flag was placed successfully
        """
        raise NotImplementedError
    
    def get_flag(
        self,
        team_id: UUID,
        flag: str,
        tick: int,
        connection_info: Dict,
    ) -> bool:
        """
        Verify that a flag exists in the service (for SLA defense).
        
        Args:
            team_id: The team UUID
            flag: The flag to verify
            tick: The current tick
            connection_info: Connection details
            
        Returns:
            True if flag is present
        """
        raise NotImplementedError


class CheckerRunner:
    """Executes service health checks via asyncio subprocesses."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self._checkers: Dict[str, BaseChecker] = {}
        self._checker_timeout = 30  # seconds
    
    def register_checker(self, service_id: str, checker: BaseChecker) -> None:
        """Register a checker for a service."""
        self._checkers[service_id] = checker
    
    async def run_check(
        self,
        service_id: str,
        team_id: UUID,
        connection_info: Dict,
    ) -> bool:
        """Run a service health check."""
        checker = self._checkers.get(service_id)
        if not checker:
            logger.warning("No checker registered for service", service_id=service_id)
            return False
        
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    checker.check_service,
                    team_id,
                    connection_info,
                ),
                timeout=self._checker_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error("Checker timeout", service_id=service_id, team_id=str(team_id))
            return False
        except Exception as e:
            logger.exception("Checker error", service_id=service_id, error=str(e))
            return False


class ScoreCalculator:
    """Calculates SLA, Offense, and Defense points."""
    
    def __init__(self, config: ADGameConfig):
        self.config = config
    
    def calculate_sla_points(
        self,
        service_healthy: bool,
        team_kept_flag: bool,
    ) -> int:
        """
        Calculate SLA points for a team.
        
        SLA points awarded for:
        - Service is healthy (100 pts)
        - Team kept their flag (100 pts)
        
        Args:
            service_healthy: Whether service was healthy this tick
            team_kept_flag: Whether team defended their flag
            
        Returns:
            SLA points for this tick
        """
        points = 0
        if service_healthy:
            points += self.config.sla_points_per_tick
        if team_kept_flag:
            points += self.config.defense_points_per_flag
        return points
    
    def calculate_offense_points(self, flags_captured: int) -> int:
        """
        Calculate offense points for flags captured.
        
        Args:
            flags_captured: Number of enemy flags captured
            
        Returns:
            Offense points
        """
        return flags_captured * self.config.offense_points_per_flag
    
    def calculate_total_score(
        self,
        sla_points: int,
        offense_points: int,
        defense_points: int,
    ) -> int:
        """Calculate total score."""
        return sla_points + offense_points + defense_points


class ADManager:
    """
    Main AD game manager handling tick scheduling and coordination.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        flag_secret_key: bytes,
        tick_duration: int = 300,
    ):
        self.db = db_manager
        self.cache = cache_manager
        
        # Core components
        self.flag_generator = FlagGenerator(flag_secret_key)
        self.checker_runner = CheckerRunner(cache_manager)
        self.score_calculator = ScoreCalculator(ADGameConfig())
        
        # Game state
        self._active_games: Dict[UUID, ADGame] = {}
        self._game_locks: Dict[UUID, asyncio.Lock] = {}
        self._tick_tasks: Dict[UUID, asyncio.Task] = {}
        
        # Configuration
        self._tick_duration = tick_duration
        self._running = False
        
        # Rate limiting for submissions
        self._submission_rate_limit = 10  # max submissions per tick per team
        self._submission_timestamps: Dict[str, List[datetime]] = {}
    
    async def start(self) -> None:
        """Start the AD manager."""
        self._running = True
        logger.info("AD Manager started", tick_duration=self._tick_duration)
    
    async def stop(self) -> None:
        """Stop the AD manager and all active games."""
        self._running = False
        
        # Cancel all tick tasks
        for task in self._tick_tasks.values():
            task.cancel()
        
        logger.info("AD Manager stopped")
    
    def _get_game_lock(self, game_id: UUID) -> asyncio.Lock:
        """Get or create a lock for a game."""
        if game_id not in self._game_locks:
            self._game_locks[game_id] = asyncio.Lock()
        return self._game_locks[game_id]
    
    async def create_game(
        self,
        challenge_id: UUID,
        name: str,
        team_ids: List[UUID],
        service_ids: List[str],
        tick_duration: Optional[int] = None,
    ) -> ADGame:
        """
        Create a new AD game.
        
        Args:
            challenge_id: The challenge UUID
            name: Game name
            team_ids: List of participating team UUIDs
            service_ids: List of service IDs to be attacked/defended
            tick_duration: Override for tick duration
            
        Returns:
            The created ADGame
        """
        game = ADGame(
            id=uuid4(),
            challenge_id=challenge_id,
            name=name,
            config=ADGameConfig(
                tick_duration=tick_duration or self._tick_duration,
                team_count=len(team_ids),
                service_ids=service_ids,
            ),
            status=ADGameStatus.PENDING,
        )
        
        async with self._get_game_lock(game.id):
            self._active_games[game.id] = game
        
        logger.info(
            "AD game created",
            game_id=str(game.id),
            name=name,
            team_count=len(team_ids),
            service_count=len(service_ids),
        )
        
        return game
    
    async def start_game(self, game_id: UUID) -> bool:
        """
        Start an AD game.
        
        Args:
            game_id: The game UUID
            
        Returns:
            True if started successfully
        """
        async with self._get_game_lock(game_id):
            game = self._active_games.get(game_id)
            if not game:
                return False
            
            if game.status != ADGameStatus.PENDING:
                return False
            
            game.status = ADGameStatus.RUNNING
            game.started_at = datetime.utcnow()
            
            # Start tick loop
            self._tick_tasks[game_id] = asyncio.create_task(
                self._tick_loop(game_id)
            )
            
            logger.info("AD game started", game_id=str(game_id))
            
            # Emit WebSocket event
            await self._emit_event("ad.game_started", {"game_id": str(game_id)})
            
            return True
    
    async def stop_game(self, game_id: UUID) -> bool:
        """
        Stop an AD game.
        
        Args:
            game_id: The game UUID
            
        Returns:
            True if stopped successfully
        """
        async with self._get_game_lock(game_id):
            game = self._active_games.get(game_id)
            if not game:
                return False
            
            # Cancel tick task
            task = self._tick_tasks.pop(game_id, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            game.status = ADGameStatus.FINISHED
            game.ended_at = datetime.utcnow()
            
            logger.info("AD game stopped", game_id=str(game_id))
            
            # Emit WebSocket event
            await self._emit_event("ad.game_stopped", {"game_id": str(game_id)})
            
            return True
    
    async def _tick_loop(self, game_id: UUID) -> None:
        """Main tick loop for a game."""
        game = self._active_games.get(game_id)
        if not game:
            return
        
        while game.status == ADGameStatus.RUNNING and game.current_tick < game.config.total_ticks:
            try:
                await asyncio.sleep(game.config.tick_duration)
                
                if game.status != ADGameStatus.RUNNING:
                    break
                
                await self._execute_tick(game_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Tick loop error", game_id=str(game_id), error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry
        
        # Game finished
        if game.status == ADGameStatus.RUNNING:
            await self.stop_game(game_id)
    
    async def _execute_tick(self, game_id: UUID) -> None:
        """Execute a single tick."""
        game = self._active_games.get(game_id)
        if not game:
            return
        
        async with self._get_game_lock(game_id):
            game.current_tick += 1
            tick = game.current_tick
            
            logger.info("Executing tick", game_id=str(game_id), tick=tick)
            
            # Generate new flags for all teams and services
            for team_id in await self._get_game_teams(game_id):
                for service_id in game.config.service_ids:
                    # Generate flag
                    flag = self.flag_generator.generate_flag(
                        game_id, service_id, team_id, tick
                    )
                    
                    # Store flag
                    ad_flag = ADFlag(
                        id=uuid4(),
                        game_id=game_id,
                        tick=tick,
                        service_id=service_id,
                        team_id=team_id,
                        flag_hash=flag,
                        status=ADFlagStatus.ACTIVE,
                    )
                    await self._store_flag(ad_flag)
                    
                    # Put flag in service (for SLA verification)
                    await self._put_flag_in_service(team_id, service_id, flag, tick)
            
            # Run service health checks
            service_health = await self._run_health_checks(game_id, tick)
            
            # Calculate scores for this tick
            await self._calculate_tick_scores(game_id, tick, service_health)
            
            # Expire old flags
            await self._expire_old_flags(game_id, tick)
            
            # Emit new tick event
            await self._emit_event("ad.new_tick", {
                "game_id": str(game_id),
                "tick": tick,
                "current_tick": game.current_tick,
                "total_ticks": game.config.total_ticks,
            })
    
    async def _put_flag_in_service(
        self,
        team_id: UUID,
        service_id: str,
        flag: str,
        tick: int,
    ) -> bool:
        """Put a flag in a service for SLA verification."""
        checker = self.checker_runner._checkers.get(service_id)
        if not checker:
            return False
        
        try:
            connection_info = await self._get_service_connection(team_id, service_id)
            return await asyncio.to_thread(
                checker.put_flag,
                team_id,
                flag,
                tick,
                connection_info,
            )
        except Exception as e:
            logger.exception("Failed to put flag", error=str(e))
            return False
    
    async def _get_service_connection(
        self,
        team_id: UUID,
        game_id: UUID,
        service_id: str,
    ) -> Dict:
        """Get connection info for a team's service."""
        # Get from cache or database
        cache_key = f"ad:service:{game_id}:{team_id}:{service_id}"
        connection_info = await self.cache.get(cache_key)
        
        if not connection_info:
            # Default based on team VLAN
            team_vlan = 10 + (hash(str(team_id)) % 200)
            connection_info = {
                "host": f"10.{team_vlan}.0.1",
                "port": self._get_service_port(service_id),
            }
        
        return connection_info
    
    def _get_service_port(self, service_id: str) -> int:
        """Get default port for a service type."""
        ports = {
            "web": 80,
            "api": 8080,
            "database": 5432,
            "ssh": 22,
            "ftp": 21,
            "smtp": 25,
        }
        return ports.get(service_id, 8000 + hash(service_id) % 1000)
    
    async def _run_health_checks(
        self,
        game_id: UUID,
        tick: int,
    ) -> Dict[UUID, Dict[str, bool]]:
        """Run health checks for all services."""
        game = self._active_games.get(game_id)
        if not game:
            return {}
        
        health_results: Dict[UUID, Dict[str, bool]] = {}
        
        for team_id in await self._get_game_teams(game_id):
            health_results[team_id] = {}
            
            for service_id in game.config.service_ids:
                connection_info = await self._get_service_connection(team_id, service_id)
                is_healthy = await self.checker_runner.run_check(
                    service_id, team_id, connection_info
                )
                health_results[team_id][service_id] = is_healthy
        
        return health_results
    
    async def _calculate_tick_scores(
        self,
        game_id: UUID,
        tick: int,
        service_health: Dict[UUID, Dict[str, bool]],
    ) -> None:
        """Calculate and store scores for a tick."""
        game = self._active_games.get(game_id)
        if not game:
            return
        
        for team_id in await self._get_game_teams(game_id):
            # Calculate SLA points
            services_healthy = all(service_health.get(team_id, {}).values())
            team_kept_flag = await self._check_team_defense(game_id, team_id, tick)
            
            sla_points = self.score_calculator.calculate_sla_points(
                services_healthy, team_kept_flag
            )
            
            # Calculate offense points from submissions
            offense_points = await self._get_offense_points(game_id, team_id, tick)
            
            # Calculate defense points
            defense_points = self.score_calculator.config.defense_points_per_flag if team_kept_flag else 0
            
            # Calculate total
            total = self.score_calculator.calculate_total_score(
                sla_points, offense_points, defense_points
            )
            
            # Store score
            score = ADScore(
                team_id=team_id,
                game_id=game_id,
                tick=tick,
                sla_points=sla_points,
                offense_points=offense_points,
                defense_points=defense_points,
                total_score=total,
            )
            await self._store_score(score)
    
    async def _check_team_defense(
        self,
        game_id: UUID,
        team_id: UUID,
        tick: int,
    ) -> bool:
        """Check if a team successfully defended their flag."""
        game = self._active_games.get(game_id)
        if not game:
            return False
        
        for service_id in game.config.service_ids:
            checker = self.checker_runner._checkers.get(service_id)
            if not checker:
                continue
            
            # Get the flag for this team/service/tick
            flag = self.flag_generator.generate_flag(
                game_id, service_id, team_id, tick
            )
            
            connection_info = await self._get_service_connection(team_id, service_id)
            
            try:
                is_present = await asyncio.to_thread(
                    checker.get_flag,
                    team_id,
                    flag,
                    tick,
                    connection_info,
                )
                if is_present:
                    return True
            except Exception:
                continue
        
        return False
    
    async def _get_offense_points(
        self,
        game_id: UUID,
        team_id: UUID,
        tick: int,
    ) -> int:
        """Get offense points earned by a team in a tick."""
        # Get valid submissions for this team and tick
        cache_key = f"ad:submissions:{game_id}:{team_id}:{tick}"
        submissions = await self.cache.get(cache_key)
        
        if not submissions:
            return 0
        
        return sum(
            s.get("points_awarded", 0)
            for s in submissions
            if s.get("is_valid", False)
        )
    
    async def submit_flag(
        self,
        game_id: UUID,
        attacker_team_id: UUID,
        flag: str,
    ) -> ADSubmission:
        """
        Submit a captured flag.
        
        Args:
            game_id: The game UUID
            attacker_team_id: The attacking team UUID
            flag: The captured flag
            
        Returns:
            ADSubmission with result
        """
        # Rate limiting
        rate_key = f"{game_id}:{attacker_team_id}"
        now = datetime.utcnow()
        
        if rate_key not in self._submission_timestamps:
            self._submission_timestamps[rate_key] = []
        
        # Clean old timestamps
        self._submission_timestamps[rate_key] = [
            t for t in self._submission_timestamps[rate_key]
            if (now - t).total_seconds() < 300  # Within last 5 minutes
        ]
        
        if len(self._submission_timestamps[rate_key]) >= self._submission_rate_limit:
            logger.warning(
                "Rate limit exceeded",
                game_id=str(game_id),
                team_id=str(attacker_team_id),
            )
            
            return ADSubmission(
                id=uuid4(),
                game_id=game_id,
                attacker_team_id=attacker_team_id,
                victim_team_id=uuid4(),  # Unknown
                flag_hash=flag,
                tick=0,
                is_valid=False,
                points_awarded=0,
                submitted_at=now,
            )
        
        self._submission_timestamps[rate_key].append(now)
        
        game = self._active_games.get(game_id)
        if not game or game.status != ADGameStatus.RUNNING:
            return ADSubmission(
                id=uuid4(),
                game_id=game_id,
                attacker_team_id=attacker_team_id,
                victim_team_id=uuid4(),
                flag_hash=flag,
                tick=0,
                is_valid=False,
                points_awarded=0,
                submitted_at=now,
            )
        
        tick = game.current_tick
        
        # Parse and verify flag
        for service_id in game.config.service_ids:
            for victim_team_id in await self._get_game_teams(game_id):
                if victim_team_id == attacker_team_id:
                    continue
                
                if self.flag_generator.verify_flag(
                    flag, game_id, service_id, victim_team_id, tick
                ):
                    # Valid flag!
                    points = game.config.offense_points_per_flag
                    
                    submission = ADSubmission(
                        id=uuid4(),
                        game_id=game_id,
                        attacker_team_id=attacker_team_id,
                        victim_team_id=victim_team_id,
                        service_id=service_id,
                        flag_hash=flag,
                        tick=tick,
                        is_valid=True,
                        points_awarded=points,
                        submitted_at=now,
                    )
                    
                    await self._store_submission(submission)
                    
                    # Update flag status
                    await self._mark_flag_captured(game_id, service_id, victim_team_id, tick)
                    
                    # Emit event
                    await self._emit_event("ad.flag_captured", {
                        "game_id": str(game_id),
                        "attacker_team_id": str(attacker_team_id),
                        "victim_team_id": str(victim_team_id),
                        "service_id": service_id,
                        "tick": tick,
                    })
                    
                    return submission
        
        # Invalid flag
        return ADSubmission(
            id=uuid4(),
            game_id=game_id,
            attacker_team_id=attacker_team_id,
            victim_team_id=uuid4(),
            flag_hash=flag,
            tick=tick,
            is_valid=False,
            points_awarded=0,
            submitted_at=now,
        )
    
    async def get_scoreboard(self, game_id: UUID) -> List[Dict]:
        """
        Get the current scoreboard for a game.
        
        Args:
            game_id: The game UUID
            
        Returns:
            List of team scores sorted by total points
        """
        game = self._active_games.get(game_id)
        if not game:
            return []
        
        scores: Dict[UUID, Dict] = {}
        
        for team_id in await self._get_game_teams(game_id):
            scores[team_id] = {
                "team_id": str(team_id),
                "team_name": await self._get_team_name(team_id),
                "sla_points": 0,
                "offense_points": 0,
                "defense_points": 0,
                "total_score": 0,
            }
        
        # Aggregate scores from all ticks
        for tick in range(1, game.current_tick + 1):
            for team_id in scores.keys():
                score = await self._get_score(game_id, team_id, tick)
                if score:
                    scores[team_id]["sla_points"] += score.sla_points
                    scores[team_id]["offense_points"] += score.offense_points
                    scores[team_id]["defense_points"] += score.defense_points
                    scores[team_id]["total_score"] += score.total_score
        
        # Sort by total score
        sorted_scores = sorted(scores.values(), key=lambda x: x["total_score"], reverse=True)
        
        return sorted_scores
    
    # Storage methods (implement with actual database/cache)
    
    async def _store_flag(self, flag: ADFlag) -> None:
        """Store a flag in cache/database."""
        cache_key = f"ad:flag:{flag.game_id}:{flag.tick}:{flag.service_id}:{flag.team_id}"
        await self.cache.set(cache_key, flag.to_dict(), ttl=86400 * 7)  # 7 days
    
    async def _store_score(self, score: ADScore) -> None:
        """Store a score in cache/database."""
        cache_key = f"ad:score:{score.game_id}:{score.team_id}:{score.tick}"
        await self.cache.set(cache_key, score.to_dict(), ttl=86400 * 7)
    
    async def _store_submission(self, submission: ADSubmission) -> None:
        """Store a submission in cache/database."""
        cache_key = f"ad:submission:{submission.id}"
        await self.cache.set(cache_key, submission.to_dict(), ttl=86400 * 7)
        
        # Also add to team's tick submissions for scoring
        tick_key = f"ad:submissions:{submission.game_id}:{submission.attacker_team_id}:{submission.tick}"
        submissions = await self.cache.get(tick_key) or []
        submissions.append(submission.to_dict())
        await self.cache.set(tick_key, submissions, ttl=86400 * 7)
    
    async def _get_score(
        self,
        game_id: UUID,
        team_id: UUID,
        tick: int,
    ) -> Optional[ADScore]:
        """Get a specific score."""
        cache_key = f"ad:score:{game_id}:{team_id}:{tick}"
        data = await self.cache.get(cache_key)
        if data:
            return ADScore(**data)
        return None
    
    async def _mark_flag_captured(
        self,
        game_id: UUID,
        service_id: str,
        team_id: UUID,
        tick: int,
    ) -> None:
        """Mark a flag as captured."""
        cache_key = f"ad:flag:{game_id}:{tick}:{service_id}:{team_id}"
        flag_data = await self.cache.get(cache_key)
        if flag_data:
            flag_data["status"] = ADFlagStatus.CAPTURED.value
            await self.cache.set(cache_key, flag_data, ttl=86400 * 7)
    
    async def _expire_old_flags(self, game_id: UUID, current_tick: int) -> None:
        """Expire flags that are past their lifetime."""
        game = self._active_games.get(game_id)
        if not game:
            return
        
        expire_before = current_tick - game.config.flag_lifetime_ticks
        
        for tick in range(1, expire_before):
            for service_id in game.config.service_ids:
                for team_id in await self._get_game_teams(game_id):
                    cache_key = f"ad:flag:{game_id}:{tick}:{service_id}:{team_id}"
                    flag_data = await self.cache.get(cache_key)
                    if flag_data and flag_data.get("status") == ADFlagStatus.ACTIVE.value:
                        flag_data["status"] = ADFlagStatus.EXPIRED.value
                        await self.cache.set(cache_key, flag_data, ttl=86400 * 7)
    
    async def _get_game_teams(self, game_id: UUID) -> List[UUID]:
        """Get list of teams in a game."""
        cache_key = f"ad:game:{game_id}:teams"
        teams = await self.cache.get(cache_key)
        return [UUID(t) for t in teams] if teams else []
    
    async def _get_team_name(self, team_id: UUID) -> str:
        """Get team name by ID."""
        cache_key = f"team:{team_id}:name"
        name = await self.cache.get(cache_key)
        return name or f"Team {str(team_id)[:8]}"
    
    async def _emit_event(self, event_type: str, data: Dict) -> None:
        """Emit a WebSocket event."""
        # This would integrate with the WebSocket manager
        cache_key = f"ws:events:{event_type}"
        await self.cache.publish(cache_key, data)
