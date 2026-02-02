"""
Cerberus CTF Platform - Challenge Domain Entities
Challenge types: Static, Containerized, VM, Cloud
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class ChallengeDifficulty(str, Enum):
    """Challenge difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    INSANE = "insane"


class ChallengeCategory(str, Enum):
    """Challenge categories."""
    WEB = "web"
    PWN = "pwn"
    CRYPTO = "crypto"
    FORENSICS = "forensics"
    REVERSE = "reverse"
    MISC = "misc"
    OSINT = "osint"
    BLOCKCHAIN = "blockchain"
    HARDWARE = "hardware"
    STEGANOGRAPHY = "steganography"


class FlagFormat(str, Enum):
    """Flag format types."""
    STATIC = "static"      # Fixed flag
    DYNAMIC = "dynamic"    # Per-user generated flag
    REGEX = "regex"        # Regex pattern match


class ChallengeType(str, Enum):
    """Challenge deployment types."""
    STATIC = "static"           # Files only, no infrastructure
    CONTAINERIZED = "containerized"  # Docker container per user/team
    VM = "vm"                   # Full VM instance
    CLOUD = "cloud"             # Cloud-based (AWS, GCP, etc.)


@dataclass
class Flag:
    """Value object for challenge flag."""
    value: str
    format: FlagFormat = FlagFormat.STATIC
    case_sensitive: bool = True
    
    def matches(self, submission: str) -> bool:
        """Check if submission matches the flag."""
        if self.format == FlagFormat.STATIC:
            if self.case_sensitive:
                return submission == self.value
            return submission.lower() == self.value.lower()
        
        elif self.format == FlagFormat.REGEX:
            import re
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return bool(re.match(self.value, submission, flags))
        
        elif self.format == FlagFormat.DYNAMIC:
            # Dynamic flags are verified differently (per-user)
            raise NotImplementedError("Dynamic flags require user context")
        
        return False


@dataclass
class Hint:
    """Challenge hint with optional cost."""
    id: UUID = field(default_factory=uuid4)
    content: str = ""
    cost: int = 0  # Points deducted when revealed
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "content": self.content,
            "cost": self.cost,
            "order": self.order,
        }


@dataclass
class Prerequisite:
    """Challenge prerequisite for hierarchical unlocks."""
    challenge_id: UUID
    required_points: Optional[int] = None  # Min points on prerequisite
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": str(self.challenge_id),
            "required_points": self.required_points,
        }


@dataclass
class ChallengeBase(ABC):
    """
    Abstract base class for all challenge types.
    
    Implements common functionality and defines interface for specific types.
    """
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    slug: str = ""
    description: str = ""
    
    # Classification
    category_id: UUID = field(default_factory=uuid4)
    difficulty: ChallengeDifficulty = ChallengeDifficulty.MEDIUM
    challenge_type: ChallengeType = ChallengeType.STATIC
    
    # Scoring
    points: int = 100
    is_dynamic_scoring: bool = False
    dynamic_score_min: Optional[int] = None
    dynamic_score_decay: Optional[int] = None
    
    # Flag
    flag: Optional[Flag] = None
    
    # Content
    hints: List[Hint] = field(default_factory=list)
    file_urls: List[str] = field(default_factory=list)
    
    # Prerequisites (hierarchical unlock)
    prerequisites: List[Prerequisite] = field(default_factory=list)
    
    # Statistics
    solve_count: int = 0
    attempt_count: int = 0
    
    # Visibility
    is_visible: bool = False
    release_at: Optional[datetime] = None
    
    # Authorship
    author_id: Optional[UUID] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None
    
    @abstractmethod
    def get_instance_config(self) -> Dict[str, Any]:
        """Get configuration for challenge instance deployment."""
        pass
    
    def is_available(self) -> bool:
        """Check if challenge is available to players."""
        if not self.is_visible:
            return False
        if self.deleted_at is not None:
            return False
        if self.release_at and datetime.utcnow() < self.release_at:
            return False
        return True
    
    def calculate_current_points(self) -> int:
        """Calculate current points based on dynamic scoring."""
        if not self.is_dynamic_scoring:
            return self.points
        
        if self.dynamic_score_min is None or self.dynamic_score_decay is None:
            return self.points
        
        # Decay formula: points - (solve_count * decay)
        decayed = self.points - (self.solve_count * self.dynamic_score_decay)
        return max(decayed, self.dynamic_score_min)
    
    def record_solve(self) -> int:
        """Record a successful solve and return points awarded."""
        points = self.calculate_current_points()
        self.solve_count += 1
        self.updated_at = datetime.utcnow()
        return points
    
    def record_attempt(self) -> None:
        """Record a submission attempt."""
        self.attempt_count += 1
        self.updated_at = datetime.utcnow()
    
    def add_hint(self, content: str, cost: int = 0) -> Hint:
        """Add a hint to the challenge."""
        hint = Hint(
            content=content,
            cost=cost,
            order=len(self.hints),
        )
        self.hints.append(hint)
        self.updated_at = datetime.utcnow()
        return hint
    
    def add_prerequisite(
        self, 
        challenge_id: UUID, 
        required_points: Optional[int] = None
    ) -> Prerequisite:
        """Add a prerequisite challenge."""
        prereq = Prerequisite(
            challenge_id=challenge_id,
            required_points=required_points,
        )
        self.prerequisites.append(prereq)
        self.updated_at = datetime.utcnow()
        return prereq
    
    def check_prerequisites_met(
        self, 
        solved_challenges: Dict[UUID, int]  # challenge_id -> points earned
    ) -> bool:
        """Check if all prerequisites are met."""
        for prereq in self.prerequisites:
            if prereq.challenge_id not in solved_challenges:
                return False
            if prereq.required_points is not None:
                if solved_challenges[prereq.challenge_id] < prereq.required_points:
                    return False
        return True


@dataclass
class StaticChallenge(ChallengeBase):
    """
    Static challenge - files only, no infrastructure.
    
    Examples: Crypto puzzles, forensics files, reversing binaries
    """
    challenge_type: ChallengeType = field(default=ChallengeType.STATIC)
    
    def get_instance_config(self) -> Dict[str, Any]:
        """Static challenges don't need instance configuration."""
        return {
            "type": "static",
            "files": self.file_urls,
        }


@dataclass
class ContainerizedChallenge(ChallengeBase):
    """
    Containerized challenge - Docker container per user/team.
    
    Examples: Web challenges, pwn challenges with services
    """
    challenge_type: ChallengeType = field(default=ChallengeType.CONTAINERIZED)
    
    # Docker configuration
    docker_image: str = ""
    docker_registry: Optional[str] = None
    service_port: int = 80
    
    # Resource limits
    memory_limit: str = "256m"
    cpu_limit: float = 0.5
    
    # Networking
    expose_ports: List[int] = field(default_factory=list)
    internal_network: bool = True
    
    # Lifecycle
    instance_timeout: int = 3600  # seconds
    max_instances_per_user: int = 1
    
    def get_instance_config(self) -> Dict[str, Any]:
        """Get Docker container configuration."""
        return {
            "type": "containerized",
            "image": self.docker_image,
            "registry": self.docker_registry,
            "port": self.service_port,
            "memory": self.memory_limit,
            "cpu": self.cpu_limit,
            "expose_ports": self.expose_ports,
            "internal_network": self.internal_network,
            "timeout": self.instance_timeout,
        }


@dataclass
class VMChallenge(ChallengeBase):
    """
    VM challenge - Full virtual machine instance.
    
    Examples: Full system exploitation, AD challenges
    """
    challenge_type: ChallengeType = field(default=ChallengeType.VM)
    
    # VM configuration
    vm_template: str = ""
    vm_provider: str = "proxmox"  # proxmox, vmware, libvirt
    
    # Resources
    vcpus: int = 2
    memory_mb: int = 2048
    disk_gb: int = 20
    
    # Networking
    network_mode: str = "isolated"  # isolated, nat, bridged
    vpn_required: bool = True
    
    # Lifecycle
    instance_timeout: int = 7200  # 2 hours
    snapshot_enabled: bool = True
    
    def get_instance_config(self) -> Dict[str, Any]:
        """Get VM configuration."""
        return {
            "type": "vm",
            "template": self.vm_template,
            "provider": self.vm_provider,
            "vcpus": self.vcpus,
            "memory_mb": self.memory_mb,
            "disk_gb": self.disk_gb,
            "network_mode": self.network_mode,
            "vpn_required": self.vpn_required,
            "timeout": self.instance_timeout,
            "snapshot": self.snapshot_enabled,
        }


@dataclass
class CloudChallenge(ChallengeBase):
    """
    Cloud challenge - Cloud provider infrastructure.
    
    Examples: AWS/GCP/Azure exploitation, cloud misconfigurations
    """
    challenge_type: ChallengeType = field(default=ChallengeType.CLOUD)
    
    # Cloud configuration
    cloud_provider: str = "aws"  # aws, gcp, azure
    terraform_module: str = ""
    
    # Resources
    estimated_cost_per_hour: float = 0.0
    max_runtime_hours: int = 2
    
    # Credentials
    credential_type: str = "iam_user"  # iam_user, service_account, etc.
    
    def get_instance_config(self) -> Dict[str, Any]:
        """Get cloud infrastructure configuration."""
        return {
            "type": "cloud",
            "provider": self.cloud_provider,
            "terraform": self.terraform_module,
            "cost_per_hour": self.estimated_cost_per_hour,
            "max_runtime": self.max_runtime_hours,
            "credential_type": self.credential_type,
        }


# Factory function for creating challenges
def create_challenge(
    challenge_type: ChallengeType,
    **kwargs: Any
) -> ChallengeBase:
    """
    Factory function to create appropriate challenge type.
    
    Args:
        challenge_type: Type of challenge to create
        **kwargs: Challenge attributes
        
    Returns:
        Appropriate challenge subclass instance
    """
    type_map = {
        ChallengeType.STATIC: StaticChallenge,
        ChallengeType.CONTAINERIZED: ContainerizedChallenge,
        ChallengeType.VM: VMChallenge,
        ChallengeType.CLOUD: CloudChallenge,
    }
    
    challenge_class = type_map.get(challenge_type)
    if challenge_class is None:
        raise ValueError(f"Unknown challenge type: {challenge_type}")
    
    return challenge_class(**kwargs)
