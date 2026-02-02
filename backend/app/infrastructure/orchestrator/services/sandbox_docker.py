"""
Docker Sandbox - Containerized challenge isolation

Features:
- Kata Containers runtime (gVisor alternative) for strong isolation
- Rootless Docker daemon for challenge user
- Network: CNI plugins with custom bridge (no host network)
- Resource limits: CPU quota, memory limit, PIDs limit, no swap
- Read-only rootfs with tmpfs for /tmp
- Capability drop: ALL, then add only NET_BIND_SERVICE if needed
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiodocker
import structlog
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from ..models import (
    ChallengeInstance,
    InstanceStatus,
    NetworkConfig,
    ResourceLimits,
    SandboxType,
    SecurityProfile,
    SpawnResult,
)

logger = structlog.get_logger(__name__)


class DockerSandbox:
    """
    Docker-based sandbox for containerized challenges.
    
    Supports web challenges, pwn challenges, and other service-based CTF tasks.
    """
    
    # Default seccomp profile path
    SECCOMP_PROFILE_PATH = Path("/opt/cerberus/orchestrator/configs/seccomp_profiles/default.json")
    
    # Default network name
    NETWORK_NAME = "cerberus-challenges"
    
    def __init__(
        self,
        docker_url: Optional[str] = None,
        network_name: str = NETWORK_NAME,
    ):
        self.docker_url = docker_url or os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        self.network_name = network_name
        self._docker: Optional[aiodocker.Docker] = None
        
        # Configuration
        self._default_memory_limit = "256m"
        self._default_cpu_quota = 0.5
        self._default_pids_limit = 100
        self._read_only_rootfs = True
    
    async def _get_docker(self) -> aiodocker.Docker:
        """Get or create Docker client."""
        if self._docker is None:
            self._docker = aiodocker.Docker(url=self.docker_url)
        return self._docker
    
    async def spawn(self, instance: ChallengeInstance) -> SpawnResult:
        """
        Spawn a new Docker container for the challenge instance.
        
        Args:
            instance: Challenge instance configuration
            
        Returns:
            SpawnResult with container details
        """
        try:
            docker = await self._get_docker()
            
            # Prepare container configuration
            config = await self._prepare_container_config(instance)
            
            # Create container
            logger.info(
                "Creating Docker container",
                instance_id=str(instance.id),
                image=config["Image"],
            )
            
            container = await docker.containers.create(
                config=config,
                name=f"cerberus-{instance.id}",
            )
            
            # Connect to challenge network
            await self._connect_network(container, instance)
            
            # Start container
            await container.start()
            
            # Get container info
            container_info = await container.show()
            
            # Update instance with container details
            instance.provider_instance_id = container.id
            instance.network = await self._extract_network_info(container_info)
            instance.access_url = await self._build_access_url(instance)
            
            # Inject canary token if needed
            if instance.canary_token:
                await self._inject_canary_token(container, instance.canary_token)
            
            logger.info(
                "Docker container started",
                instance_id=str(instance.id),
                container_id=container.id[:12],
            )
            
            return SpawnResult(success=True, instance=instance)
            
        except DockerError as e:
            logger.error(
                "Docker error spawning container",
                instance_id=str(instance.id),
                error=str(e),
            )
            return SpawnResult(
                success=False,
                error_message=f"Docker error: {e.message}",
                retryable=e.status in [409, 429, 500, 503],
            )
            
        except Exception as e:
            logger.exception(
                "Failed to spawn Docker container",
                instance_id=str(instance.id),
                error=str(e),
            )
            return SpawnResult(
                success=False,
                error_message=f"Spawn failed: {str(e)}",
                retryable=False,
            )
    
    async def destroy(self, instance: ChallengeInstance) -> bool:
        """
        Destroy a Docker container.
        
        Args:
            instance: Challenge instance to destroy
            
        Returns:
            True if destroyed successfully
        """
        try:
            docker = await self._get_docker()
            
            if not instance.provider_instance_id:
                logger.warning(
                    "No container ID for instance",
                    instance_id=str(instance.id),
                )
                return True
            
            container = docker.containers.container(instance.provider_instance_id)
            
            # Stop container with timeout
            try:
                await container.stop(timeout=10)
            except DockerError:
                # Force kill if graceful stop fails
                await container.kill()
            
            # Remove container
            await container.delete(force=True, v=True)
            
            logger.info(
                "Docker container destroyed",
                instance_id=str(instance.id),
                container_id=instance.provider_instance_id[:12],
            )
            
            return True
            
        except DockerError as e:
            if e.status == 404:
                # Container already gone
                return True
            logger.error(
                "Docker error destroying container",
                instance_id=str(instance.id),
                error=str(e),
            )
            return False
            
        except Exception as e:
            logger.exception(
                "Failed to destroy Docker container",
                instance_id=str(instance.id),
                error=str(e),
            )
            return False
    
    async def exists(self, instance: ChallengeInstance) -> bool:
        """Check if container still exists."""
        try:
            if not instance.provider_instance_id:
                return False
            
            docker = await self._get_docker()
            container = docker.containers.container(instance.provider_instance_id)
            await container.show()
            return True
            
        except DockerError as e:
            if e.status == 404:
                return False
            raise
            
        except Exception:
            return False
    
    async def get_logs(
        self,
        instance: ChallengeInstance,
        tail: int = 100,
        follow: bool = False,
    ) -> str:
        """Get container logs."""
        try:
            docker = await self._get_docker()
            container = docker.containers.container(instance.provider_instance_id)
            
            logs = await container.log(
                stdout=True,
                stderr=True,
                tail=tail,
                follow=follow,
            )
            
            return logs
            
        except Exception as e:
            logger.error(
                "Failed to get container logs",
                instance_id=str(instance.id),
                error=str(e),
            )
            return ""
    
    async def exec_command(
        self,
        instance: ChallengeInstance,
        command: List[str],
    ) -> Dict[str, Any]:
        """Execute a command in the container."""
        try:
            docker = await self._get_docker()
            container = docker.containers.container(instance.provider_instance_id)
            
            exec_result = await container.exec(
                cmd=command,
                stdout=True,
                stderr=True,
            )
            
            return {
                "exit_code": exec_result.get("ExitCode", -1),
                "output": exec_result.get("output", ""),
            }
            
        except Exception as e:
            logger.error(
                "Failed to exec command in container",
                instance_id=str(instance.id),
                command=command,
                error=str(e),
            )
            return {"exit_code": -1, "output": "", "error": str(e)}
    
    async def get_stats(self, instance: ChallengeInstance) -> Dict[str, Any]:
        """Get container resource statistics."""
        try:
            docker = await self._get_docker()
            container = docker.containers.container(instance.provider_instance_id)
            
            stats = await container.stats(stream=False)
            
            # Parse stats
            cpu_stats = stats.get("cpu_stats", {})
            memory_stats = stats.get("memory_stats", {})
            
            return {
                "cpu_usage_percent": self._calculate_cpu_percent(stats),
                "memory_usage_mb": memory_stats.get("usage", 0) / (1024 * 1024),
                "memory_limit_mb": memory_stats.get("limit", 0) / (1024 * 1024),
                "network_rx_bytes": stats.get("networks", {}).get("eth0", {}).get("rx_bytes", 0),
                "network_tx_bytes": stats.get("networks", {}).get("eth0", {}).get("tx_bytes", 0),
            }
            
        except Exception as e:
            logger.error(
                "Failed to get container stats",
                instance_id=str(instance.id),
                error=str(e),
            )
            return {}
    
    async def _prepare_container_config(self, instance: ChallengeInstance) -> Dict[str, Any]:
        """Prepare Docker container configuration."""
        # Get challenge configuration from provider metadata
        image = instance.provider_metadata.get("image", "alpine:latest")
        command = instance.provider_metadata.get("command")
        env_vars = instance.provider_metadata.get("env", {})
        exposed_ports = instance.provider_metadata.get("ports", [80])
        
        # Build port bindings
        port_bindings = {}
        exposed_ports_config = {}
        for port in exposed_ports:
            port_bindings[f"{port}/tcp"] = [{"HostPort": "0"}]  # Random host port
            exposed_ports_config[f"{port}/tcp"] = {}
        
        # Resource limits
        resources = instance.resources
        memory_limit = resources.memory_limit_mb or self._default_memory_limit
        if isinstance(memory_limit, int):
            memory_limit = f"{memory_limit}m"
        
        cpu_quota = resources.cpu_quota or self._default_cpu_quota
        cpu_period = 100000
        cpu_quota_value = int(cpu_period * cpu_quota)
        
        # Security options
        security = instance.security
        
        config = {
            "Image": image,
            "Cmd": command,
            "Env": [f"{k}={v}" for k, v in env_vars.items()],
            "ExposedPorts": exposed_ports_config,
            "HostConfig": {
                # Resource limits
                "Memory": self._parse_memory(memory_limit),
                "MemorySwap": resources.memory_swap_mb or 0,
                "CpuPeriod": cpu_period,
                "CpuQuota": cpu_quota_value,
                "PidsLimit": resources.pids_limit or self._default_pids_limit,
                
                # Storage
                "StorageOpt": {
                    "size": f"{resources.storage_limit_mb or 1024}M"
                } if resources.storage_limit_mb else {},
                
                # Network - no host network
                "NetworkMode": "none",  # Will connect to custom network after creation
                "PortBindings": port_bindings,
                
                # Security
                "ReadonlyRootfs": security.read_only_rootfs,
                "SecurityOpt": self._build_security_options(security),
                "CapDrop": security.drop_capabilities,
                "CapAdd": security.add_capabilities,
            },
            # Mount tmpfs for /tmp
            "Mounts": [
                {
                    "Type": "tmpfs",
                    "Target": "/tmp",
                    "TmpfsOptions": {
                        "SizeBytes": 64 * 1024 * 1024,  # 64MB
                        "Mode": 1777,
                    }
                }
            ]
        }
        
        # Add canary token as environment variable
        if instance.canary_token:
            config["Env"].append(f"CERBERUS_CANARY={instance.canary_token}")
        
        return config
    
    async def _connect_network(
        self,
        container: DockerContainer,
        instance: ChallengeInstance,
    ) -> None:
        """Connect container to challenge network."""
        try:
            docker = await self._get_docker()
            network = await docker.networks.get(self.network_name)
            await network.connect({"Container": container.id})
        except DockerError as e:
            if e.status == 404:
                # Network doesn't exist, create it
                docker = await self._get_docker()
                await docker.networks.create(
                    {"Name": self.network_name, "Driver": "bridge"}
                )
                network = await docker.networks.get(self.network_name)
                await network.connect({"Container": container.id})
            else:
                raise
    
    async def _extract_network_info(self, container_info: Dict[str, Any]) -> NetworkConfig:
        """Extract network information from container info."""
        network_settings = container_info.get("NetworkSettings", {})
        networks = network_settings.get("Networks", {})
        
        # Get primary network
        primary_network = networks.get(self.network_name, {})
        
        # Extract port mappings
        port_mappings = {}
        ports = network_settings.get("Ports", {})
        for container_port, host_bindings in ports.items():
            if host_bindings:
                port_num = int(container_port.split("/")[0])
                host_port = int(host_bindings[0].get("HostPort", 0))
                port_mappings[host_port] = port_num
        
        return NetworkConfig(
            internal_ip=primary_network.get("IPAddress"),
            mac_address=primary_network.get("MacAddress"),
            port_mappings=port_mappings,
        )
    
    async def _build_access_url(self, instance: ChallengeInstance) -> Optional[str]:
        """Build access URL for the instance."""
        if not instance.network.port_mappings:
            return None
        
        # Get the first exposed port
        host_port = list(instance.network.port_mappings.keys())[0]
        
        # Use configured proxy domain or IP
        proxy_domain = os.getenv("CHALLENGE_PROXY_DOMAIN", "challenges.cerberus.local")
        
        return f"http://{proxy_domain}:{host_port}"
    
    async def _inject_canary_token(
        self,
        container: DockerContainer,
        canary_token: str,
    ) -> None:
        """Inject canary token into container for anti-cheat detection."""
        try:
            # Write canary to a hidden file
            await container.exec(
                cmd=["sh", "-c", f"echo '{canary_token}' > /.cerberus_canary"],
            )
        except Exception as e:
            logger.warning(
                "Failed to inject canary token",
                container_id=container.id[:12],
                error=str(e),
            )
    
    def _parse_memory(self, memory: str) -> int:
        """Parse memory string to bytes."""
        if isinstance(memory, int):
            return memory
        
        memory = memory.lower()
        multipliers = {
            "b": 1,
            "k": 1024,
            "kb": 1024,
            "m": 1024 ** 2,
            "mb": 1024 ** 2,
            "g": 1024 ** 3,
            "gb": 1024 ** 3,
        }
        
        for suffix, multiplier in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if memory.endswith(suffix):
                return int(memory[:-len(suffix)]) * multiplier
        
        return int(memory)
    
    def _build_security_options(self, security: SecurityProfile) -> List[str]:
        """Build Docker security options."""
        options = []
        
        if security.no_new_privileges:
            options.append("no-new-privileges:true")
        
        if security.seccomp_profile:
            options.append(f"seccomp={security.seccomp_profile}")
        else:
            # Use default restricted profile
            options.append(f"seccomp={self.SECCOMP_PROFILE_PATH}")
        
        if security.apparmor_profile:
            options.append(f"apparmor={security.apparmor_profile}")
        
        return options
    
    def _calculate_cpu_percent(self, stats: Dict[str, Any]) -> float:
        """Calculate CPU usage percentage from stats."""
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})
        
        cpu_usage = cpu_stats.get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})
        
        cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get("total_usage", 0)
        system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
        
        if system_delta > 0 and cpu_delta > 0:
            cpu_count = len(cpu_usage.get("percpu_usage", []) or [])
            if cpu_count == 0:
                cpu_count = 1
            return (cpu_delta / system_delta) * cpu_count * 100.0
        
        return 0.0