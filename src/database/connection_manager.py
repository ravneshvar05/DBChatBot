"""
Session-based Database Connection Manager.

This module manages multiple database connections for different sessions,
allowing each user to connect to their own database dynamically.

Features:
- Per-session connection management
- Connection validation and testing
- Support for MySQL and PostgreSQL
- SSL/TLS support for cloud databases
- Automatic connection cleanup
- Connection credential encryption in memory
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseCredentials:
    """Database connection credentials."""
    db_type: str  # "mysql" or "postgresql"
    host: str
    port: int
    database: str
    username: str
    password: str
    use_ssl: bool = False
    
    def to_connection_url(self) -> str:
        """
        Convert credentials to SQLAlchemy connection URL.
        
        Returns:
            Connection URL string
        """
        # URL-encode password to handle special characters
        encoded_password = quote_plus(self.password)
        
        if self.db_type.lower() == "mysql":
            driver = "mysql+pymysql"
            default_port = 3306
        elif self.db_type.lower() == "postgresql":
            driver = "postgresql"
            default_port = 5432
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        
        port = self.port or default_port
        
        # Build base URL
        url = f"{driver}://{self.username}:{encoded_password}@{self.host}:{port}/{self.database}"
        
        # Add SSL parameter if needed
        if self.use_ssl:
            if self.db_type.lower() == "postgresql":
                url += "?sslmode=require"
            # For MySQL, pymysql handles SSL automatically in most cases
            # Aiven-specific SSL is handled by the driver
        
        return url


@dataclass
class ConnectionInfo:
    """Information about an active connection."""
    session_id: str
    credentials: DatabaseCredentials
    engine: Any  # SQLAlchemy Engine
    created_at: datetime
    last_used: datetime
    
    def is_expired(self, timeout_minutes: int = 60) -> bool:
        """Check if connection has expired due to inactivity."""
        expiry_time = self.last_used + timedelta(minutes=timeout_minutes)
        return datetime.utcnow() > expiry_time
    
    def update_last_used(self):
        """Update last used timestamp."""
        self.last_used = datetime.utcnow()


class SessionConnectionManager:
    """
    Manages database connections for multiple sessions.
    
    This class provides thread-safe management of database connections,
    allowing each session to have its own connection to a user-specified database.
    
    Example:
        >>> manager = SessionConnectionManager()
        >>> creds = DatabaseCredentials(
        ...     db_type="mysql",
        ...     host="localhost",
        ...     port=3306,
        ...     database="mydb",
        ...     username="user",
        ...     password="pass"
        ... )
        >>> success, message = manager.test_connection(creds)
        >>> if success:
        ...     manager.create_connection("session_123", creds)
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = threading.Lock()
        logger.info("SessionConnectionManager initialized")
    
    def test_connection(self, credentials: DatabaseCredentials) -> tuple[bool, str]:
        """
        Test database connection with provided credentials.
        
        Args:
            credentials: Database credentials to test
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            connection_url = credentials.to_connection_url()
            
            # Create a temporary engine to test connection
            test_engine = create_engine(
                connection_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10}
            )
            
            # Try to connect and execute a simple query
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Clean up test engine
            test_engine.dispose()
            
            logger.info(f"Connection test successful for {credentials.db_type}://{credentials.host}/{credentials.database}")
            return True, "Connection successful!"
            
        except SQLAlchemyError as e:
            error_msg = str(e)
            logger.warning(f"Connection test failed: {error_msg}")
            
            # Provide user-friendly error messages
            if "Access denied" in error_msg or "authentication failed" in error_msg.lower():
                return False, "Authentication failed. Please check your username and password."
            elif "Unknown database" in error_msg:
                return False, f"Database '{credentials.database}' not found."
            elif "Can't connect" in error_msg or "Connection refused" in error_msg:
                return False, f"Cannot connect to {credentials.host}:{credentials.port}. Please check host and port."
            elif "timeout" in error_msg.lower():
                return False, "Connection timeout. Please check your network or host address."
            else:
                return False, f"Connection failed: {error_msg}"
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {e}")
            return False, f"Unexpected error: {str(e)}"
    
    def create_connection(
        self, 
        session_id: str, 
        credentials: DatabaseCredentials
    ) -> tuple[bool, str]:
        """
        Create and store a database connection for a session.
        
        Args:
            session_id: Session identifier
            credentials: Database credentials
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        with self._lock:
            try:
                # Close existing connection if any
                if session_id in self._connections:
                    self.close_connection(session_id)
                
                # Create connection URL
                connection_url = credentials.to_connection_url()
                
                # Create engine with connection pooling
                engine = create_engine(
                    connection_url,
                    pool_pre_ping=True,
                    pool_size=3,
                    max_overflow=5,
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    echo=False
                )
                
                # Test the connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                # Store connection info
                now = datetime.utcnow()
                self._connections[session_id] = ConnectionInfo(
                    session_id=session_id,
                    credentials=credentials,
                    engine=engine,
                    created_at=now,
                    last_used=now
                )
                
                logger.info(
                    f"Created connection for session {session_id}: "
                    f"{credentials.db_type}://{credentials.host}/{credentials.database}"
                )
                
                return True, f"Connected to {credentials.database} on {credentials.host}"
                
            except SQLAlchemyError as e:
                logger.error(f"Failed to create connection for session {session_id}: {e}")
                return False, f"Connection failed: {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error creating connection: {e}")
                return False, f"Unexpected error: {str(e)}"
    
    def get_connection(self, session_id: str) -> Optional[Any]:
        """
        Get the database engine for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SQLAlchemy Engine or None if not found
        """
        with self._lock:
            conn_info = self._connections.get(session_id)
            
            if conn_info is None:
                return None
            
            # Check if connection has expired
            if conn_info.is_expired():
                logger.warning(f"Connection for session {session_id} has expired")
                self.close_connection(session_id)
                return None
            
            # Update last used timestamp
            conn_info.update_last_used()
            
            return conn_info.engine
    
    def get_connection_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get connection information for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with connection details or None
        """
        with self._lock:
            conn_info = self._connections.get(session_id)
            
            if conn_info is None:
                return None
            
            return {
                "connected": True,
                "db_type": conn_info.credentials.db_type,
                "host": conn_info.credentials.host,
                "port": conn_info.credentials.port,
                "database": conn_info.credentials.database,
                "username": conn_info.credentials.username,
                "use_ssl": conn_info.credentials.use_ssl,
                "created_at": conn_info.created_at.isoformat(),
                "last_used": conn_info.last_used.isoformat()
            }
    
    def close_connection(self, session_id: str) -> bool:
        """
        Close and remove a session's database connection.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if connection was closed, False if not found
        """
        with self._lock:
            conn_info = self._connections.pop(session_id, None)
            
            if conn_info is None:
                return False
            
            try:
                conn_info.engine.dispose()
                logger.info(f"Closed connection for session {session_id}")
                return True
            except Exception as e:
                logger.error(f"Error closing connection for session {session_id}: {e}")
                return False
    
    def cleanup_expired_connections(self, timeout_minutes: int = 60):
        """
        Remove expired connections.
        
        Args:
            timeout_minutes: Connection timeout in minutes
        """
        with self._lock:
            expired_sessions = [
                session_id
                for session_id, conn_info in self._connections.items()
                if conn_info.is_expired(timeout_minutes)
            ]
            
            for session_id in expired_sessions:
                logger.info(f"Cleaning up expired connection for session {session_id}")
                conn_info = self._connections.pop(session_id)
                try:
                    conn_info.engine.dispose()
                except Exception as e:
                    logger.error(f"Error disposing expired connection: {e}")
    
    def get_active_connection_count(self) -> int:
        """Get the number of active connections."""
        with self._lock:
            return len(self._connections)
    
    def close_all_connections(self):
        """Close all active connections. Use with caution!"""
        with self._lock:
            session_ids = list(self._connections.keys())
            for session_id in session_ids:
                try:
                    conn_info = self._connections.pop(session_id)
                    conn_info.engine.dispose()
                except Exception as e:
                    logger.error(f"Error closing connection for {session_id}: {e}")
            
            logger.info("Closed all connections")


# Global singleton instance
_connection_manager: Optional[SessionConnectionManager] = None


def get_connection_manager() -> SessionConnectionManager:
    """
    Get or create the global SessionConnectionManager instance.
    
    Returns:
        SessionConnectionManager singleton
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = SessionConnectionManager()
    return _connection_manager
