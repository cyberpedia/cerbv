"""
Hardware Lab Manager Service

Manages remote access to physical hardware equipment:
- Oscilloscopes, Logic Analyzers, SDR devices
- Session booking and queue management
- Video streaming (WebRTC) for hardware workbench view
- Equipment reset and safety controls

Features:
- 2-hour session slots with auto-kick on 15min idle
- USB/IP for remote device access
- SoapySDR integration for SDR devices
- Safety limits (voltage, current)
- Watchdog relay for emergency power cut
"""

import asyncio
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import structlog

from app.infrastructure.cache import CacheManager
from app.infrastructure.database import DatabaseManager

from ..models_advanced import (
    EquipmentType,
    HardwareConfig,
    HardwareEquipment,
    HardwareSession,
    HardwareStatus,
)

logger = structlog.get_logger(__name__)


class EquipmentController:
    """Controls physical hardware equipment."""
    
    def __init__(self, equipment: HardwareEquipment):
        self.equipment = equipment
        self._connected = False
    
    async def connect(self) -> bool:
        """Establish connection to hardware."""
        try:
            # USB/IP connection for USB devices
            if self.equipment.connection_string.startswith("usbip:"):
                device = self.equipment.connection_string[6:]  # Remove "usbip:"
                result = await self._run_command([
                    "usbip", "attach", "--remote=localhost", f"--busid={device}"
                ])
                if result.returncode == 0:
                    self._connected = True
                    return True
            
            # Network connection for network devices
            elif self.equipment.connection_string.startswith("tcp://"):
                # Just mark as connected - actual connection handled by client
                self._connected = True
                return True
            
            return False
            
        except Exception as e:
            logger.exception("Failed to connect to equipment", error=str(e))
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from hardware."""
        try:
            if self.equipment.connection_string.startswith("usbip:"):
                device = self.equipment.connection_string[6:]
                await self._run_command([
                    "usbip", "detach", f"--port=0", f"--busid={device}"
                ])
            
            self._connected = False
            return True
            
        except Exception as e:
            logger.exception("Failed to disconnect equipment", error=str(e))
            return False
    
    async def reset(self) -> bool:
        """
        Reset equipment to clean state.
        - Reflash firmware
        - Clear EEPROM
        - Reset USB state
        """
        try:
            # Run reset script if configured
            if self.equipment.maintenance_mode:
                logger.info(
                    "Equipment in maintenance mode, skipping reset",
                    equipment_id=str(self.equipment.id),
                )
                return False
            
            # In production, execute actual reset procedure
            logger.info(
                "Resetting equipment",
                equipment_id=str(self.equipment.id),
                name=self.equipment.name,
            )
            
            return True
            
        except Exception as e:
            logger.exception("Failed to reset equipment", error=str(e))
            return False
    
    async def get_status(self) -> Dict:
        """Get current equipment status."""
        return {
            "connected": self._connected,
            "status": self.equipment.status.value,
            "capabilities": self.equipment.capabilities,
        }
    
    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run a shell command."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        )


class SDRController(EquipmentController):
    """Controller for Software Defined Radio devices."""
    
    SUPPORTED_DEVICES = {
        "hackrf": "HackRF One",
        "bladerf": "BladeRF",
        "rtl_sdr": "RTL-SDR",
        "usrp": "USRP",
    }
    
    async def configure(
        self,
        center_freq: float = 100e6,
        sample_rate: float = 2e6,
        gain: int = 40,
    ) -> bool:
        """Configure SDR parameters."""
        try:
            # In production, use SoapySDR API
            # from soapysdr import Device
            # dev = Device("driver=hackrf")
            # dev.set("center_freq", center_freq)
            
            logger.info(
                "Configuring SDR",
                equipment_id=str(self.equipment.id),
                center_freq_hz=center_freq,
                sample_rate_hz=sample_rate,
                gain_db=gain,
            )
            
            return True
            
        except Exception as e:
            logger.exception("SDR configuration failed", error=str(e))
            return False
    
    async def get_power_spectrum(
        self,
        start_freq: float,
        end_freq: float,
        points: int = 1024,
    ) -> List[float]:
        """Get power spectrum data."""
        # In production, capture and process IQ samples
        return []


class VideoStreamManager:
    """Manages WebRTC video streams for hardware workbench view."""
    
    def __init__(self):
        self._streams: Dict[UUID, Dict] = {}
    
    async def create_stream(
        self,
        equipment_id: UUID,
        user_id: UUID,
    ) -> str:
        """
        Create a new video stream for equipment.
        
        Returns:
            WebRTC stream URL
        """
        stream_id = uuid4()
        
        # In production, this would:
        # 1. Spawn a WebRTC signaling server
        # 2. Connect to camera attached to workbench
        # 3. Return stream URL
        
        stream_url = f"webrtc://stream/{stream_id}"
        
        self._streams[stream_id] = {
            "equipment_id": equipment_id,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "url": stream_url,
            "active": True,
        }
        
        logger.info(
            "Created video stream",
            stream_id=str(stream_id),
            equipment_id=str(equipment_id),
        )
        
        return stream_url
    
    async def end_stream(self, stream_id: UUID) -> bool:
        """End a video stream."""
        if stream_id in self._streams:
            self._streams[stream_id]["active"] = False
            logger.info("Ended video stream", stream_id=str(stream_id))
            return True
        return False
    
    def get_stream_info(self, stream_id: UUID) -> Optional[Dict]:
        """Get stream information."""
        return self._streams.get(stream_id)


class SafetyMonitor:
    """Monitors and enforces safety limits for hardware sessions."""
    
    def __init__(self, safety_limits: Dict[str, float]):
        self.safety_limits = safety_limits
        self._watchdog_relay_enabled = True
    
    async def check_limits(
        self,
        voltage: float,
        current: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if measurements are within safety limits.
        
        Returns:
            Tuple of (within_limits, warning_message)
        """
        max_voltage = self.safety_limits.get("max_voltage", 5.0)
        max_current = self.safety_limits.get("max_current_ma", 500.0)
        
        if voltage > max_voltage:
            await self._cut_power()
            return False, f"Voltage {voltage}V exceeds limit {max_voltage}V"
        
        if current > max_current:
            await self._cut_power()
            return False, f"Current {current}mA exceeds limit {max_current}mA"
        
        return True, None
    
    async def _cut_power(self) -> None:
        """Cut power via watchdog relay."""
        if self._watchdog_relay_enabled:
            logger.warning("SAFETY: Cutting power via watchdog relay")
            # In production, toggle GPIO pin controlling relay
    
    async def start_watchdog(self, session: HardwareSession) -> None:
        """Start watchdog timer for session."""
        idle_timeout = 900  # 15 minutes in seconds
        
        while session.is_active():
            await asyncio.sleep(60)  # Check every minute
            
            if session.is_idle(idle_timeout):
                logger.info(
                    "Session idle, cutting power",
                    session_id=str(session.id),
                )
                await self._cut_power()
                break


# ============================================================================
# Hardware Lab Manager
# ============================================================================

class HardwareLabManager:
    """
    Main hardware lab manager.
    
    Handles:
    - Equipment registration and status tracking
    - Session booking and queue management
    - Session lifecycle (start, extend, end, auto-kick)
    - Video streaming
    - Safety monitoring
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_manager: CacheManager,
        config: Optional[HardwareConfig] = None,
    ):
        self.db = db_manager
        self.cache = cache_manager
        self.config = config or HardwareConfig()
        
        # Equipment management
        self._equipment: Dict[UUID, HardwareEquipment] = {}
        self._equipment_controllers: Dict[UUID, EquipmentController] = {}
        
        # Session management
        self._sessions: Dict[UUID, HardwareSession] = {}
        self._session_locks: Dict[UUID, asyncio.Lock] = {}
        
        # Queue management
        self._reservation_queue: Dict[UUID, List[Dict]] = {}  # equipment_id -> queue
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Video streaming
        self.stream_manager = VideoStreamManager()
        
        # Safety monitor
        self.safety_monitor = SafetyMonitor(self.config.safety_limits)
    
    async def start(self) -> None:
        """Start the hardware lab manager."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(
            "Hardware Lab Manager started",
            session_duration_minutes=self.config.session_duration_minutes,
            idle_timeout_seconds=self.config.idle_timeout_seconds,
        )
    
    async def stop(self) -> None:
        """Stop the hardware lab manager."""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # End all active sessions
        for session in list(self._sessions.values()):
            await self.end_session(session.id)
        
        logger.info("Hardware Lab Manager stopped")
    
    def _get_session_lock(self, session_id: UUID) -> asyncio.Lock:
        """Get or create a lock for a session."""
        if session_id not in self._session_locks:
            self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]
    
    # =========================================================================
    # Equipment Management
    # =========================================================================
    
    async def register_equipment(
        self,
        name: str,
        equipment_type: EquipmentType,
        connection_string: str,
        capabilities: Optional[List[str]] = None,
    ) -> HardwareEquipment:
        """
        Register new hardware equipment.
        
        Args:
            name: Human-readable name
            equipment_type: Type of equipment
            connection_string: USB/IP address or network URL
            capabilities: List of capabilities
            
        Returns:
            The registered equipment
        """
        equipment = HardwareEquipment(
            id=uuid4(),
            name=name,
            equipment_type=equipment_type,
            status=HardwareStatus.AVAILABLE,
            connection_string=connection_string,
            capabilities=capabilities or [],
        )
        
        self._equipment[equipment.id] = equipment
        
        # Create appropriate controller
        if equipment_type == EquipmentType.SDR:
            self._equipment_controllers[equipment.id] = SDRController(equipment)
        else:
            self._equipment_controllers[equipment.id] = EquipmentController(equipment)
        
        # Store in cache
        await self._store_equipment(equipment)
        
        logger.info(
            "Equipment registered",
            equipment_id=str(equipment.id),
            name=name,
            equipment_type=equipment_type.value,
        )
        
        return equipment
    
    async def get_equipment(self, equipment_id: UUID) -> Optional[HardwareEquipment]:
        """Get equipment by ID."""
        return self._equipment.get(equipment_id)
    
    async def list_available_equipment(
        self,
        equipment_type: Optional[EquipmentType] = None,
    ) -> List[HardwareEquipment]:
        """
        List available equipment.
        
        Args:
            equipment_type: Optional filter by type
            
        Returns:
            List of available equipment
        """
        equipment = [
            eq for eq in self._equipment.values()
            if eq.status == HardwareStatus.AVAILABLE
            and not eq.maintenance_mode
        ]
        
        if equipment_type:
            equipment = [eq for eq in equipment if eq.equipment_type == equipment_type]
        
        return equipment
    
    async def set_equipment_status(
        self,
        equipment_id: UUID,
        status: HardwareStatus,
    ) -> bool:
        """Set equipment status."""
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            return False
        
        equipment.status = status
        await self._store_equipment(equipment)
        
        await self._emit_event("hardware.status_changed", {
            "equipment_id": str(equipment_id),
            "status": status.value,
        })
        
        return True
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    async def reserve_equipment(
        self,
        equipment_id: UUID,
        user_id: UUID,
        team_id: Optional[UUID] = None,
    ) -> HardwareSession:
        """
        Reserve equipment for a user.
        
        Args:
            equipment_id: Equipment to reserve
            user_id: User making reservation
            team_id: Optional team ID
            
        Returns:
            The reservation session
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            raise ValueError("Equipment not found")
        
        if equipment.status == HardwareStatus.MAINTENANCE:
            raise ValueError("Equipment is under maintenance")
        
        # Check for existing session
        existing = await self._get_user_active_session(user_id, equipment_id)
        if existing:
            raise ValueError("Already have an active session for this equipment")
        
        # Check concurrent session limit
        concurrent = await self._get_user_concurrent_sessions(user_id)
        if concurrent >= self.config.max_concurrent_sessions_per_user:
            raise ValueError("Maximum concurrent sessions reached")
        
        # Check queue or create reservation
        session = HardwareSession(
            id=uuid4(),
            equipment_id=equipment_id,
            user_id=user_id,
            team_id=team_id,
            start_time=datetime.utcnow(),
            reserved_end_time=datetime.utcnow() + timedelta(
                minutes=self.config.session_duration_minutes
            ),
            status=HardwareStatus.RESERVED,
        )
        
        async with self._get_session_lock(session.id):
            self._sessions[session.id] = session
            
            # Update equipment status
            equipment.status = HardwareStatus.RESERVED
            equipment.current_session_id = session.id
            await self._store_equipment(equipment)
            
            # Store session
            await self._store_session(session)
        
        logger.info(
            "Equipment reserved",
            session_id=str(session.id),
            equipment_id=str(equipment_id),
            user_id=str(user_id),
        )
        
        return session
    
    async def grant_session_access(
        self,
        session_id: UUID,
    ) -> Dict:
        """
        Grant access to a reserved session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dict with access details (stream URL, connection info)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")
        
        if session.status != HardwareStatus.RESERVED:
            raise ValueError("Session not in reserved state")
        
        equipment = self._equipment.get(session.equipment_id)
        if not equipment:
            raise ValueError("Equipment not found")
        
        async with self._get_session_lock(session_id):
            # Connect to equipment
            controller = self._equipment_controllers.get(equipment.id)
            if controller:
                await controller.connect()
            
            # Create video stream
            stream_url = await self.stream_manager.create_stream(
                equipment.id, session.user_id
            )
            
            # Update session
            session.status = HardwareStatus.IN_USE
            session.start_time = datetime.utcnow()
            session.stream_url = stream_url
            session.access_granted = True
            session.last_heartbeat = datetime.utcnow()
            
            # Update equipment status
            equipment.status = HardwareStatus.IN_USE
            
            await self._store_session(session)
            await self._store_equipment(equipment)
            
            # Start safety watchdog
            asyncio.create_task(self.safety_monitor.start_watchdog(session))
        
        logger.info(
            "Session access granted",
            session_id=str(session_id),
            stream_url=stream_url,
        )
        
        return {
            "session_id": str(session_id),
            "stream_url": stream_url,
            "connection_string": equipment.connection_string,
            "capabilities": equipment.capabilities,
            "expires_at": session.reserved_end_time.isoformat(),
        }
    
    async def send_heartbeat(self, session_id: UUID) -> bool:
        """
        Update session heartbeat.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if heartbeat was recorded
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.last_heartbeat = datetime.utcnow()
        await self._store_session(session)
        
        return True
    
    async def extend_session(
        self,
        session_id: UUID,
        additional_minutes: int = 30,
    ) -> bool:
        """
        Extend a session's duration.
        
        Args:
            session_id: Session ID
            additional_minutes: Minutes to add
            
        Returns:
            True if extended successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        if session.status != HardwareStatus.IN_USE:
            return False
        
        # Check if equipment is available for extension
        equipment = self._equipment.get(session.equipment_id)
        if not equipment:
            return False
        
        # In production, check if next user in queue can be accommodated
        
        session.reserved_end_time += timedelta(minutes=additional_minutes)
        await self._store_session(session)
        
        logger.info(
            "Session extended",
            session_id=str(session_id),
            additional_minutes=additional_minutes,
        )
        
        return True
    
    async def end_session(self, session_id: UUID) -> bool:
        """
        End a hardware session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if ended successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        async with self._get_session_lock(session_id):
            equipment = self._equipment.get(session.equipment_id)
            
            # Disconnect from equipment
            if equipment:
                controller = self._equipment_controllers.get(equipment.id)
                if controller:
                    await controller.disconnect()
                
                # Reset equipment
                if controller:
                    await controller.reset()
                
                # Update equipment status
                equipment.status = HardwareStatus.AVAILABLE
                equipment.current_session_id = None
                await self._store_equipment(equipment)
            
            # End video stream
            if session.stream_url:
                # Extract stream ID from URL
                stream_id = UUID(session.stream_url.split("/")[-1])
                await self.stream_manager.end_stream(stream_id)
            
            # Update session
            session.status = HardwareStatus.AVAILABLE
            session.end_time = datetime.utcnow()
            await self._store_session(session)
        
        logger.info("Session ended", session_id=str(session_id))
        
        return True
    
    async def get_session(self, session_id: UUID) -> Optional[HardwareSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    async def list_user_sessions(
        self,
        user_id: UUID,
        active_only: bool = True,
    ) -> List[HardwareSession]:
        """List sessions for a user."""
        sessions = [
            s for s in self._sessions.values()
            if s.user_id == user_id
        ]
        
        if active_only:
            sessions = [s for s in sessions if s.is_active()]
        
        return sessions
    
    async def get_session_queue(self, equipment_id: UUID) -> List[Dict]:
        """Get the reservation queue for equipment."""
        queue = self._reservation_queue.get(equipment_id, [])
        return [
            {
                "user_id": str(item["user_id"]),
                "team_id": str(item["team_id"]) if item.get("team_id") else None,
                "queued_at": item["queued_at"].isoformat(),
            }
            for item in queue
        ]
    
    # =========================================================================
    # Background Tasks
    # =========================================================================
    
    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup expired and idle sessions."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                now = datetime.utcnow()
                
                for session in list(self._sessions.values()):
                    if not session.is_active():
                        continue
                    
                    # Check for expired sessions
                    if now >= session.reserved_end_time:
                        logger.info(
                            "Cleaning up expired session",
                            session_id=str(session.id),
                        )
                        await self.end_session(session.id)
                        continue
                    
                    # Check for idle sessions
                    if session.is_idle(self.config.idle_timeout_seconds):
                        logger.info(
                            "Cleaning up idle session",
                            session_id=str(session.id),
                        )
                        await self.end_session(session.id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup error", error=str(e))
    
    # =========================================================================
    # Storage Methods
    # =========================================================================
    
    async def _store_equipment(self, equipment: HardwareEquipment) -> None:
        """Store equipment in cache."""
        cache_key = f"hardware:equipment:{equipment.id}"
        await self.cache.set(cache_key, equipment.to_dict(), ttl=86400 * 30)
    
    async def _store_session(self, session: HardwareSession) -> None:
        """Store session in cache."""
        cache_key = f"hardware:session:{session.id}"
        await self.cache.set(cache_key, session.to_dict(), ttl=86400 * 7)
    
    async def _get_user_active_session(
        self,
        user_id: UUID,
        equipment_id: UUID,
    ) -> Optional[HardwareSession]:
        """Get user's active session for equipment."""
        for session in self._sessions.values():
            if (
                session.user_id == user_id
                and session.equipment_id == equipment_id
                and session.is_active()
            ):
                return session
        return None
    
    async def _get_user_concurrent_sessions(self, user_id: UUID) -> int:
        """Count user's concurrent active sessions."""
        count = 0
        for session in self._sessions.values():
            if session.user_id == user_id and session.is_active():
                count += 1
        return count
    
    async def _emit_event(self, event_type: str, data: Dict) -> None:
        """Emit a WebSocket event."""
        cache_key = f"ws:events:{event_type}"
        await self.cache.publish(cache_key, data)
