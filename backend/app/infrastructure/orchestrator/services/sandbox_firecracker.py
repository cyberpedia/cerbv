"""
Firecracker Sandbox - MicroVM-based isolation for kernel pwn and Windows challenges

Features:
- API socket per VM (Unix socket)
- Jailer for chroot isolation
- TAP interfaces for networking
- Pre-built microVM images (Ubuntu 22.04 minimal, Windows Server Core)
- 5 second boot time target
"""

import asyncio
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp
import structlog

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


class FirecrackerSandbox:
    """
    Firecracker microVM sandbox for high-isolation challenges.
    
    Ideal for:
    - Kernel exploitation challenges
    - Windows reverse engineering
    - Challenges requiring full system access
    """
    
    # Paths
    FIRECRACKER_BINARY = "/usr/local/bin/firecracker"
    JAILER_BINARY = "/usr/local/bin/jailer"
    VM_IMAGES_DIR = Path("/opt/cerberus/orchestrator/vm-images")
    
    # VM Configuration
    DEFAULT_VCPUS = 2
    DEFAULT_MEMORY_MB = 512
    DEFAULT_DISK_GB = 5
    
    # Network
    TAP_PREFIX = "fc-tap"
    BRIDGE_NAME = "fc-br0"
    
    def __init__(
        self,
        firecracker_binary: Optional[str] = None,
        jailer_binary: Optional[str] = None,
        vm_images_dir: Optional[Path] = None,
    ):
        self.firecracker_binary = firecracker_binary or self.FIRECRACKER_BINARY
        self.jailer_binary = jailer_binary or self.JAILER_BINARY
        self.vm_images_dir = vm_images_dir or self.VM_IMAGES_DIR
        
        # Track running VMs
        self._vms: Dict[UUID, Dict[str, Any]] = {}
        self._vm_locks: Dict[UUID, asyncio.Lock] = {}
    
    def _get_vm_lock(self, instance_id: UUID) -> asyncio.Lock:
        """Get or create a lock for a VM."""
        if instance_id not in self._vm_locks:
            self._vm_locks[instance_id] = asyncio.Lock()
        return self._vm_locks[instance_id]
    
    async def spawn(self, instance: ChallengeInstance) -> SpawnResult:
        """
        Spawn a new Firecracker microVM.
        
        Args:
            instance: Challenge instance configuration
            
        Returns:
            SpawnResult with VM details
        """
        async with self._get_vm_lock(instance.id):
            try:
                # Prepare VM configuration
                vm_config = await self._prepare_vm_config(instance)
                
                # Create jailer environment
                jailer_dir = await self._create_jailer_environment(instance)
                
                # Setup networking
                tap_device = await self._setup_networking(instance)
                
                # Start Firecracker with Jailer
                vm_process = await self._start_firecracker(
                    instance,
                    vm_config,
                    jailer_dir,
                    tap_device,
                )
                
                # Wait for API socket
                api_socket = jailer_dir / "run" / "firecracker.socket"
                await self._wait_for_api_socket(api_socket)
                
                # Configure VM via API
                await self._configure_vm(instance, vm_config, api_socket)
                
                # Start microVM
                await self._start_microvm(api_socket)
                
                # Wait for VM to boot
                await self._wait_for_boot(instance, vm_config)
                
                # Update instance
                instance.provider_instance_id = str(jailer_dir)
                instance.network = NetworkConfig(
                    internal_ip=vm_config.get("guest_ip"),
                    port_mappings=vm_config.get("port_mappings", {}),
                )
                instance.access_url = await self._build_access_url(instance, vm_config)
                
                # Track VM
                self._vms[instance.id] = {
                    "process": vm_process,
                    "jailer_dir": jailer_dir,
                    "api_socket": api_socket,
                    "tap_device": tap_device,
                    "config": vm_config,
                }
                
                logger.info(
                    "Firecracker VM started",
                    instance_id=str(instance.id),
                    jailer_dir=str(jailer_dir),
                    boot_time_ms=vm_config.get("boot_time_ms", 0),
                )
                
                return SpawnResult(success=True, instance=instance)
                
            except Exception as e:
                logger.exception(
                    "Failed to spawn Firecracker VM",
                    instance_id=str(instance.id),
                    error=str(e),
                )
                # Cleanup on failure
                await self._cleanup_vm(instance)
                return SpawnResult(
                    success=False,
                    error_message=f"Firecracker spawn failed: {str(e)}",
                    retryable=False,
                )
    
    async def destroy(self, instance: ChallengeInstance) -> bool:
        """
        Destroy a Firecracker microVM.
        
        Args:
            instance: Challenge instance to destroy
            
        Returns:
            True if destroyed successfully
        """
        async with self._get_vm_lock(instance.id):
            return await self._cleanup_vm(instance)
    
    async def exists(self, instance: ChallengeInstance) -> bool:
        """Check if VM is still running."""
        if instance.id not in self._vms:
            return False
        
        vm_info = self._vms[instance.id]
        process = vm_info.get("process")
        
        if process is None:
            return False
        
        # Check if process is still running
        return process.returncode is None
    
    async def get_logs(self, instance: ChallengeInstance) -> str:
        """Get VM serial console logs."""
        try:
            vm_info = self._vms.get(instance.id)
            if not vm_info:
                return ""
            
            log_path = vm_info["jailer_dir"] / "logs" / "serial.log"
            if log_path.exists():
                return log_path.read_text()
            return ""
            
        except Exception as e:
            logger.error(
                "Failed to get VM logs",
                instance_id=str(instance.id),
                error=str(e),
            )
            return ""
    
    async def exec_command(
        self,
        instance: ChallengeInstance,
        command: List[str],
    ) -> Dict[str, Any]:
        """Execute a command in the VM via SSH or serial."""
        # TODO: Implement SSH-based command execution
        return {"exit_code": -1, "output": "", "error": "Not implemented"}
    
    async def get_stats(self, instance: ChallengeInstance) -> Dict[str, Any]:
        """Get VM resource statistics."""
        try:
            vm_info = self._vms.get(instance.id)
            if not vm_info:
                return {}
            
            api_socket = vm_info["api_socket"]
            
            async with aiohttp.UnixConnector(path=str(api_socket)) as connector:
                async with aiohttp.ClientSession(connector=connector) as session:
                    # Get machine configuration
                    async with session.get("http://localhost/machine-config") as resp:
                        machine_config = await resp.json()
                    
                    # Get balloon stats if enabled
                    async with session.get("http://localhost/balloon/statistics") as resp:
                        if resp.status == 200:
                            balloon_stats = await resp.json()
                        else:
                            balloon_stats = {}
            
            return {
                "vcpus": machine_config.get("vcpu_count"),
                "memory_mb": machine_config.get("mem_size_mib"),
                "balloon_stats": balloon_stats,
            }
            
        except Exception as e:
            logger.error(
                "Failed to get VM stats",
                instance_id=str(instance.id),
                error=str(e),
            )
            return {}
    
    async def _prepare_vm_config(self, instance: ChallengeInstance) -> Dict[str, Any]:
        """Prepare VM configuration."""
        # Get image from metadata
        image_name = instance.provider_metadata.get("vm_image", "ubuntu-22.04-minimal")
        is_windows = instance.provider_metadata.get("is_windows", False)
        
        # Resources
        vcpus = instance.resources.cpu_quota or self.DEFAULT_VCPUS
        memory_mb = instance.resources.memory_limit_mb or self.DEFAULT_MEMORY_MB
        
        # Generate unique IDs
        vm_id = instance.id.hex[:8]
        guest_mac = f"02:FC:00:00:{vm_id[:2]}:{vm_id[2:4]}"
        guest_ip = f"172.16.0.{int(vm_id[:2], 16) + 10}"
        
        # Port mappings
        port_mappings = {}
        if is_windows:
            port_mappings[3389] = 3389  # RDP
        else:
            port_mappings[22] = 22  # SSH
            port_mappings[80] = 80  # HTTP
        
        config = {
            "vm_id": vm_id,
            "image_name": image_name,
            "is_windows": is_windows,
            "vcpus": int(vcpus),
            "memory_mb": memory_mb,
            "guest_mac": guest_mac,
            "guest_ip": guest_ip,
            "port_mappings": port_mappings,
            "kernel_image": self.vm_images_dir / f"{image_name}-vmlinux",
            "rootfs_image": self.vm_images_dir / f"{image_name}-rootfs.ext4",
        }
        
        return config
    
    async def _create_jailer_environment(
        self,
        instance: ChallengeInstance,
    ) -> Path:
        """Create chroot jail environment for the VM."""
        vm_id = instance.id.hex[:8]
        jailer_dir = Path(f"/srv/jailer/firecracker/{vm_id}/root")
        
        # Create directory structure
        for subdir in ["run", "dev", "logs", "images"]:
            (jailer_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Create device nodes
        await self._create_device_nodes(jailer_dir)
        
        return jailer_dir
    
    async def _create_device_nodes(self, jailer_dir: Path) -> None:
        """Create necessary device nodes in the jail."""
        devices = [
            ("/dev/null", "c", 1, 3),
            ("/dev/zero", "c", 1, 5),
            ("/dev/random", "c", 1, 8),
            ("/dev/urandom", "c", 1, 9),
            ("/dev/tty", "c", 5, 0),
        ]
        
        for dev_path, dev_type, major, minor in devices:
            full_path = jailer_dir / dev_path.lstrip("/")
            try:
                subprocess.run(
                    ["mknod", str(full_path), dev_type, str(major), str(minor)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                pass  # May already exist
    
    async def _setup_networking(self, instance: ChallengeInstance) -> str:
        """Setup TAP device and networking for the VM."""
        vm_id = instance.id.hex[:8]
        tap_device = f"{self.TAP_PREFIX}-{vm_id}"
        
        # Create TAP device
        try:
            subprocess.run(
                ["ip", "tuntap", "add", tap_device, "mode", "tap"],
                check=True,
                capture_output=True,
            )
            
            # Bring up TAP device
            subprocess.run(
                ["ip", "link", "set", tap_device, "up"],
                check=True,
                capture_output=True,
            )
            
            # Add to bridge
            subprocess.run(
                ["ip", "link", "set", tap_device, "master", self.BRIDGE_NAME],
                check=True,
                capture_output=True,
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to setup networking",
                instance_id=str(instance.id),
                error=e.stderr.decode(),
            )
            raise
        
        return tap_device
    
    async def _start_firecracker(
        self,
        instance: ChallengeInstance,
        vm_config: Dict[str, Any],
        jailer_dir: Path,
        tap_device: str,
    ) -> asyncio.subprocess.Process:
        """Start Firecracker process with Jailer."""
        vm_id = instance.id.hex[:8]
        
        # Build jailer command
        cmd = [
            self.jailer_binary,
            "--id", vm_id,
            "--uid", "1000",
            "--gid", "1000",
            "--chroot-base-dir", str(jailer_dir.parent),
            "--exec-file", self.firecracker_binary,
            "--",
            "--api-sock", "/run/firecracker.socket",
            "--log-path", "/logs/firecracker.log",
            "--level", "Info",
            "--show-log-origin",
            "--show-log-level",
        ]
        
        # Start process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        return process
    
    async def _wait_for_api_socket(self, api_socket: Path, timeout: int = 10) -> None:
        """Wait for Firecracker API socket to be ready."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            if api_socket.exists():
                return
            
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("API socket not ready")
            
            await asyncio.sleep(0.1)
    
    async def _configure_vm(
        self,
        instance: ChallengeInstance,
        vm_config: Dict[str, Any],
        api_socket: Path,
    ) -> None:
        """Configure VM via Firecracker API."""
        async with aiohttp.UnixConnector(path=str(api_socket)) as connector:
            async with aiohttp.ClientSession(connector=connector) as session:
                # Set machine configuration
                machine_config = {
                    "vcpu_count": vm_config["vcpus"],
                    "mem_size_mib": vm_config["memory_mb"],
                    "smt": False,
                    "track_dirty_pages": False,
                }
                
                async with session.put(
                    "http://localhost/machine-config",
                    json=machine_config,
                ) as resp:
                    if resp.status not in [200, 204]:
                        raise RuntimeError(f"Failed to set machine config: {resp.status}")
                
                # Set boot source
                boot_source = {
                    "kernel_image_path": str(vm_config["kernel_image"]),
                    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
                }
                
                async with session.put(
                    "http://localhost/boot-source",
                    json=boot_source,
                ) as resp:
                    if resp.status not in [200, 204]:
                        raise RuntimeError(f"Failed to set boot source: {resp.status}")
                
                # Add root drive
                drives = [
                    {
                        "drive_id": "rootfs",
                        "path_on_host": str(vm_config["rootfs_image"]),
                        "is_root_device": True,
                        "is_read_only": False,
                    }
                ]
                
                for drive in drives:
                    async with session.put(
                        "http://localhost/drives/rootfs",
                        json=drive,
                    ) as resp:
                        if resp.status not in [200, 204]:
                            raise RuntimeError(f"Failed to add drive: {resp.status}")
                
                # Add network interface
                network_interface = {
                    "iface_id": "eth0",
                    "guest_mac": vm_config["guest_mac"],
                    "host_dev_name": f"{self.TAP_PREFIX}-{vm_config['vm_id']}",
                }
                
                async with session.put(
                    "http://localhost/network-interfaces/eth0",
                    json=network_interface,
                ) as resp:
                    if resp.status not in [200, 204]:
                        raise RuntimeError(f"Failed to add network interface: {resp.status}")
    
    async def _start_microvm(self, api_socket: Path) -> None:
        """Start the microVM instance."""
        async with aiohttp.UnixConnector(path=str(api_socket)) as connector:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.put(
                    "http://localhost/actions",
                    json={"action_type": "InstanceStart"},
                ) as resp:
                    if resp.status not in [200, 204]:
                        raise RuntimeError(f"Failed to start microVM: {resp.status}")
    
    async def _wait_for_boot(
        self,
        instance: ChallengeInstance,
        vm_config: Dict[str, Any],
        timeout: int = 30,
    ) -> None:
        """Wait for VM to finish booting."""
        start_time = asyncio.get_event_loop().time()
        
        # Simple wait - in production, check for service availability
        await asyncio.sleep(2)
        
        boot_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        vm_config["boot_time_ms"] = boot_time_ms
        
        logger.info(
            "VM booted",
            instance_id=str(instance.id),
            boot_time_ms=boot_time_ms,
        )
    
    async def _build_access_url(
        self,
        instance: ChallengeInstance,
        vm_config: Dict[str, Any],
    ) -> Optional[str]:
        """Build access URL for the VM."""
        # For Windows with RDP
        if vm_config.get("is_windows"):
            return f"rdp://{vm_config['guest_ip']}:3389"
        
        # For Linux with SSH
        return f"ssh://root@{vm_config['guest_ip']}:22"
    
    async def _cleanup_vm(self, instance: ChallengeInstance) -> bool:
        """Cleanup VM resources."""
        try:
            vm_info = self._vms.get(instance.id)
            
            if vm_info:
                # Stop Firecracker process
                process = vm_info.get("process")
                if process and process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                
                # Remove TAP device
                tap_device = vm_info.get("tap_device")
                if tap_device:
                    try:
                        subprocess.run(
                            ["ip", "link", "delete", tap_device],
                            check=False,
                            capture_output=True,
                        )
                    except Exception:
                        pass
                
                # Cleanup jailer directory
                jailer_dir = vm_info.get("jailer_dir")
                if jailer_dir and jailer_dir.exists():
                    import shutil
                    shutil.rmtree(jailer_dir, ignore_errors=True)
            
            # Remove from tracking
            if instance.id in self._vms:
                del self._vms[instance.id]
            
            return True
            
        except Exception as e:
            logger.error(
                "Error during VM cleanup",
                instance_id=str(instance.id),
                error=str(e),
            )
            return False