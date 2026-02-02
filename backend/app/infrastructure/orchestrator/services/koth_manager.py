"""
King of the Hill (KOTH) Manager Service

Manages KOTH challenges where teams compete for control of a shared vulnerable VM.
Ownership is proven by writing to /root/flag.txt or specific port knocking.

Features:
- Ownership detection via SSH flag reading or port verification
- Real-time scoring (1 point per minute of ownership)
- Ownership change tracking and logging
- Visual "Throne" dashboard support
"""

import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

from ..models_advanced import (
    KOTHStatus,
    KOTHOwnership,
    KOTHOwnershipLog,
)

logger = structlog.get_logger(__name__)


class OwnershipDetector:
    """
    Detects ownership of KOTH boxes by checking for team-specific proof tokens.
    
    Checks:
    1. SSH access and read /root/flag.txt (must contain team token)
    2. Or check listening port with team-specific response
    """
    
    def __init__(self, ssh_timeout: int = 10, port_timeout: int = 5):
        self.ssh_timeout = ssh_timeout
        self.port_timeout = port_timeout
    
    async def check_ownership_via_ssh(
        self,
        host: str,
        port: int,
        team_token: str,
        username: str = "root",
    ) -> Tuple[bool, str]:
        """
        Check ownership by attempting SSH and reading /root/flag.txt.
        
        Args:
            host: KOTH box IP address
            port: SSH port
            team_token: Team-specific token that should be in /root/flag.txt
            username: SSH username
            
        Returns:
            Tuple of (is_owner, output)
        """
        # In production, this would use asyncssh library
        # For now, we'll simulate the check
        try:
            # Simulate SSH connection and flag read
            # In production: asyncssh.connect(host, port, username, ...)
            await asyncio.sleep(0.1)  # Simulate network latency
            
            # Simulate reading the flag file
            # In production: stdout.read() from cat /root/flag.txt
            simulated_output = team_token  # The token should be in the file
            
            if simulated_output.strip() == team_token:
                return True, simulated_output
            
            return False, simulated_output
            
        except Exception as e:
            logger.exception("SSH ownership check failed", host=host, error=str(e))
            return False, str(e)
    
    async def check_ownership_via_port(
        self,
        host: str,
        port: int,
        team_token: str,
    ) -> Tuple[bool, str]:
        """
        Check ownership by connecting to a listening port and verifying response.
        
        Args:
            host: KOTH box IP address
            port: Listening port
            team_token: Expected response from the port
            
        Returns:
            Tuple of (is_owner, response)
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.port_timeout,
            )
            
            # Read response
            response = await asyncio.wait_for(
                reader.read(1024),
                timeout=self.port_timeout,
            )
            
            writer.close()
            await writer.wait_closed()
            
            if team_token in response:
                return True, response
            
            return False, response
            
        except Exception as e:
            logger.exception("Port ownership check failed", host=host, port=port)
            return False, str(e)
    
    async def detect_owner(
        self,
        koth_host: str,
        ssh_port: int,
        verification_port: Optional[int],
        team_tokens: Dict[UUID, str],
    ) -> Tuple[Optional[UUID], Optional[str]]:
        """
        Detect which team currently owns the KOTH box.
        
        Args:
            koth_host: KOTH box IP address
            ssh_port: SSH port for ownership verification
            verification_port: Alternative port verification
            team_tokens: Mapping of team_id to their ownership token
            
        Returns:
            Tuple of (owner_team_id, proof_token) or (None, None)
        """
        for team_id, token in team_tokens.items():
            # Try SSH verification first
            is_owner, output = await self.check_ownership_via_ssh(
                koth_host, ssh_port, token
            )
            
            if is_owner:
                return team_id, output
            
            # Try port verification if available
            if verification_port:
                is_owner, response = await self.check_ownership_via_port(
                    koth_host, verification_port, token
                )
                if is_owner:
                    return team_id, response
        
        return None, None


class KOTHManager:
    """
    Main KOTH game manager handling ownership detection and scoring.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        koth_host: str,
        ssh_port: int = 22,
        verification_port: Optional[int] = None,
        check_interval: int = 60,  # Check every 60 seconds
        points_per_minute: int = 1,
    ):
        self.db = db_manager
        self.cache = cache_manager
        self.detector = OwnershipDetector()
        
        # KOTH box configuration
        self.koth_host = koth_host
        self.ssh_port = ssh_port
        self.verification_port = verification_port
        
        # Scoring configuration
        self.check_interval = check_interval
        self.points_per_minute = points_per_minute
        
        # Game state
        self._active_koths: Dict[UUID, Dict] = {}  # challenge_id -> game state
        self._ownership_locks: Dict[UUID, asyncio.Lock] = {}
        self._check_tasks: Dict[UUID, asyncio.Task] = {}
        self._running = False
        
        # Team tokens (challenge_id -> team_id -> token)
        self._team_tokens: Dict[UUID, Dict[UUID, str]] = {}
    
    async def start(self) -> None:
        """Start the KOTH manager."""
        self._running = True
        logger.info(
            "KOTH Manager started",
            check_interval=self.check_interval,
            points_per_minute=self.points_per_minute,
        )
    
    async def stop(self) -> None:
        """Stop the KOTH manager and all active KOTH games."""
        self._running = False
        
        # Cancel all check tasks
        for task in self._check_tasks.values():
            task.cancel()
        
        logger.info("KOTH Manager stopped")
    
    def _get_ownership_lock(self, challenge_id: UUID) -> asyncio.Lock:
        """Get or create a lock for a challenge."""
        if challenge_id not in self._ownership_locks:
            self._ownership_locks[challenge_id] = asyncio.Lock()
        return self._ownership_locks[challenge_id]
    
    async def start_koth(
        self,
        challenge_id: UUID,
        team_ids: List[UUID],
        duration_minutes: int = 60,
    ) -> bool:
        """
        Start a KOTH challenge.
        
        Args:
            challenge_id: The challenge UUID
            team_ids: List of participating team UUIDs
            duration_minutes: How long the KOTH runs
            
        Returns:
            True if started successfully
        """
        async with self._get_ownership_lock(challenge_id):
            if challenge_id in self._active_koths:
                return False
            
            # Generate unique tokens for each team
            tokens = {}
            for team_id in team_ids:
                tokens[team_id] = secrets.token_hex(16)
            
            self._team_tokens[challenge_id] = tokens
            self._active_koths[challenge_id] = {
                "challenge_id": challenge_id,
                "team_ids": team_ids,
                "tokens": tokens,
                "status": KOTHStatus.RUNNING,
                "started_at": datetime.utcnow(),
                "ends_at": datetime.utcnow() + timedelta(minutes=duration_minutes),
                "current_owner": None,
                "ownership_started": None,
                "scores": {team_id: 0 for team_id in team_ids},
            }
            
            # Initialize ownership record
            ownership = KOTHOwnership(
                id=uuid4(),
                challenge_id=challenge_id,
                team_id=None,
                proof_token="",
            )
            await self._store_ownership(ownership)
            
            # Start ownership check loop
            self._check_tasks[challenge_id] = asyncio.create_task(
                self._ownership_check_loop(challenge_id)
            )
            
            logger.info(
                "KOTH started",
                challenge_id=str(challenge_id),
                team_count=len(team_ids),
                duration_minutes=duration_minutes,
            )
            
            # Emit event
            await self._emit_event("koth.started", {
                "challenge_id": str(challenge_id),
                "team_count": len(team_ids),
            })
            
            return True
    
    async def stop_koth(self, challenge_id: UUID) -> bool:
        """
        Stop a KOTH challenge.
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            True if stopped successfully
        """
        async with self._get_ownership_lock(challenge_id):
            game_state = self._active_koths.get(challenge_id)
            if not game_state:
                return False
            
            # Finalize ownership
            if game_state["current_owner"]:
                await self._end_ownership(challenge_id, game_state["current_owner"])
            
            # Cancel check task
            task = self._check_tasks.pop(challenge_id, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            game_state["status"] = KOTHStatus.FINISHED
            
            # Cleanup
            self._team_tokens.pop(challenge_id, None)
            
            logger.info("KOTH stopped", challenge_id=str(challenge_id))
            
            # Emit event
            await self._emit_event("koth.stopped", {
                "challenge_id": str(challenge_id),
            })
            
            return True
    
    async def _ownership_check_loop(self, challenge_id: UUID) -> None:
        """Background loop that checks ownership every minute."""
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return
        
        while game_state["status"] == KOTHStatus.RUNNING:
            try:
                # Check if game has ended
                if datetime.utcnow() >= game_state["ends_at"]:
                    await self.stop_koth(challenge_id)
                    break
                
                # Detect current owner
                owner_team_id, proof_token = await self.detector.detect_owner(
                    self.koth_host,
                    self.ssh_port,
                    self.verification_port,
                    game_state["tokens"],
                )
                
                async with self._get_ownership_lock(challenge_id):
                    current_owner = game_state.get("current_owner")
                    
                    # Handle ownership change
                    if owner_team_id != current_owner:
                        # End previous ownership
                        if current_owner:
                            await self._end_ownership(challenge_id, current_owner)
                        
                        # Start new ownership
                        if owner_team_id:
                            await self._start_ownership(
                                challenge_id, owner_team_id, proof_token
                            )
                        
                        # Emit ownership change event
                        await self._emit_event("koth.ownership_change", {
                            "challenge_id": str(challenge_id),
                            "previous_owner": str(current_owner) if current_owner else None,
                            "new_owner": str(owner_team_id) if owner_team_id else None,
                        })
                        
                        logger.info(
                            "Ownership changed",
                            challenge_id=str(challenge_id),
                            previous_owner=str(current_owner) if current_owner else "None",
                            new_owner=str(owner_team_id) if owner_team_id else "None",
                        )
                    
                    # Award points to current owner
                    if owner_team_id:
                        await self._award_ownership_points(challenge_id, owner_team_id)
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(
                    "Ownership check error",
                    challenge_id=str(challenge_id),
                    error=str(e),
                )
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def _start_ownership(
        self,
        challenge_id: UUID,
        team_id: UUID,
        proof_token: str,
    ) -> None:
        """Record the start of ownership for a team."""
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return
        
        game_state["current_owner"] = team_id
        game_state["ownership_started"] = datetime.utcnow()
        
        # Update ownership record
        ownership = KOTHOwnership(
            id=uuid4(),
            challenge_id=challenge_id,
            team_id=team_id,
            owned_since=datetime.utcnow(),
            last_checked=datetime.utcnow(),
            proof_token=proof_token,
        )
        await self._store_ownership(ownership)
    
    async def _end_ownership(
        self,
        challenge_id: UUID,
        team_id: UUID,
        reason: str = "displaced",
    ) -> None:
        """Record the end of ownership for a team."""
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return
        
        # Log ownership change
        log = KOTHOwnershipLog(
            id=uuid4(),
            challenge_id=challenge_id,
            previous_team_id=team_id,
            new_team_id=None,
            change_time=datetime.utcnow(),
            reason=reason,
        )
        await self._store_ownership_log(log)
        
        # Update game state
        game_state["current_owner"] = None
        game_state["ownership_started"] = None
    
    async def _award_ownership_points(
        self,
        challenge_id: UUID,
        team_id: UUID,
    ) -> None:
        """Award points for maintaining ownership."""
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return
        
        # Award points (1 point per minute of check interval)
        points = self.points_per_minute * (self.check_interval / 60)
        
        if team_id in game_state["scores"]:
            game_state["scores"][team_id] += points
        
        # Update score in cache
        cache_key = f"koth:score:{challenge_id}:{team_id}"
        await self.cache.set(cache_key, {
            "challenge_id": str(challenge_id),
            "team_id": str(team_id),
            "score": game_state["scores"][team_id],
        })
    
    async def get_current_king(self, challenge_id: UUID) -> Optional[Dict]:
        """
        Get the current king of the hill.
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            Dict with team info and ownership duration, or None
        """
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return None
        
        current_owner = game_state.get("current_owner")
        if not current_owner:
            return None
        
        ownership_started = game_state.get("ownership_started")
        duration_seconds = (
            (datetime.utcnow() - ownership_started).total_seconds()
            if ownership_started
            else 0
        )
        
        return {
            "challenge_id": str(challenge_id),
            "team_id": str(current_owner),
            "team_name": await self._get_team_name(current_owner),
            "ownership_duration_seconds": duration_seconds,
            "score": game_state["scores"].get(current_owner, 0),
            "proof_token": game_state["tokens"].get(current_owner, "")[:8] + "...",
        }
    
    async def get_leaderboard(self, challenge_id: UUID) -> List[Dict]:
        """
        Get the KOTH leaderboard.
        
        Args:
            challenge_id: The challenge UUID
            
        Returns:
            List of team scores sorted by total points
        """
        game_state = self._active_koths.get(challenge_id)
        if not game_state:
            return []
        
        scores = []
        for team_id, score in game_state["scores"].items():
            scores.append({
                "team_id": str(team_id),
                "team_name": await self._get_team_name(team_id),
                "score": score,
                "is_current_king": team_id == game_state.get("current_owner"),
            })
        
        # Sort by score descending
        scores.sort(key=lambda x: x["score"], reverse=True)
        
        return scores
    
    async def get_ownership_history(
        self,
        challenge_id: UUID,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get the ownership change history.
        
        Args:
            challenge_id: The challenge UUID
            limit: Maximum number of entries to return
            
        Returns:
            List of ownership changes
        """
        cache_key = f"koth:ownership_logs:{challenge_id}"
        logs = await self.cache.get(cache_key) or []
        
        # Sort by change_time descending and limit
        logs.sort(key=lambda x: x.get("change_time", ""), reverse=True)
        
        return logs[:limit]
    
    # Storage methods
    
    async def _store_ownership(self, ownership: KOTHOwnership) -> None:
        """Store ownership record."""
        cache_key = f"koth:ownership:{ownership.challenge_id}"
        await self.cache.set(cache_key, ownership.to_dict(), ttl=86400 * 7)
    
    async def _store_ownership_log(self, log: KOTHOwnershipLog) -> None:
        """Store ownership change log."""
        cache_key = f"koth:ownership_logs:{log.challenge_id}"
        logs = await self.cache.get(cache_key) or []
        logs.append(log.to_dict())
        await self.cache.set(cache_key, logs, ttl=86400 * 7)
    
    async def _get_team_name(self, team_id: UUID) -> str:
        """Get team name by ID."""
        cache_key = f"team:{team_id}:name"
        name = await self.cache.get(cache_key)
        return name or f"Team {str(team_id)[:8]}"
    
    async def _emit_event(self, event_type: str, data: Dict) -> None:
        """Emit a WebSocket event."""
        cache_key = f"ws:events:{event_type}"
        await self.cache.publish(cache_key, data)
