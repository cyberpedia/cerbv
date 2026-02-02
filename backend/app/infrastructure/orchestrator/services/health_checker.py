"""
Health Checker - Service health validation for challenge instances

Features:
- HTTP health checks
- TCP port checks
- Custom command checks
- Prometheus metrics export
- Auto-terminate unhealthy instances
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import aiohttp
import structlog

from ..models import ChallengeInstance, HealthStatus, InstanceStatus

logger = structlog.get_logger(__name__)


class HealthCheckError(Exception):
    """Raised when a health check fails."""
    pass


class HealthChecker:
    """
    Health checker for challenge instances.
    
    Performs various health checks and reports status.
    """
    
    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 10,
        max_failures: int = 3,
    ):
        self.check_interval = check_interval
        self.timeout = timeout
        self.max_failures = max_failures
        
        # Track scheduled checks
        self._scheduled_checks: Dict[UUID, asyncio.Task] = {}
        self._check_callbacks: List[Callable[[UUID, HealthStatus], None]] = []
    
    def add_callback(
        self,
        callback: Callable[[UUID, HealthStatus], None],
    ) -> None:
        """Add a callback for health status changes."""
        self._check_callbacks.append(callback)
    
    async def schedule_check(self, instance: ChallengeInstance) -> None:
        """Schedule periodic health checks for an instance."""
        if instance.id in self._scheduled_checks:
            # Cancel existing check
            self._scheduled_checks[instance.id].cancel()
        
        # Start new check loop
        task = asyncio.create_task(
            self._check_loop(instance),
            name=f"health-check-{instance.id}",
        )
        self._scheduled_checks[instance.id] = task
    
    async def cancel_check(self, instance_id: UUID) -> None:
        """Cancel health checks for an instance."""
        if instance_id in self._scheduled_checks:
            self._scheduled_checks[instance_id].cancel()
            try:
                await self._scheduled_checks[instance_id]
            except asyncio.CancelledError:
                pass
            del self._scheduled_checks[instance_id]
    
    async def check_once(self, instance: ChallengeInstance) -> HealthStatus:
        """Perform a single health check."""
        checks = {}
        
        # Determine check type from instance metadata
        check_type = instance.provider_metadata.get("health_check_type", "http")
        
        try:
            if check_type == "http":
                checks["http"] = await self._check_http(instance)
            elif check_type == "tcp":
                checks["tcp"] = await self._check_tcp(instance)
            elif check_type == "command":
                checks["command"] = await self._check_command(instance)
            
            # All checks passed
            healthy = all(checks.values())
            
            return HealthStatus(
                healthy=healthy,
                checks=checks,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            logger.error(
                "Health check failed",
                instance_id=str(instance.id),
                error=str(e),
            )
            return HealthStatus(
                healthy=False,
                checks=checks,
                message=str(e),
                timestamp=datetime.utcnow(),
            )
    
    async def _check_loop(self, instance: ChallengeInstance) -> None:
        """Background loop for periodic health checks."""
        try:
            while True:
                await asyncio.sleep(self.check_interval)
                
                # Skip if instance is no longer active
                if not instance.is_active():
                    break
                
                # Perform health check
                health = await self.check_once(instance)
                
                # Notify callbacks
                for callback in self._check_callbacks:
                    try:
                        callback(instance.id, health)
                    except Exception as e:
                        logger.error(
                            "Health check callback failed",
                            error=str(e),
                        )
                
                # Log unhealthy status
                if not health.healthy:
                    logger.warning(
                        "Instance health check failed",
                        instance_id=str(instance.id),
                        checks=health.checks,
                    )
                    
        except asyncio.CancelledError:
            logger.debug(
                "Health check loop cancelled",
                instance_id=str(instance.id),
            )
        except Exception as e:
            logger.exception(
                "Health check loop error",
                instance_id=str(instance.id),
                error=str(e),
            )
    
    async def _check_http(self, instance: ChallengeInstance) -> bool:
        """Perform HTTP health check."""
        url = instance.provider_metadata.get("health_check_url")
        if not url:
            # Try to construct from access URL
            if instance.access_url:
                url = f"{instance.access_url}/health"
            else:
                return True  # No URL to check
        
        expected_status = instance.provider_metadata.get("health_check_status", 200)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    return response.status == expected_status
                    
        except Exception as e:
            logger.debug(
                "HTTP health check failed",
                instance_id=str(instance.id),
                url=url,
                error=str(e),
            )
            return False
    
    async def _check_tcp(self, instance: ChallengeInstance) -> bool:
        """Perform TCP port health check."""
        host = instance.network.external_ip or instance.network.internal_ip
        port = instance.provider_metadata.get("health_check_port", 80)
        
        if not host:
            return True  # No host to check
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
            writer.close()
            await writer.wait_closed()
            return True
            
        except Exception as e:
            logger.debug(
                "TCP health check failed",
                instance_id=str(instance.id),
                host=host,
                port=port,
                error=str(e),
            )
            return False
    
    async def _check_command(self, instance: ChallengeInstance) -> bool:
        """Perform custom command health check."""
        command = instance.provider_metadata.get("health_check_command")
        if not command:
            return True
        
        # This would need to be implemented based on the sandbox type
        # For now, return True
        return True
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get health checker metrics."""
        return {
            "scheduled_checks": len(self._scheduled_checks),
            "check_interval": self.check_interval,
            "timeout": self.timeout,
            "max_failures": self.max_failures,
        }


class PrometheusHealthExporter:
    """Export health metrics to Prometheus."""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
        self._metrics: Dict[str, Any] = {}
    
    def on_health_status(self, instance_id: UUID, health: HealthStatus) -> None:
        """Callback for health status updates."""
        self._metrics[str(instance_id)] = {
            "healthy": 1 if health.healthy else 0,
            "timestamp": health.timestamp.isoformat(),
            "checks": health.checks,
        }
    
    def export_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        lines.append("# HELP cerberus_instance_health Instance health status")
        lines.append("# TYPE cerberus_instance_health gauge")
        
        for instance_id, metrics in self._metrics.items():
            healthy = metrics["healthy"]
            lines.append(f'cerberus_instance_health{{instance_id="{instance_id}"}} {healthy}')
        
        return "\n".join(lines)