"""
Unit tests for privacy services.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.domain.privacy.services import (
    PrivacyMode,
    AnonymizationService,
    VisibilityFilter,
)
from app.domain.privacy.gdpr_service import (
    GDPRService,
    RetentionPolicy,
    ExportStatus,
    DeletionStatus,
)


class TestAnonymizationService:
    """Tests for the AnonymizationService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = AnonymizationService(salt="test-salt")
        self.team_id = uuid4()
    
    def test_get_anonymous_id_consistency(self):
        """Same team_id should always produce same anonymous_id."""
        id1 = self.service.get_anonymous_id(self.team_id)
        id2 = self.service.get_anonymous_id(self.team_id)
        assert id1 == id2
    
    def test_get_anonymous_id_format(self):
        """Anonymous ID should be in 'Team #XXXX' format."""
        anonymous_id = self.service.get_anonymous_id(self.team_id)
        assert anonymous_id.startswith("Team #")
        team_num = int(anonymous_id.replace("Team #", ""))
        assert 1 <= team_num <= 9999
    
    def test_different_teams_different_ids(self):
        """Different teams should get different anonymous IDs."""
        team1 = uuid4()
        team2 = uuid4()
        id1 = self.service.get_anonymous_id(team1)
        id2 = self.service.get_anonymous_id(team2)
        assert id1 != id2
    
    def test_get_anonymous_avatar_hash(self):
        """Avatar hash should be deterministic for a team."""
        hash1 = self.service.get_anonymous_avatar(self.team_id)
        hash2 = self.service.get_anonymous_avatar(self.team_id)
        assert hash1 == hash2
        assert len(hash1) == 16
    
    def test_anonymize_team(self):
        """Full anonymization should return all anonymized fields."""
        result = self.service.anonymize_team(self.team_id, PrivacyMode.ANONYMOUS)
        assert result.anonymous_id.startswith("Team #")
        assert result.display_name.startswith("Team #")
        assert len(result.avatar_hash) == 16


class TestVisibilityFilter:
    """Tests for the VisibilityFilter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.anonymization = AnonymizationService()
        self.filter = VisibilityFilter(self.anonymization)
        self.team_id = uuid4()
    
    def test_full_mode_returns_data(self):
        """Full mode should return all data."""
        solve_data = {
            "team_id": self.team_id,
            "team_name": "Team Alpha",
            "user_id": uuid4(),
            "challenge_id": uuid4(),
        }
        
        result = self.filter.filter_solve(solve_data, "user", PrivacyMode.FULL)
        assert result == solve_data
    
    def test_admin_sees_all_data(self):
        """Admin should see all data regardless of mode."""
        solve_data = {
            "team_id": self.team_id,
            "team_name": "Team Alpha",
            "user_id": uuid4(),
        }
        
        result = self.filter.filter_solve(solve_data, "admin", PrivacyMode.STEALTH, is_admin=True)
        assert result == solve_data
    
    def test_anonymous_mode_masks_team(self):
        """Anonymous mode should mask team identity."""
        solve_data = {
            "team_id": self.team_id,
            "team_name": "Team Alpha",
            "user_id": uuid4(),
        }
        
        result = self.filter.filter_solve(solve_data, "user", PrivacyMode.ANONYMOUS)
        assert result["team_id"].startswith("Team #")
        assert result["team_name"].startswith("Team #")
        assert "user_id" not in result
        assert "user_name" not in result
    
    def test_stealth_mode_hides_solves(self):
        """Stealth mode should hide detailed solve data."""
        solve_data = {
            "team_id": self.team_id,
            "team_name": "Team Alpha",
            "challenge_id": uuid4(),
            "solved_at": datetime.now(timezone.utc),
        }
        
        result = self.filter.filter_solve(solve_data, "user", PrivacyMode.STEALTH)
        assert result["_stealth_mode"] is True
        assert result["solved"] is True
        assert "team_name" not in result
        assert "solved_at" not in result
    
    def test_delayed_mode_hides_until_reveal(self):
        """Delayed mode should hide solves until reveal time."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        solve_data = {
            "challenge_id": uuid4(),
            "solved_at": datetime.now(timezone.utc),
            "_reveal_time": future_time,
            "_current_time": datetime.now(timezone.utc),
        }
        
        result = self.filter.filter_solve(solve_data, "user", PrivacyMode.DELAYED)
        assert result["_delayed_mode"] is True
        assert result["_reveal_at"] == future_time
    
    def test_get_visibility_info(self):
        """Visibility info should describe what data is visible."""
        info = self.filter.get_visibility_info(PrivacyMode.FULL)
        assert info["team_names_visible"] is True
        assert info["solves_visible"] is True
        
        info = self.filter.get_visibility_info(PrivacyMode.STEALTH)
        assert info["team_names_visible"] is False
        assert info["solves_visible"] is False


class TestRetentionPolicy:
    """Tests for the RetentionPolicy class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.policy = RetentionPolicy()
    
    def test_default_policies_exist(self):
        """Default policies should exist for standard data types."""
        assert "session_logs" in self.policy.policies
        assert "solves" in self.policy.policies
        assert "audit_logs" in self.policy.policies
    
    def test_get_policy(self):
        """Getting a policy should return the correct configuration."""
        session_policy = self.policy.get_policy("session_logs")
        assert "retention_days" in session_policy
        assert "anonymize_after" in session_policy
        assert "delete_after" in session_policy
    
    def test_get_unknown_policy(self):
        """Unknown data type should return default empty policy."""
        policy = self.policy.get_policy("unknown")
        assert policy["retention_days"] is None
    
    def test_set_policy(self):
        """Setting a policy should update the configuration."""
        self.policy.set_policy(
            "custom_data",
            retention_days=90,
            anonymize_after=30,
            delete_after=180,
        )
        
        policy = self.policy.get_policy("custom_data")
        assert policy["retention_days"] == 90
        assert policy["anonymize_after"] == 30
        assert policy["delete_after"] == 180


class TestGDPRService:
    """Tests for the GDPRService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock session
        self.mock_session = None
        self.service = GDPRService(
            session=self.mock_session,
            storage_path="/tmp/test-exports",
        )
        self.user_id = uuid4()
    
    def test_data_export_request_creation(self):
        """Creating a data export request should generate proper structure."""
        request = self.service.request_data_export(self.user_id)
        
        assert request.user_id == self.user_id
        assert request.status == ExportStatus.PENDING
        assert request.expires_at is not None
        assert request.expires_at > datetime.now(timezone.utc)
    
    def test_deletion_request_grace_period(self):
        """Deletion request should have 30-day grace period."""
        request = self.service.request_account_deletion(
            self.user_id,
            verification_email="test@example.com",
        )
        
        assert request.status == DeletionStatus.PENDING
        assert request.grace_end is not None
        grace_days = (request.grace_end - datetime.now(timezone.utc)).days
        assert 29 <= grace_days <= 30  # Allow for test execution time
    
    def test_deletion_request_verification_hash(self):
        """Deletion request should have a verification hash."""
        request = self.service.request_account_deletion(
            self.user_id,
            verification_email="test@example.com",
        )
        
        assert request.verification_hash is not None
        assert len(request.verification_hash) == 64  # SHA256 hex
    
    def test_get_retention_summary(self):
        """Retention summary should include all data."""
        summary = self.service.get_retention_summary()
        
        assert "policies" in summary
        assert "expiring_soon" in summary
        assert "data_subjects_pending_deletion" in summary
        assert "exports_pending" in summary
    
    def test_run_retention_check(self):
        """Retention check should return results dictionary."""
        results = self.service.run_retention_check()
        
        assert "anonymized_solves" in results
        assert "deleted_sessions" in results
        assert "archived_audit_logs" in results
        assert "failed" in results
