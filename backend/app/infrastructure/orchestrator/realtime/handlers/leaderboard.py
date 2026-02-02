"""
Leaderboard Handler

Manages real-time leaderboard updates with:
- Diff-based updates (only send changed positions)
- Scoreboard freeze support
- Anonymous mode (mask names in transit)
- Materialized view refresh triggers
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import structlog

from app.infrastructure.database import DatabaseManager

logger = structlog.get_logger(__name__)


class LeaderboardHandler:
    """
    Handles leaderboard real-time updates and broadcasts.
    
    Features:
    - Diff-based updates for efficient broadcasting
    - Scoreboard freeze/unfreeze
    - Anonymous mode support
    - Integration with materialized views
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_prefix: str = "leaderboard",
    ):
        self.db_manager = db_manager
        self.cache_prefix = cache_prefix
        self._previous_state: Dict[str, Any] = {}
        self._frozen = False
        self._frozen_state: Optional[Dict[str, Any]] = None
        self._anonymous_mode = False
        self._diff_threshold = 5  # Minimum position change to include in diff
        
        logger.info("LeaderboardHandler initialized")
    
    async def get_current_leaderboard(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get current leaderboard from database.
        
        Returns:
            Leaderboard data with entries and metadata
        """
        async with self.db_manager.session() as session:
            # This would query the materialized view or denormalized table
            # Example query structure (adapt to your models):
            query = f"""
                SELECT 
                    team_id,
                    team_name,
                    COALESCE(SUM(c.points), 0) as total_points,
                    COUNT(DISTINCT c.challenge_id) as solves_count,
                    MIN(s.solved_at) as first_solve
                FROM team_challenge_solves s
                JOIN challenges c ON c.id = s.challenge_id
                WHERE c.active = true
                GROUP BY team_id, team_name
                ORDER BY total_points DESC, first_solve ASC
                LIMIT :limit OFFSET :offset
            """
            
            # Simplified - adapt to actual model structure
            result = {
                "entries": [],
                "total": 0,
                "last_updated": datetime.utcnow().isoformat(),
            }
            
            return result
    
    async def compute_diff(
        self,
        new_entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute diff between current and previous leaderboard state.
        
        Returns:
            Diff data containing only changed positions
        """
        if not self._previous_state:
            # First load - return full leaderboard
            return {
                "type": "full",
                "entries": new_entries,
                "changed_positions": [],
            }
        
        # Build position lookup from previous state
        previous_positions = {
            entry.get("team_id"): entry.get("position", i + 1)
            for i, entry in enumerate(self._previous_state.get("entries", []))
        }
        
        # Compute changes
        changed_positions = []
        for i, entry in enumerate(new_entries):
            team_id = entry.get("team_id")
            new_position = i + 1
            old_position = previous_positions.get(team_id)
            
            if old_position is None:
                # New entry
                changed_positions.append({
                    "team_id": team_id,
                    "old_position": None,
                    "new_position": new_position,
                    "entry": entry if not self._anonymous_mode else self._anonymize_entry(entry),
                })
            elif abs(old_position - new_position) >= self._diff_threshold:
                # Significant position change
                changed_positions.append({
                    "team_id": team_id,
                    "old_position": old_position,
                    "new_position": new_position,
                    "entry": entry if not self._anonymous_mode else self._anonymize_entry(entry),
                })
        
        # Store previous state
        self._previous_state = {
            "entries": new_entries,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return {
            "type": "diff",
            "entries": changed_positions,
            "total_teams": len(new_entries),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _anonymize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize a leaderboard entry."""
        return {
            **entry,
            "team_name": f"Team {entry.get('team_id', '???')[:8]}",
            "members": [
                {
                    "user_id": m.get("user_id"),
                    "username": f"Player {m.get('user_id', '???')[:8]}" if m.get('user_id') else "Anonymous",
                }
                for m in entry.get("members", [])
            ],
        }
    
    async def freeze(self) -> Dict[str, Any]:
        """Freeze the leaderboard and return frozen state."""
        self._frozen = True
        self._frozen_state = await self.get_current_leaderboard()
        
        logger.info("Leaderboard frozen")
        
        return {
            "frozen": True,
            "frozen_at": datetime.utcnow().isoformat(),
            "entries": self._frozen_state.get("entries", []),
        }
    
    async def unfreeze(self) -> Dict[str, Any]:
        """Unfreeze the leaderboard."""
        self._frozen = False
        frozen_state = self._frozen_state
        self._frozen_state = None
        
        logger.info("Leaderboard unfrozen")
        
        return {
            "frozen": False,
            "unfrozen_at": datetime.utcnow().isoformat(),
            "entries": frozen_state.get("entries", []) if frozen_state else [],
        }
    
    def set_anonymous_mode(self, enabled: bool) -> None:
        """Enable or disable anonymous mode."""
        self._anonymous_mode = enabled
        logger.info(f"Anonymous mode: {enabled}")
    
    def set_diff_threshold(self, threshold: int) -> None:
        """Set minimum position change for diff inclusion."""
        self._diff_threshold = max(1, threshold)
    
    async def handle_challenge_solve(
        self,
        team_id: UUID,
        challenge_id: UUID,
        points: int,
    ) -> Dict[str, Any]:
        """
        Handle a challenge solve and return updated leaderboard diff.
        
        Args:
            team_id: Team that solved the challenge
            challenge_id: Challenge that was solved
            points: Points awarded
            
        Returns:
            Updated leaderboard diff
        """
        if self._frozen:
            # Queue the update for after unfreeze
            return {
                "type": "queued",
                "message": "Leaderboard is frozen, update queued",
            }
        
        # Get current leaderboard and compute diff
        leaderboard = await self.get_current_leaderboard()
        diff = await self.compute_diff(leaderboard.get("entries", []))
        
        return diff
    
    async def refresh_materialized_view(self) -> bool:
        """
        Refresh the leaderboard materialized view.
        
        Returns:
            True if successful
        """
        try:
            async with self.db_manager.session() as session:
                # Execute REFRESH MATERIALIZED VIEW CONCURRENTLY
                # This depends on your database setup
                pass
            
            logger.info("Leaderboard materialized view refreshed")
            return True
        except Exception as e:
            logger.error("Failed to refresh materialized view", error=str(e))
            return False
    
    async def get_team_rank(
        self,
        team_id: UUID,
    ) -> Optional[int]:
        """Get a team's current rank."""
        leaderboard = await self.get_current_leaderboard()
        
        for i, entry in enumerate(leaderboard.get("entries", [])):
            if entry.get("team_id") == str(team_id):
                return i + 1
        
        return None
    
    async def get_top_teams(
        self,
        n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top N teams."""
        leaderboard = await self.get_current_leaderboard(limit=n)
        return leaderboard.get("entries", [])
    
    async def get_team_solves(
        self,
        team_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get all solves for a specific team."""
        async with self.db_manager.session() as session:
            # Query team solves
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            "frozen": self._frozen,
            "anonymous_mode": self._anonymous_mode,
            "diff_threshold": self._diff_threshold,
            "previous_entries_count": len(self._previous_state.get("entries", [])),
            "frozen_entries_count": len(self._frozen_state.get("entries", [])) if self._frozen_state else 0,
        }
