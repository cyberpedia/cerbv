"""
Cerberus CTF Platform - Challenge Orchestrator

Sandbox management system supporting:
- Static files (CDN delivery)
- Docker containers (isolated per team/user)
- Firecracker VMs (microVMs for kernel pwn/windows)
- Cloud sandboxes (Terraform AWS/GCP)
- Hardware labs (remote access)
"""

from .services.challenge_manager import ChallengeManager
from .services.sandbox_docker import DockerSandbox
from .services.sandbox_firecracker import FirecrackerSandbox
from .services.sandbox_terraform import TerraformSandbox
from .services.health_checker import HealthChecker

__all__ = [
    "ChallengeManager",
    "DockerSandbox",
    "FirecrackerSandbox",
    "TerraformSandbox",
    "HealthChecker",
]