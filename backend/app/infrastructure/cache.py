"""
Cerberus CTF Platform - Cache Infrastructure
Redis client with connection pooling and circuit breaker
"""

import json
from typing import Any, Optional

import structlog
from pybreaker import CircuitBreaker, CircuitBreakerError
from redis.asyncio import Redis, ConnectionPool

from app.core.config import Settings

logger = structlog.get_logger(__name__)


# Circuit breaker for Redis operations
redis_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    exclude=[ConnectionError],
)


class CacheManager:
    """
    Redis cache manager with circuit breaker pattern.
    
    Provides resilient caching with automatic fallback on failures.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize cache manager.
        
        Args:
            settings: Application settings
        """
        self._settings = settings
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
    
    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        logger.info(
            "Connecting to Redis",
            host=str(self._settings.redis_url).split("@")[-1],
        )
        
        self._pool = ConnectionPool.from_url(
            str(self._settings.redis_url),
            password=self._settings.redis_password or None,
            max_connections=self._settings.redis_pool_size,
            decode_responses=True,
        )
        
        self._client = Redis(connection_pool=self._pool)
        
        # Test connection
        await self._client.ping()
        
        logger.info("Redis connection established")
    
    async def disconnect(self) -> None:
        """Close Redis connection pool."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis connection closed")
    
    @property
    def client(self) -> Redis:
        """Get Redis client."""
        if self._client is None:
            raise RuntimeError("Cache not connected")
        return self._client
    
    @redis_breaker
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        try:
            return await self.client.get(key)
        except CircuitBreakerError:
            logger.warning("Redis circuit breaker open", key=key)
            return None
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    @redis_breaker
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            await self.client.set(key, value, ex=ttl)
            return True
        except CircuitBreakerError:
            logger.warning("Redis circuit breaker open", key=key)
            return False
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False
    
    @redis_breaker
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted
        """
        try:
            result = await self.client.delete(key)
            return result > 0
        except CircuitBreakerError:
            logger.warning("Redis circuit breaker open", key=key)
            return False
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False
    
    @redis_breaker
    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get a JSON value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Deserialized JSON value or None
        """
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in cache", key=key)
            return None
    
    @redis_breaker
    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set a JSON value in cache.
        
        Args:
            key: Cache key
            value: Value to serialize and cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            serialized = json.dumps(value)
            return await self.set(key, serialized, ttl)
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization error", key=key, error=str(e))
            return False
    
    @redis_breaker
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a counter.
        
        Args:
            key: Cache key
            amount: Amount to increment
            
        Returns:
            New value or None on error
        """
        try:
            return await self.client.incrby(key, amount)
        except CircuitBreakerError:
            logger.warning("Redis circuit breaker open", key=key)
            return None
        except Exception as e:
            logger.error("Redis incr error", key=key, error=str(e))
            return None
    
    @redis_breaker
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration on a key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            return await self.client.expire(key, ttl)
        except CircuitBreakerError:
            logger.warning("Redis circuit breaker open", key=key)
            return False
        except Exception as e:
            logger.error("Redis expire error", key=key, error=str(e))
            return False
    
    async def health_check(self) -> dict:
        """
        Check Redis health.
        
        Returns:
            Health status dictionary
        """
        try:
            await self.client.ping()
            info = await self.client.info("memory")
            
            return {
                "status": "healthy",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }


class SessionStore:
    """
    Session storage using Redis.
    
    Provides secure session management with automatic expiration.
    """
    
    def __init__(self, cache: CacheManager, prefix: str = "session:"):
        """
        Initialize session store.
        
        Args:
            cache: Cache manager instance
            prefix: Key prefix for sessions
        """
        self._cache = cache
        self._prefix = prefix
    
    def _key(self, session_id: str) -> str:
        """Generate session key."""
        return f"{self._prefix}{session_id}"
    
    async def create(
        self,
        session_id: str,
        data: dict,
        ttl: int = 3600,
    ) -> bool:
        """
        Create a new session.
        
        Args:
            session_id: Session identifier
            data: Session data
            ttl: Session lifetime in seconds
            
        Returns:
            True if successful
        """
        return await self._cache.set_json(self._key(session_id), data, ttl)
    
    async def get(self, session_id: str) -> Optional[dict]:
        """
        Get session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None
        """
        return await self._cache.get_json(self._key(session_id))
    
    async def update(
        self,
        session_id: str,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session identifier
            data: New session data
            ttl: Optional new TTL
            
        Returns:
            True if successful
        """
        return await self._cache.set_json(self._key(session_id), data, ttl)
    
    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted
        """
        return await self._cache.delete(self._key(session_id))
    
    async def extend(self, session_id: str, ttl: int) -> bool:
        """
        Extend session lifetime.
        
        Args:
            session_id: Session identifier
            ttl: New TTL in seconds
            
        Returns:
            True if successful
        """
        return await self._cache.expire(self._key(session_id), ttl)
