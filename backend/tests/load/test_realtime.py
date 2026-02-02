"""
Load Tests for Real-Time Infrastructure

Uses Locust for load testing WebSocket and SSE endpoints.
Run with: locust -f tests/load/test_realtime.py --host=http://localhost:8000

Artillery.io config also available in tests/load/artillery.yml
"""

import asyncio
import json
import random
import string
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog
from locust import HttpUser, between, events, task
from locust.runners import MasterRunner

logger = structlog.get_logger(__name__)


# ============================================================================
# Locust Load Tests
# ============================================================================


class WebSocketUser(HttpUser):
    """
    Simulates a real-time WebSocket client.
    
    Behaviors:
    - Connect and authenticate
    - Subscribe to rooms
    - Send periodic heartbeats
    - Receive broadcasts
    """
    
    wait_time = between(1, 5)
    
    def on_start(self):
        """Initialize user session."""
        self.user_id = str(uuid4())
        self.username = f"loadtest_{self.user_id[:8]}"
        self.team_id = str(uuid4())
        self.token = None
        self.connected = False
        self.messages_received = 0
        self.last_heartbeat = time.time()
    
    @task(1)
    def connect_and_subscribe(self):
        """Connect and subscribe to rooms."""
        try:
            # Generate JWT token (simplified for load testing)
            self.token = self._generate_token()
            
            # Connect to WebSocket
            with self.client.websocket_connect(
                f"/api/v1/ws?token={self.token}&rooms=global,leaderboard"
            ) as ws:
                self.connected = True
                
                # Subscribe to additional rooms
                ws.send_json({
                    "type": "subscribe",
                    "channels": ["notifications", f"team:{self.team_id}"],
                })
                
                # Listen for messages for a short time
                for _ in range(10):
                    try:
                        msg = ws.receive_json(timeout=5)
                        self.messages_received += 1
                    except Exception:
                        break
                
                # Send heartbeat
                ws.send_json({"type": "ping"})
                
                # Wait a bit
                time.sleep(random.uniform(2, 5))
                
        except Exception as e:
            logger.debug("Connection failed", error=str(e))
    
    def _generate_token(self) -> str:
        """Generate a simplified JWT token for testing."""
        # In production, use proper JWT library
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        payload = {
            "sub": self.user_id,
            "username": self.username,
            "role": "player",
            "team_id": self.team_id,
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "type": "access",
        }
        payload_b64 = __import__("base64").b64encode(
            json.dumps(payload).encode()
        ).decode()
        signature = "fake_signature_for_load_test"
        return f"{header}.{payload_b64}.{signature}"


class SSEUser(HttpUser):
    """
    Simulates an SSE client for one-way broadcasts.
    """
    
    wait_time = between(5, 15)
    
    def on_start(self):
        """Initialize session."""
        self.user_id = str(uuid4())
        self.anonymous = random.random() > 0.5
    
    @task(1)
    def subscribe_leaderboard(self):
        """Subscribe to leaderboard SSE stream."""
        try:
            with self.client.get(
                f"/api/v1/events/leaderboard?anonymous={self.anonymous}",
                stream=True,
            ) as response:
                # Read for a short time
                start = time.time()
                bytes_received = 0
                
                for _ in range(50):  # Read up to 50 lines
                    if time.time() - start > 10:
                        break
                    
                    line = response.iter_lines(decode_unicode=True)
                    try:
                        next(line)  # Skip data line
                        event_line = next(line)
                        if event_line.startswith("event:"):
                            bytes_received += len(event_line)
                    except StopIteration:
                        break
                
                logger.debug(
                    "SSE stream received",
                    user_id=self.user_id,
                    bytes=bytes_received,
                )
                
        except Exception as e:
            logger.debug("SSE subscription failed", error=str(e))


class AdminUser(HttpUser):
    """
    Simulates an admin monitoring the dashboard.
    """
    
    wait_time = between(10, 30)
    
    def on_start(self):
        """Initialize admin session."""
        self.admin_id = str(uuid4())
        self.admin_token = self._generate_admin_token()
    
    @task(1)
    def monitor_admin_dashboard(self):
        """Connect to admin WebSocket and receive stats."""
        try:
            with self.client.websocket_connect(
                f"/api/v1/ws/admin?token={self.admin_token}"
            ) as ws:
                # Wait for messages
                for _ in range(5):
                    try:
                        msg = ws.receive_json(timeout=10)
                        logger.debug(
                            "Admin received event",
                            type=msg.get("type"),
                        )
                    except Exception:
                        break
                        
        except Exception as e:
            logger.debug("Admin connection failed", error=str(e))
    
    @task(1)
    def get_websocket_stats(self):
        """Fetch WebSocket stats via HTTP."""
        try:
            response = self.client.get("/api/v1/ws/stats")
            if response.status_code == 200:
                logger.debug("Stats fetched", data=response.json())
        except Exception as e:
            logger.debug("Stats fetch failed", error=str(e))
    
    def _generate_admin_token(self) -> str:
        """Generate admin JWT token."""
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        payload = {
            "sub": self.admin_id,
            "username": "loadtest_admin",
            "role": "admin",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "type": "access",
        }
        payload_b64 = __import__("base64").b64encode(
            json.dumps(payload).encode()
        ).decode()
        signature = "fake_admin_signature"
        return f"{header}.{payload_b64}.{signature}"


# ============================================================================
# Artillery.io Load Test Configuration
# ============================================================================

ARTILLERY_CONFIG = """
config:
  target: "http://localhost:8000"
  phases:
    - duration: 60
      arrivalRate: 10
      name: "Warm up"
    - duration: 300
      arrivalRate: 50
      rampTo: 200
      name: "Ramp up load"
    - duration: 600
      arrivalRate: 200
      name: "Sustained load"
    - duration: 120
      arrivalRate: 100
      rampTo: 0
      name: "Cool down"
  
  processor: "./processors.js"

scenarios:
  - name: "WebSocket connection and subscription"
    weight: 60
    engine: "socketio"
    flow:
      - emit:
          channel: "auth"
          data:
            token: "{{ token }}"
      - think: 2
      - emit:
          channel: "subscribe"
          data:
            channels: ["global", "leaderboard"]
      - loop:
          count: 10
          flow:
            - think:
                min: 1
                max: 3
            - emit:
                channel: "ping"
      - emit:
          channel: "disconnect"

  - name: "SSE subscription"
    weight: 30
    engine: "http"
    flow:
      - get:
          url: "/api/v1/events/leaderboard"
          capture:
            - json: "$.type"
            as: "event_type"
      - think:
          min: 5
          max: 15

  - name: "Admin monitoring"
    weight: 10
    engine: "socketio"
    flow:
      - emit:
          channel: "auth"
          data:
            token: "{{ admin_token }}"
      - think: 2
      - emit:
          channel: "subscribe"
          data:
            channels: ["admin", "global"]
      - loop:
          count: 5
          flow:
            - think:
                min: 5
                max: 10
            - emit:
                channel: "ping"

  - name: "Notification delivery"
    weight: 20
    engine: "socketio"
    flow:
      - emit:
          channel: "auth"
          data:
            token: "{{ token }}"
      - think: 1
      - emit:
          channel: "subscribe"
          data:
            channels: ["notifications"]
      - think:
          min: 10
          max: 30

  - name: "AD game updates"
    weight: 15
    engine: "socketio"
    flow:
      - emit:
          channel: "auth"
          data:
            token: "{{ token }}"
      - think: 1
      - emit:
          channel: "subscribe"
          data:
            channels: ["ad:{{ game_id }}", "global"]
      - loop:
          count: 20
          flow:
            - think:
                min: 5
                max: 15
            - emit:
                channel: "ping"

# Processor functions for dynamic data
processors:
  functions:
    generateToken:
      - function: "generateToken"
        inline: |
          module.exports = function(context, callback) {
            const token = Buffer.from(JSON.stringify({
              sub: context.vars.userId || 'test-user',
              username: 'loadtest-' + Math.random().toString(36).substring(7),
              role: 'player',
              team_id: context.vars.teamId || 'test-team',
              exp: Date.now() + 3600000,
              iat: Date.now()
            })).toString('base64');
            context.vars.token = token;
            callback(null, context);
          }
"""


# ============================================================================
# Async Load Test Utilities
# ============================================================================


class AsyncLoadTester:
    """
    Async load tester for WebSocket infrastructure.
    
    Can be used with asyncio and aiohttp for more control.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        num_users: int = 100,
        duration_seconds: int = 300,
    ):
        self.base_url = base_url
        self.num_users = num_users
        self.duration_seconds = duration_seconds
        self.results: List[Dict[str, Any]] = []
        self._running = False
    
    async def run_load_test(self) -> Dict[str, Any]:
        """Run the load test."""
        import aiohttp
        import asyncio
        import websockets
        
        self._running = True
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            # Create concurrent users
            for i in range(self.num_users):
                task = self._simulate_user(session, i)
                tasks.append(asyncio.create_task(task))
            
            # Wait for completion or timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks),
                    timeout=self.duration_seconds,
                )
            except asyncio.TimeoutError:
                logger.info("Load test timed out")
            
            end_time = time.time()
            
            return {
                "duration_seconds": end_time - start_time,
                "num_users": self.num_users,
                "results": self.results,
            }
    
    async def _simulate_user(
        self,
        session: aiohttp.ClientSession,
        user_index: int,
    ) -> Dict[str, Any]:
        """Simulate a single user."""
        user_id = str(uuid4())
        username = f"async_loadtest_{user_index}"
        
        result = {
            "user_id": user_id,
            "connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "duration": 0,
        }
        
        start = time.time()
        
        try:
            # Connect to WebSocket
            async with websockets.connect(
                f"{self.base_url.replace('http', 'ws')}/api/v1/ws",
            ) as websocket:
                result["connections"] += 1
                
                # Authenticate
                await websocket.send(json.dumps({
                    "type": "subscribe",
                    "channels": ["global", "leaderboard"],
                }))
                result["messages_sent"] += 1
                
                # Listen for messages
                listen_task = asyncio.create_task(
                    self._listen_messages(websocket, result)
                )
                
                # Send periodic messages
                for _ in range(5):
                    await asyncio.sleep(random.uniform(1, 3))
                    
                    if not self._running:
                        break
                    
                    await websocket.send(json.dumps({
                        "type": "ping",
                    }))
                    result["messages_sent"] += 1
                
                # Stop listening
                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            result["errors"] += 1
            logger.debug("User simulation error", error=str(e))
        
        result["duration"] = time.time() - start
        self.results.append(result)
        
        return result
    
    async def _listen_messages(
        self,
        websocket: Any,
        result: Dict[str, Any],
    ) -> None:
        """Listen for incoming messages."""
        try:
            async for message in websocket:
                data = json.loads(message)
                result["messages_received"] += 1
                
                # Stop after receiving many messages
                if result["messages_received"] >= 100:
                    break
                    
        except Exception:
            pass
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        if not self.results:
            return {}
        
        total_connections = sum(r["connections"] for r in self.results)
        total_sent = sum(r["messages_sent"] for r in self.results)
        total_received = sum(r["messages_received"] for r in self.results)
        total_errors = sum(r["errors"] for r in self.results)
        
        return {
            "total_connections": total_connections,
            "total_messages_sent": total_sent,
            "total_messages_received": total_received,
            "total_errors": total_errors,
            "avg_messages_per_connection": total_sent / max(1, total_connections),
            "success_rate": (total_connections - total_errors) / max(1, total_connections) * 100,
        }


# ============================================================================
# Performance Benchmarks
# ============================================================================


async def benchmark_message_throughput():
    """
    Benchmark WebSocket message throughput.
    
    Measures:
    - Messages per second
    - Latency percentiles
    - Connection overhead
    """
    from app.infrastructure.orchestrator.realtime.server import (
        EventMessage,
        EventType,
        RealtimeServer,
    )
    from app.infrastructure.orchestrator.realtime.middleware.auth import WSAuthMiddleware
    
    # Create server
    server = RealtimeServer()
    
    # Create test data
    leaderboard_entries = []
    for i in range(100):
        leaderboard_entries.append({
            "position": i + 1,
            "team_id": str(uuid4()),
            "team_name": f"Team {i}",
            "score": random.randint(100, 10000),
            "solves_count": random.randint(0, 50),
        })
    
    # Benchmark leaderboard broadcast
    event = EventMessage(
        type=EventType.LEADERBOARD_UPDATE.value,
        data={"entries": leaderboard_entries},
    )
    
    # Run benchmark
    iterations = 100
    start = time.time()
    
    for _ in range(iterations):
        # Simulate broadcast (without actual connections)
        pass
    
    elapsed = time.time() - start
    throughput = iterations / elapsed
    
    logger.info(
        "Throughput benchmark",
        iterations=iterations,
        elapsed_seconds=elapsed,
        throughput_per_second=throughput,
    )
    
    return {
        "iterations": iterations,
        "elapsed_seconds": elapsed,
        "throughput_per_second": throughput,
    }


# ============================================================================
# Events for Locust
# ============================================================================


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize locust environment."""
    logger.info("Load test initialized", environment=environment)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    logger.info("Load test started")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    logger.info("Load test stopped")
    
    # Print summary
    if isinstance(environment.runner, MasterRunner):
        stats = environment.runner.stats
        logger.info(
            "Test statistics",
            total_requests=stats.total.num_requests,
            total_failures=stats.total.num_failures,
            avg_response_time=stats.total.avg_response_time,
        )


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Called when test is quitting."""
    logger.info("Load test finishing")


# ============================================================================
# Main Entry Point
# ============================================================================


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run load tests")
    parser.add_argument(
        "--type",
        choices=["locust", "artillery", "async"],
        default="locust",
        help="Load test type",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Target URL",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=100,
        help="Number of concurrent users",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Test duration in seconds",
    )
    
    args = parser.parse_args()
    
    if args.type == "locust":
        print("Run with: locust -f tests/load/test_realtime.py --host=" + args.url)
    elif args.type == "async":
        import asyncio
        
        tester = AsyncLoadTester(
            base_url=args.url,
            num_users=args.users,
            duration_seconds=args.duration,
        )
        
        results = asyncio.run(tester.run_load_test())
        print(json.dumps(tester.get_summary(), indent=2))
    else:
        print(f"Artillery config:\n{ARTILLERY_CONFIG}")
        print(f"Run with: artillery run config.yml --output report.json")
