"""
Privacy domain services for anonymization and visibility filtering.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import hashlib
from dataclasses import dataclass
from enum import Enum


class PrivacyMode(str, Enum):
    """Privacy mode enumeration."""
    FULL = "full"
    ANONYMOUS = "anonymous"
    STEALTH = "stealth"
    DELAYED = "delayed"


@dataclass
class AnonymizedTeam:
    """Represents an anonymized team identity."""
    anonymous_id: str
    display_name: str
    avatar_hash: str


class AnonymizationService:
    """
    Service for anonymizing team identities based on privacy mode.
    Provides consistent hash-based IDs for anonymous mode.
    """
    
    def __init__(self, salt: str = "cerb-privacy-salt"):
        self.salt = salt
    
    def get_anonymous_id(self, team_id: UUID) -> str:
        """
        Generate a consistent anonymous ID for a team.
        Same team_id always produces same anonymous_id.
        
        Args:
            team_id: The actual team UUID
            
        Returns:
            Anonymous ID like "Team #1234"
        """
        hash_input = f"{self.salt}:{team_id}".encode('utf-8')
        hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
        team_number = (hash_value % 9999) + 1
        return f"Team #{team_number}"
    
    def get_display_name(self, team_id: UUID, privacy_mode: PrivacyMode) -> str:
        """
        Get the display name for a team based on privacy mode.
        
        Args:
            team_id: The actual team UUID
            privacy_mode: Current privacy mode
            
        Returns:
            Team name or anonymized ID
        """
        if privacy_mode == PrivacyMode.ANONYMOUS:
            return self.get_anonymous_id(team_id)
        # For full/stealth/delayed modes, return None to indicate real name should be used
        # (real name is handled elsewhere based on context)
        return self.get_anonymous_id(team_id) if privacy_mode == PrivacyMode.ANONYMOUS else ""
    
    def get_anonymous_avatar(self, team_id: UUID) -> str:
        """
        Generate a deterministic identicon/avatar hash for a team.
        
        Args:
            team_id: The actual team UUID
            
        Returns:
            Hash string for avatar generation
        """
        hash_input = f"{self.salt}:avatar:{team_id}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()[:16]
    
    def anonymize_team(self, team_id: UUID, privacy_mode: PrivacyMode) -> AnonymizedTeam:
        """
        Get a fully anonymized team representation.
        
        Args:
            team_id: The actual team UUID
            privacy_mode: Current privacy mode
            
        Returns:
            AnonymizedTeam with masked identity
        """
        return AnonymizedTeam(
            anonymous_id=self.get_anonymous_id(team_id),
            display_name=self.get_anonymous_id(team_id) if privacy_mode == PrivacyMode.ANONYMOUS else "",
            avatar_hash=self.get_anonymous_avatar(team_id)
        )


class VisibilityFilter:
    """
    Filter that redacts solve data based on privacy mode and user role.
    """
    
    def __init__(self, anonymization_service: AnonymizationService):
        self.anonymization = anonymization_service
    
    def filter_solve(
        self, 
        solve_data: Dict[str, Any], 
        user_role: str,
        privacy_mode: PrivacyMode,
        is_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Filter solve data based on privacy mode and user role.
        
        Args:
            solve_data: Original solve data dictionary
            user_role: Role of the requesting user
            privacy_mode: Current platform privacy mode
            is_admin: Whether user has admin privileges
            
        Returns:
            Redacted solve data appropriate for the user's visibility level
        """
        if is_admin:
            return solve_data  # Admins see everything
        
        filtered = solve_data.copy()
        
        if privacy_mode == PrivacyMode.FULL:
            return filtered
        
        if privacy_mode == PrivacyMode.ANONYMOUS:
            # Mask team information
            team_id = solve_data.get('team_id')
            if team_id:
                anonymized = self.anonymization.anonymize_team(team_id, privacy_mode)
                filtered['team_id'] = anonymized.anonymous_id
                filtered['team_name'] = anonymized.display_name
                filtered['team_avatar'] = anonymized.avatar_hash
            
            # Keep solve timestamp and challenge info but mask user details
            filtered.pop('user_id', None)
            filtered.pop('user_name', None)
            return filtered
        
        if privacy_mode == PrivacyMode.STEALTH:
            # Hide solves completely, only show aggregate counts
            return {
                'challenge_id': solve_data.get('challenge_id'),
                'solved': True,  # Just indicate it's solved
                '_stealth_mode': True,  # Marker for UI
            }
        
        if privacy_mode == PrivacyMode.DELAYED:
            # Check if reveal time has passed
            reveal_time = solve_data.get('_reveal_time')
            current_time = solve_data.get('_current_time')
            
            if reveal_time and current_time and current_time >= reveal_time:
                return filtered  # Show the solve
            
            # Hide detailed solve info if not yet revealed
            return {
                'challenge_id': solve_data.get('challenge_id'),
                'solved': True,
                '_delayed_mode': True,
                '_reveal_at': reveal_time,
            }
        
        return filtered
    
    def filter_leaderboard(
        self, 
        leaderboard_data: List[Dict[str, Any]], 
        user_role: str,
        privacy_mode: PrivacyMode,
        is_admin: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter entire leaderboard based on privacy mode.
        
        Args:
            leaderboard_data: List of team leaderboard entries
            user_role: Role of the requesting user
            privacy_mode: Current platform privacy mode
            is_admin: Whether user has admin privileges
            
        Returns:
            Filtered leaderboard entries
        """
        if is_admin:
            return leaderboard_data
        
        if privacy_mode == PrivacyMode.FULL:
            return leaderboard_data
        
        if privacy_mode in [PrivacyMode.ANONYMOUS, PrivacyMode.STEALTH, PrivacyMode.DELAYED]:
            filtered_entries = []
            
            for entry in leaderboard_data:
                entry_copy = entry.copy()
                
                if privacy_mode == PrivacyMode.ANONYMOUS:
                    # Anonymize team identities
                    team_id = entry.get('team_id')
                    if team_id:
                        anonymized = self.anonymization.anonymize_team(team_id, privacy_mode)
                        entry_copy['team_id'] = anonymized.anonymous_id
                        entry_copy['team_name'] = anonymized.display_name
                        entry_copy['team_avatar'] = anonymized.avatar_hash
                    entry_copy.pop('members', None)  # Hide member info
                
                elif privacy_mode == PrivacyMode.STEALTH:
                    # Hide individual solves, show only score
                    entry_copy = {
                        'rank': entry.get('rank'),
                        'score': entry.get('score'),
                        'solves_count': entry.get('solves_count', 0),
                        '_stealth_mode': True,
                    }
                
                elif privacy_mode == PrivacyMode.DELAYED:
                    # Hide solves until reveal time
                    if entry.get('_delayed_reveal'):
                        entry_copy['_delayed_reveal'] = True
                        entry_copy['solves'] = []  # Hide individual solves
                
                filtered_entries.append(entry_copy)
            
            return filtered_entries
        
        return leaderboard_data
    
    def get_visibility_info(self, privacy_mode: PrivacyMode) -> Dict[str, Any]:
        """
        Get information about what data is visible under current mode.
        
        Args:
            privacy_mode: Current platform privacy mode
            
        Returns:
            Dictionary describing visibility settings
        """
        visibility_map = {
            PrivacyMode.FULL: {
                "mode": "full",
                "description": "All data visible",
                "team_names_visible": True,
                "solves_visible": True,
                "timestamps_visible": True,
                "member_list_visible": True,
            },
            PrivacyMode.ANONYMOUS: {
                "mode": "anonymous",
                "description": "Team names masked as 'Team #1234'",
                "team_names_visible": False,
                "solves_visible": True,
                "timestamps_visible": True,
                "member_list_visible": False,
            },
            PrivacyMode.STEALTH: {
                "mode": "stealth",
                "description": "Solves hidden, only counts shown",
                "team_names_visible": False,
                "solves_visible": False,
                "timestamps_visible": False,
                "member_list_visible": False,
            },
            PrivacyMode.DELAYED: {
                "mode": "delayed",
                "description": "Scoreboard updates delayed",
                "team_names_visible": True,
                "solves_visible": False,
                "timestamps_visible": False,
                "member_list_visible": True,
            },
        }
        
        return visibility_map.get(privacy_mode, visibility_map[PrivacyMode.FULL])
