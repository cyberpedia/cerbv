"""
Challenge Manager - Lifecycle management for challenge instances

Handles:
- Instance spawning with retry logic
- Instance tracking and state management
- Resource cleanup and zombie reaping
- Queue management for resource exhaustion
- Integration with different sandbox providers
"""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

from ..models import (
    ChallengeInstance,
    HealthStatus,
    InstanceStatus,
    SandboxType,
    SpawnRequest,
    SpawnResult,
)
from .health_checker import HealthChecker
from .sandbox_docker import DockerSandbox
from .sandbox_firecracker import FirecrackerSandbox
from .sandbox_terraform import TerraformSandbox

logger = structlog.get_logger(__name__)


class ResourceExhaustedError(Exception):
    """Raised when sandbox resources are exhausted."""
    pass


class InstanceNotFoundError(Exception):
    """Raised when an instance cannot be found."""
    pass


class ChallengeManager:
    """
    Central manager for challenge instance lifecycle.
    
    Coordinates between different sandbox providers and maintains
    instance state in database and cache.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        health_checker: Optional[HealthChecker] = None,
    ):
        self.db = db_manager
        self.cache = cache_manager
        self.health_checker = health_checker or HealthChecker()
        
        # Initialize sandbox providers
        self._sandboxes: Dict[SandboxType, any] = {
            SandboxType.DOCKER: DockerSandbox(),
            SandboxType.FIRECRACKER: FirecrackerSandbox(),
            SandboxType.TERRAFORM_AWS: TerraformSandbox(provider="aws"),
            SandboxType.TERRAFORM_GCP: TerraformSandbox(provider="gcp"),
        }
        
        # In-memory tracking for active instances
        self._active_instances: Dict[UUID, ChallengeInstance] = {}
        self._instance_locks: Dict[UUID, asyncio.Lock] = {}
        
        # Configuration
        self._max_retries = 3
        self._spawn_timeout = 120  # seconds
        self._default_instance_timeout = 7200  # 2 hours
        self._zombie_check_interval = 60  # seconds
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._zombie_reaper_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start background tasks for cleanup and monitoring."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._zombie_reaper_task = asyncio.create_task(self._zombie_reaper_loop())
        logger.info("Challenge manager started")
    
    async def stop(self) -> None:
        """Stop background tasks and cleanup."""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._zombie_reaper_task:
            self._zombie_reaper_task.cancel()
            try:
                await self._zombie_reaper_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup all active instances
        await self._cleanup_all_instances()
        logger.info("Challenge manager stopped")
    
    def _get_instance_lock(self, instance_id: UUID) -> asyncio.Lock:
        """Get or create a lock for an instance."""
        if instance_id not in self._instance_locks:
            self._instance_locks[instance_id] = asyncio.Lock()
        return self._instance_locks[instance_id]
    
    def _generate_canary_token(
        self,
        challenge_id: UUID,
        user_id: UUID,
        team_id: Optional[UUID],
    ) -> str:
        """Generate a unique canary token for anti-cheat detection."""
        data = f"{challenge_id}:{user_id}:{team_id}:{secrets.token_hex(16)}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    @retry(
        retry=retry_if_exception_type(ResourceExhaustedError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def spawn(self, request: SpawnRequest) -> SpawnResult:
        """
        Spawn a new challenge instance with retry logic.
        
        Args:
            request: Spawn request with challenge and user details
            
        Returns:
            SpawnResult with instance details or error
        """
        instance_id = UUID(int=secrets.randbits(128))
        
        async with self._get_instance_lock(instance_id):
            try:
                # Check user instance limits
                user_instance_count = await self._get_user_active_instance_count(
                    request.user_id
                )
                if user_instance_count >= 3:  # Max 3 instances per user
                    return SpawnResult(
                        success=False,
                        error_message="Maximum active instances reached (3)",
                        retryable=False,
                    )
                
                # Create instance record
                instance = ChallengeInstance(
                    id=instance_id,
                    challenge_id=request.challenge_id,
                    user_id=request.user_id,
                    team_id=request.team_id,
                    sandbox_type=request.sandbox_type,
                    status=InstanceStatus.CREATING,
                    canary_token=self._generate_canary_token(
                        request.challenge_id,
                        request.user_id,
                        request.team_id,
                    ),
                    expires_at=datetime.utcnow() + timedelta(
                        seconds=request.timeout_seconds
                    ),
                )
                
                # Apply resource overrides if provided
                if request.resource_overrides:
                    instance.resources = request.resource_overrides
                
                # Store in cache and memory
                await self._persist_instance(instance)
                self._active_instances[instance_id] = instance
                
                # Get sandbox provider
                sandbox = self._sandboxes.get(request.sandbox_type)
                if not sandbox:
                    raise ValueError(f"Unknown sandbox type: {request.sandbox_type}")
                
                # Spawn the instance
                logger.info(
                    "Spawning challenge instance",
                    instance_id=str(instance_id),
                    challenge_id=str(request.challenge_id),
                    user_id=str(request.user_id),
                    sandbox_type=request.sandbox_type.value,
                )
                
                spawn_result = await asyncio.wait_for(
                    sandbox.spawn(instance),
                    timeout=self._spawn_timeout,
                )
                
                if not spawn_result.success:
                    instance.update_status(InstanceStatus.ERROR)
                    await self._persist_instance(instance)
                    return spawn_result
                
                # Update instance with spawn result
                instance = spawn_result.instance
                instance.update_status(InstanceStatus.RUNNING)
                await self._persist_instance(instance)
                
                # Schedule health check
                if self.health_checker:
                    await self.health_checker.schedule_check(instance)
                
                logger.info(
                    "Challenge instance spawned successfully",
                    instance_id=str(instance_id),
                    provider_instance_id=instance.provider_instance_id,
                )
                
                return SpawnResult(success=True, instance=instance)
                
            except asyncio.TimeoutError:
                logger.error(
                    "Spawn timeout",
                    instance_id=str(instance_id),
                    challenge_id=str(request.challenge_id),
                )
                await self._destroy_instance(instance_id)
                return SpawnResult(
                    success=False,
                    error_message="Instance spawn timeout",
                    retryable=True,
                )
                
            except ResourceExhaustedError:
                logger.warning(
                    "Resources exhausted, queuing request",
                    challenge_id=str(request.challenge_id),
                    user_id=str(request.user_id),
                )
                await self._queue_spawn_request(request)
                raise  # Will trigger retry
                
            except Exception as e:
                logger.exception(
                    "Failed to spawn instance",
                    instance_id=str(instance_id),
                    error=str(e),
                )
                await self._destroy_instance(instance_id)
                return SpawnResult(
                    success=False,
                    error_message=f"Spawn failed: {str(e)}",
                    retryable=False,
                )
    
    async def destroy(self, instance_id: UUID) -> bool:
        """
        Destroy a challenge instance.
        
        Args:
            instance_id: ID of the instance to destroy
            
        Returns:
            True if destroyed successfully
        """
        async with self._get_instance_lock(instance_id):
            return await self._destroy_instance(instance_id)
    
    async def _destroy_instance(self, instance_id: UUID) -> bool:
        """Internal destroy method (must hold instance lock)."""
        try:
            instance = await self._get_instance(instance_id)
            if not instance:
                logger.warning(
                    "Attempted to destroy non-existent instance",
                    instance_id=str(instance_id),
                )
                return False
            
            if instance.status in [InstanceStatus.DESTROYED, InstanceStatus.DESTROYING]:
                return True
            
            instance.update_status(InstanceStatus.DESTROYING)
            await self._persist_instance(instance)
            
            # Get sandbox provider and destroy
            sandbox = self._sandboxes.get(instance.sandbox_type)
            if sandbox and instance.provider_instance_id:
                try:
                    await sandbox.destroy(instance)
                except Exception as e:
                    logger.error(
                        "Sandbox destroy failed",
                        instance_id=str(instance_id),
                        error=str(e),
                    )
            
            instance.update_status(InstanceStatus.DESTROYED)
            await self._persist_instance(instance)
            
            # Cleanup
            if instance_id in self._active_instances:
                del self._active_instances[instance_id]
            
            logger.info(
                "Instance destroyed",
                instance_id=str(instance_id),
                provider_instance_id=instance.provider_instance_id,
            )
            
            return True
            
        except Exception as e:
            logger.exception(
                "Error destroying instance",
                instance_id=str(instance_id),
                error=str(e),
            )
            return False
    
    async def get_status(self, instance_id: UUID) -> Optional[ChallengeInstance]:
        """Get current status of an instance."""
        return await self._get_instance(instance_id)
    
    async def list_user_instances(self, user_id: UUID) -> List[ChallengeInstance]:
        """List all active instances for a user."""
        instances = []
        for instance in self._active_instances.values():
            if instance.user_id == user_id and instance.is_active():
                instances.append(instance)
        return instances
    
    async def extend_timeout(
        self,
        instance_id: UUID,
        additional_seconds: int,
    ) -> bool:
        """Extend the timeout of an active instance."""
        async with self._get_instance_lock(instance_id):
            instance = await self._get_instance(instance_id)
            if not instance or not instance.is_active():
                return False
            
            if instance.expires_at:
                instance.expires_at += timedelta(seconds=additional_seconds)
            else:
                instance.expires_at = datetime.utcnow() + timedelta(
                    seconds=additional_seconds
                )
            
            await self._persist_instance(instance)
            return True
    
    async def update_health_status(
        self,
        instance_id: UUID,
        health: HealthStatus,
    ) -> None:
        """Update health status for an instance."""
        async with self._get_instance_lock(instance_id):
            instance = await self._get_instance(instance_id)
            if not instance:
                return
            
            instance.last_health_check = datetime.utcnow()
            
            if health.healthy:
                instance.health_check_failures = 0
                if instance.status == InstanceStatus.UNHEALTHY:
                    instance.update_status(InstanceStatus.HEALTHY)
            else:
                instance.health_check_failures += 1
                if instance.health_check_failures >= 3:
                    instance.update_status(InstanceStatus.UNHEALTHY)
                    logger.warning(
                        "Instance marked unhealthy",
                        instance_id=str(instance_id),
                        failures=instance.health_check_failures,
                    )
            
            await self._persist_instance(instance)
    
    async def _get_instance(self, instance_id: UUID) -> Optional[ChallengeInstance]:
        """Get instance from memory or cache."""
        # Check memory first
        if instance_id in self._active_instances:
            return self._active_instances[instance_id]
        
        # Check cache
        cache_key = f"instance:{instance_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            # Deserialize from cache
            # TODO: Implement proper deserialization
            pass
        
        return None
    
    async def _persist_instance(self, instance: ChallengeInstance) -> None:
        """Persist instance to cache and database."""
        # Cache for quick access
        cache_key = f"instance:{instance.id}"
        await self.cache.set(
            cache_key,
            instance.to_dict(),
            ttl=instance.expires_at.timestamp() - datetime.utcnow().timestamp()
            if instance.expires_at
            else 7200,
        )
        
        # TODO: Persist to database for durability
    
    async def _get_user_active_instance_count(self, user_id: UUID) -> int:
        """Count active instances for a user."""
        count = 0
        for instance in self._active_instances.values():
            if instance.user_id == user_id and instance.is_active():
                count += 1
        return count
    
    async def _queue_spawn_request(self, request: SpawnRequest) -> None:
        """Queue a spawn request for later processing."""
        queue_key = "spawn_queue"
        await self.cache.lpush(queue_key, request.to_dict())
    
    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup expired instances."""
        while self._running:
            try:
                await asyncio.sleep(30)
                
                expired_instances: List[UUID] = []
                for instance_id, instance in self._active_instances.items():
                    if instance.is_expired():
                        expired_instances.append(instance_id)
                
                for instance_id in expired_instances:
                    logger.info(
                        "Cleaning up expired instance",
                        instance_id=str(instance_id),
                    )
                    await self.destroy(instance_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))
    
    async def _zombie_reaper_loop(self) -> None:
        """Background loop to reap zombie instances."""
        while self._running:
            try:
                await asyncio.sleep(self._zombie_check_interval)
                
                # Check for instances that are stuck in creating/running state
                # but don't have corresponding provider resources
                for instance_id, instance in list(self._active_instances.items()):
                    if instance.status in [InstanceStatus.CREATING, InstanceStatus.RUNNING]:
                        # Verify with provider
                        sandbox = self._sandboxes.get(instance.sandbox_type)
                        if sandbox and instance.provider_instance_id:
                            exists = await sandbox.exists(instance)
                            if not exists:
                                logger.warning(
                                    "Zombie instance detected, cleaning up",
                                    instance_id=str(instance_id),
                                    provider_instance_id=instance.provider_instance_id,
                                )
                                await self._destroy_instance(instance_id)
                                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in zombie reaper loop", error=str(e))
    
    async def _cleanup_all_instances(self) -> None:
        """Cleanup all active instances on shutdown."""
        cleanup_tasks = []
        for instance_id in list(self._active_instances.keys()):
            task = asyncio.create_task(self.destroy(instance_id))
            cleanup_tasks.append(task)
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)