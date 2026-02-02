"""
Orchestrator Models - Data classes for challenge instances and sandbox configurations
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class InstanceStatus(str, Enum):
    """Challenge instance lifecycle statuses."""
    PENDING = "pending"
    CREATING = "creating"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    ERROR = "error"


class SandboxType(str, Enum):
    """Types of sandbox environments."""
    STATIC = "static"
    DOCKER = "docker"
    FIRECRACKER = "firecracker"
    TERRAFORM_AWS = "terraform_aws"
    TERRAFORM_GCP = "terraform_gcp"
    HARDWARE = "hardware"


@dataclass
class NetworkConfig:
    """Network configuration for sandbox instances."""
    internal_ip: Optional[str] = None
    external_ip: Optional[str] = None
    port_mappings: Dict[int, int] = field(default_factory=dict)  # host_port -> container_port
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "internal_ip": self.internal_ip,
            "external_ip": self.external_ip,
            "port_mappings": self.port_mappings,
            "hostname": self.hostname,
            "mac_address": self.mac_address,
        }


@dataclass
class ResourceLimits:
    """Resource limits for sandbox instances."""
    cpu_quota: Optional[float] = None  # CPU cores
    memory_limit_mb: Optional[int] = None
    memory_swap_mb: Optional[int] = 0  # 0 = no swap
    pids_limit: Optional[int] = 100
    storage_limit_mb: Optional[int] = None
    network_bandwidth_mbps: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_quota": self.cpu_quota,
            "memory_limit_mb": self.memory_limit_mb,
            "memory_swap_mb": self.memory_swap_mb,
            "pids_limit": self.pids_limit,
            "storage_limit_mb": self.storage_limit_mb,
            "network_bandwidth_mbps": self.network_bandwidth_mbps,
        }


@dataclass
class SecurityProfile:
    """Security profile for sandbox instances."""
    seccomp_profile: Optional[str] = None
    apparmor_profile: Optional[str] = None
    selinux_context: Optional[str] = None
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    drop_capabilities: List[str] = field(default_factory=lambda: ["ALL"])
    add_capabilities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "seccomp_profile": self.seccomp_profile,
            "apparmor_profile": self.apparmor_profile,
            "selinux_context": self.selinux_context,
            "read_only_rootfs": self.read_only_rootfs,
            "no_new_privileges": self.no_new_privileges,
            "drop_capabilities": self.drop_capabilities,
            "add_capabilities": self.add_capabilities,
        }


@dataclass
class ChallengeInstance:
    """
    Represents a running challenge instance.
    
    Tracks the lifecycle and metadata of a spawned challenge sandbox.
    """
    id: UUID = field(default_factory=uuid4)
    challenge_id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    team_id: Optional[UUID] = None
    
    # Instance metadata
    sandbox_type: SandboxType = SandboxType.DOCKER
    status: InstanceStatus = InstanceStatus.PENDING
    
    # Configuration
    network: NetworkConfig = field(default_factory=NetworkConfig)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    security: SecurityProfile = field(default_factory=SecurityProfile)
    
    # Connection info
    connection_string: Optional[str] = None
    access_url: Optional[str] = None
    
    # Canary token for anti-cheat
    canary_token: Optional[str] = None
    
    # Lifecycle timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    destroyed_at: Optional[datetime] = None
    
    # Provider-specific metadata
    provider_instance_id: Optional[str] = None  # Docker container ID, VM ID, etc.
    provider_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Metrics
    health_check_failures: int = 0
    restart_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "id": str(self.id),
            "challenge_id": str(self.challenge_id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "sandbox_type": self.sandbox_type.value,
            "status": self.status.value,
            "network": self.network.to_dict(),
            "resources": self.resources.to_dict(),
            "security": self.security.to_dict(),
            "connection_string": self.connection_string,
            "access_url": self.access_url,
            "canary_token": self.canary_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "destroyed_at": self.destroyed_at.isoformat() if self.destroyed_at else None,
            "provider_instance_id": self.provider_instance_id,
            "provider_metadata": self.provider_metadata,
            "health_check_failures": self.health_check_failures,
            "restart_count": self.restart_count,
        }
    
    def is_active(self) -> bool:
        """Check if instance is currently active."""
        return self.status in [
            InstanceStatus.CREATING,
            InstanceStatus.RUNNING,
            InstanceStatus.HEALTHY,
            InstanceStatus.UNHEALTHY,
        ]
    
    def is_expired(self) -> bool:
        """Check if instance has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def update_status(self, status: InstanceStatus) -> None:
        """Update instance status with timestamp tracking."""
        self.status = status
        if status == InstanceStatus.RUNNING:
            self.started_at = datetime.utcnow()
        elif status == InstanceStatus.DESTROYED:
            self.destroyed_at = datetime.utcnow()


@dataclass
class SpawnRequest:
    """Request to spawn a new challenge instance."""
    challenge_id: UUID
    user_id: UUID
    team_id: Optional[UUID] = None
    sandbox_type: SandboxType = SandboxType.DOCKER
    timeout_seconds: int = 7200  # 2 hours default
    
    # Optional overrides
    resource_overrides: Optional[ResourceLimits] = None
    network_overrides: Optional[NetworkConfig] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": str(self.challenge_id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "sandbox_type": self.sandbox_type.value,
            "timeout_seconds": self.timeout_seconds,
            "resource_overrides": self.resource_overrides.to_dict() if self.resource_overrides else None,
            "network_overrides": self.network_overrides.to_dict() if self.network_overrides else None,
        }


@dataclass
class SpawnResult:
    """Result of a spawn operation."""
    success: bool
    instance: Optional[ChallengeInstance] = None
    error_message: Optional[str] = None
    retryable: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "instance": self.instance.to_dict() if self.instance else None,
            "error_message": self.error_message,
            "retryable": self.retryable,
        }


@dataclass
class HealthStatus:
    """Health check result for an instance."""
    healthy: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "checks": self.checks,
            "metrics": self.metrics,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }