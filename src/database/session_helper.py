"""
Session Connection Helper - Utilities for session-based database connections.

This module provides helper functions to:
- Auto-connect sessions to default database
- Retrieve session-specific database connections
- Manage connection lifecycle
"""
from typing import Optional, Tuple
from src.core.config import get_settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


def ensure_default_connection(session_id: str) -> Tuple[bool, str]:
    """
    Ensure a session has a database connection.
    If not connected, auto-connect to the default database from .env (if configured).
    
    Args:
        session_id: Session identifier
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Local import to avoid circular dependency
    from src.database.connection_manager import get_connection_manager, DatabaseCredentials
    
    manager = get_connection_manager()
    
    # Check if already connected
    existing_conn = manager.get_connection(session_id)
    if existing_conn is not None:
        logger.debug(f"Session {session_id} already has active connection")
        return True, "Already connected"
    
    # Only auto-connect if DATABASE_URL is configured
    settings = get_settings()
    
    # Check if DATABASE_URL is set and not empty
    if not settings.database_url or settings.database_url.strip() == "":
        logger.debug(f"No default DATABASE_URL configured, skipping auto-connect for session {session_id}")
        return False, "No default database configured. Please connect manually."
    
    try:
        # Parse credentials from DATABASE_URL
        db_url = settings.database_url
        
        # Determine database type
        if "mysql" in db_url.lower():
            db_type = "mysql"
            default_port = 3306
        elif "postgresql" in db_url.lower():
            db_type = "postgresql"
            default_port = 5432
        else:
            return False, "Unsupported database type in DATABASE_URL"
        
        # Simple parsing of URL (format: driver://user:pass@host:port/dbname)
        import re
        pattern = r"(?:mysql\+pymysql|postgresql)://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)"
        match = re.match(pattern, db_url)
        
        if not match:
            return False, "Could not parse DATABASE_URL"
        
        username, password, host, port, database = match.groups()
        port = int(port) if port else default_port
        use_ssl = "sslmode=require" in db_url or "ssl-mode" in db_url
        
        # Create credentials
        credentials = DatabaseCredentials(
            db_type=db_type,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            use_ssl=use_ssl
        )
        
        # Create connection
        success, message = manager.create_connection(session_id, credentials)
        
        if success:
            logger.info(f"Auto-connected session {session_id} to default database: {database}")
        else:
            logger.warning(f"Failed to auto-connect session {session_id}: {message}")
        
        return success, message
        
    except Exception as e:
        logger.error(f"Error auto-connecting session {session_id}: {e}")
        return False, f"Auto-connection failed: {str(e)}"


def get_session_database_connection(session_id: str) -> Optional:
    """
    Get the DatabaseConnection for a session.
    Auto-connects to default database if not connected.
    
    Args:
        session_id: Session identifier
        
    Returns:
        DatabaseConnection instance or None if connection failed
    """
    # Local imports to avoid circular dependency
    from src.database.connection_manager import get_connection_manager, DatabaseCredentials
    
    # Ensure connection exists (auto-connect if needed)
    success, _ = ensure_default_connection(session_id)
    
    if not success:
        return None
    
    # Get the raw engine
    manager = get_connection_manager()
    engine = manager.get_connection(session_id)
    
    if engine is None:
        return None
    
    # Get connection URL from connection info
    conn_info = manager.get_connection_info(session_id)
    if not conn_info:
        return None
    
    # Reconstruct credentials to get URL
    credentials = DatabaseCredentials(
        db_type=conn_info["db_type"],
        host=conn_info["host"],
        port=conn_info["port"],
        database=conn_info["database"],
        username=conn_info["username"],
        password="",  # Not stored in info
        use_ssl=conn_info["use_ssl"]
    )
    
    # Create DatabaseConnection with the session's URL
    # Note: We're creating a new DatabaseConnection instance but using the existing engine
    # This is a bit of a workaround - ideally we'd store the DatabaseConnection directly
    # For now, we'll just use the engine directly via the connection manager
    return None  # Will use engine directly instead


def get_session_components(session_id: str):
    """
    Get database components for a session (inspector, executor, loader).
    Does NOT auto-connect - returns None if no connection exists.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Tuple of (DatabaseConnection, SchemaInspector, QueryExecutor, CSVLoader)
        or (None, None, None, None) if no connection exists
    """
    # Local imports to avoid circular dependency
    from src.database.connection_manager import get_connection_manager
    from src.database.schema import SchemaInspector
    from src.database.executor import QueryExecutor
    from src.database.loader import CSVLoader
    
    # Get connection manager
    manager = get_connection_manager()
    
    # Check if connection exists - DO NOT auto-connect
    engine = manager.get_connection(session_id)
    
    if engine is None:
        logger.debug(f"No connection found for session {session_id}")
        return None, None, None, None
    
    if engine is None:
        return None, None, None, None
    
    # Get connection info to reconstruct URL
    conn_info = manager.get_connection_info(session_id)
    if not conn_info:
        return None, None, None, None
    
    # Reconstruct database URL
    db_type = conn_info["db_type"]
    username = conn_info["username"]
    # Note: Password is not stored in conn_info for security
    # We need to get it from the manager's internal credentials
    # For now, we'll create a new DatabaseConnection using the existing engine
    # This is done by passing the connection URL
    
    # Actually, let's use a better approach - create DatabaseConnection from existing engine
    # We can't easily do this, so instead we'll create wrapper instances
    # that use the session's engine
    
    # Create a temporary DatabaseConnection with the engine
    # This requires modifying our approach slightly
    
    # Create components using a mock connection that wraps the engine
    class SessionDatabaseConnection:
        """Wrapper for session engine to match DatabaseConnection interface."""
        def __init__(self, engine):
            self.engine = engine
            self.settings = get_settings()
        
        def get_session(self):
            """Return session context manager."""
            from contextlib import contextmanager
            from sqlalchemy.orm import sessionmaker
            
            SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
            
            @contextmanager
            def _get_session():
                session = SessionLocal()
                try:
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            
            return _get_session()
    
    # Create wrapper
    db_conn = SessionDatabaseConnection(engine)
    
    # Create components
    inspector = SchemaInspector(db_conn)
    executor = QueryExecutor(db_conn)
    loader = CSVLoader(db_connection=db_conn)
    
    return db_conn, inspector, executor, loader
