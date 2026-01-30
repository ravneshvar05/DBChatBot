"""
Database Connection Management.

This module handles PostgreSQL connection via SQLAlchemy.
It provides:
- Connection pooling
- Session management
- Health checks

Why SQLAlchemy:
1. Connection pooling out of the box
2. Database-agnostic (can switch DBs easily)
3. Secure parameterized queries
4. Transaction management
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import get_settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """
    Manages database connections and session lifecycle.
    
    This class provides a clean interface for database operations:
    - Connection pooling for efficiency
    - Context managers for safe session handling
    - Health checks for monitoring
    
    Example:
        >>> db = DatabaseConnection()
        >>> with db.get_session() as session:
        ...     result = session.execute(text("SELECT 1"))
    """
    
    def __init__(self, connection_url: str = None):
        """
        Initialize database engine with connection pooling.
        
        Args:
            connection_url: Optional connection URL. If not provided, uses settings.
        """
        self.settings = get_settings()
        
        # Use provided URL or fall back to settings
        db_url = connection_url or self.settings.database_url
        
        # Create engine with connection pool settings
        # pool_pre_ping: Test connections before using (handles stale connections)
        # pool_size: Number of connections to keep open
        # max_overflow: Additional connections allowed under load
        self.engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,  # Set True to log all SQL (very verbose)
        )
        
        # Session factory - creates new sessions
        self._session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info(f"Database connection initialized: {db_url.split('@')[-1] if '@' in db_url else 'default'}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup.
        
        Usage:
            with db.get_session() as session:
                result = session.execute(text("SELECT * FROM users"))
        
        The session is automatically closed when the context exits.
        Transactions are rolled back on error, committed on success.
        
        Yields:
            SQLAlchemy Session object
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error, rolling back: {e}")
            raise
        finally:
            session.close()
    
    def check_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            logger.debug("Database connection check: OK")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def close(self):
        """Close all connections in the pool."""
        self.engine.dispose()
        logger.info("Database connections closed")


# Module-level instance (singleton pattern)
_db_connection: DatabaseConnection | None = None


def get_database() -> DatabaseConnection:
    """
    Get or create the database connection instance.
    
    This lazy initialization prevents connection before app startup.
    
    Returns:
        DatabaseConnection singleton instance
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection
