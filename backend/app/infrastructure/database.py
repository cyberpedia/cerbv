"""
Cerberus CTF Platform - Database Infrastructure
Async SQLAlchemy 2.0 with connection pooling and Unit of Work pattern
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


class DatabaseManager:
    """
    Database connection manager with async support.
    
    Handles connection pooling, session management, and health checks.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize database manager.
        
        Args:
            settings: Application settings
        """
        self._settings = settings
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def connect(self) -> None:
        """Initialize database connection pool."""
        logger.info(
            "Connecting to database",
            host=str(self._settings.database_url).split("@")[-1].split("/")[0],
        )
        
        self._engine = create_async_engine(
            str(self._settings.database_url),
            pool_size=self._settings.database_pool_size,
            max_overflow=self._settings.database_max_overflow,
            pool_timeout=self._settings.database_pool_timeout,
            pool_pre_ping=True,
            echo=self._settings.database_echo,
        )
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        
        # Test connection
        async with self._engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("Database connection established")
    
    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connection closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.
        
        Yields:
            AsyncSession for database operations
        """
        if self._session_factory is None:
            raise RuntimeError("Database not connected")
        
        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> dict:
        """
        Check database health.
        
        Returns:
            Health status dictionary
        """
        try:
            async with self.session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            
            return {
                "status": "healthy",
                "pool_size": self._engine.pool.size() if self._engine else 0,
                "checked_out": self._engine.pool.checkedout() if self._engine else 0,
            }
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
            }


class UnitOfWork:
    """
    Unit of Work pattern implementation.
    
    Manages transactions across multiple repositories.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize unit of work.
        
        Args:
            session: Database session
        """
        self._session = session
        self._committed = False
    
    @property
    def session(self) -> AsyncSession:
        """Get the underlying session."""
        return self._session
    
    async def commit(self) -> None:
        """Commit the transaction."""
        await self._session.commit()
        self._committed = True
    
    async def rollback(self) -> None:
        """Rollback the transaction."""
        await self._session.rollback()
    
    async def flush(self) -> None:
        """Flush pending changes without committing."""
        await self._session.flush()
    
    async def refresh(self, instance: object) -> None:
        """Refresh an instance from the database."""
        await self._session.refresh(instance)
    
    async def __aenter__(self) -> "UnitOfWork":
        """Enter context manager."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager with automatic rollback on error."""
        if exc_type is not None:
            await self.rollback()
        elif not self._committed:
            await self.rollback()


# Dependency injection helper
async def get_db_session(
    db_manager: DatabaseManager,
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Args:
        db_manager: Database manager instance
        
    Yields:
        Database session
    """
    async with db_manager.session() as session:
        yield session


async def get_unit_of_work(
    session: AsyncSession,
) -> AsyncGenerator[UnitOfWork, None]:
    """
    FastAPI dependency for unit of work.
    
    Args:
        session: Database session
        
    Yields:
        Unit of work instance
    """
    async with UnitOfWork(session) as uow:
        yield uow
