"""
Connection Routes - API endpoints for database connection management.

These endpoints allow users to:
- Test database connections
- Establish connections for their session
- Disconnect from databases
- Check connection status
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.core.logging_config import get_logger
from src.database import (
    get_connection_manager,
    DatabaseCredentials,
    SessionConnectionManager,
    SchemaInspector,
    DatabaseConnection
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/connection",
    tags=["Connection"],
)


# Request/Response models
class ConnectionTestRequest(BaseModel):
    """Request to test a database connection."""
    db_type: str = Field(..., description="Database type: mysql or postgresql")
    host: str = Field(..., description="Database host address")
    port: int = Field(default=None, description="Database port (default: 3306 for MySQL, 5432 for PostgreSQL)")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    use_ssl: bool = Field(default=False, description="Use SSL/TLS connection")


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str


class ConnectionCreateRequest(BaseModel):
    """Request to create a session connection."""
    session_id: str = Field(..., description="Session identifier")
    db_type: str = Field(..., description="Database type: mysql or postgresql")
    host: str = Field(..., description="Database host address")
    port: int = Field(default=None, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    use_ssl: bool = Field(default=False, description="Use SSL/TLS connection")


class ConnectionCreateResponse(BaseModel):
    """Response from connection creation."""
    success: bool
    message: str
    connection_info: Dict[str, Any] | None = None


class ConnectionStatusResponse(BaseModel):
    """Response with connection status."""
    connected: bool
    connection_info: Dict[str, Any] | None = None


class ConnectionDisconnectRequest(BaseModel):
    """Request to disconnect."""
    session_id: str = Field(..., description="Session identifier")


class ConnectionDisconnectResponse(BaseModel):
    """Response from disconnection."""
    success: bool
    message: str


@router.post(
    "/test",
    response_model=ConnectionTestResponse,
    summary="Test database connection",
    description="""
    Test a database connection with provided credentials.
    
    This does not create a persistent connection, just validates
    that the credentials work.
    
    Supports:
    - MySQL (local and cloud)
    - PostgreSQL (local and cloud)
    - SSL/TLS connections
    """
)
async def test_connection(request: ConnectionTestRequest) -> ConnectionTestResponse:
    """Test database connection without creating a session connection."""
    logger.info(f"Testing connection to {request.db_type}://{request.host}/{request.database}")
    
    # Validate database type
    if request.db_type.lower() not in ["mysql", "postgresql"]:
        raise HTTPException(
            status_code=400,
            detail="Database type must be 'mysql' or 'postgresql'"
        )
    
    # Create credentials
    credentials = DatabaseCredentials(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database=request.database,
        username=request.username,
        password=request.password,
        use_ssl=request.use_ssl
    )
    
    # Test connection
    manager = get_connection_manager()
    success, message = manager.test_connection(credentials)
    
    return ConnectionTestResponse(
        success=success,
        message=message
    )


@router.post(
    "/connect",
    response_model=ConnectionCreateResponse,
    summary="Create session database connection",
    description="""
    Create a database connection for a specific session.
    
    This connection will be used for all database operations
    in this session until disconnected.
    """
)
async def create_connection(request: ConnectionCreateRequest) -> ConnectionCreateResponse:
    """Create a database connection for a session."""
    logger.info(
        f"Creating connection for session {request.session_id}: "
        f"{request.db_type}://{request.host}/{request.database}"
    )
    
    # Validate database type
    if request.db_type.lower() not in ["mysql", "postgresql"]:
        raise HTTPException(
            status_code=400,
            detail="Database type must be 'mysql' or 'postgresql'"
        )
    
    # Create credentials
    credentials = DatabaseCredentials(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database=request.database,
        username=request.username,
        password=request.password,
        use_ssl=request.use_ssl
    )
    
    # Create connection
    manager = get_connection_manager()
    success, message = manager.create_connection(request.session_id, credentials)
    
    if not success:
        return ConnectionCreateResponse(
            success=False,
            message=message,
            connection_info=None
        )
    
    # Get connection info
    conn_info = manager.get_connection_info(request.session_id)
    
    # Get basic schema info (table count)
    try:
        engine = manager.get_connection(request.session_id)
        if engine:
            db_conn = DatabaseConnection(credentials.to_connection_url())
            inspector = SchemaInspector(db_conn)
            table_names = inspector.get_table_names()
            
            # Filter out system tables
            user_tables = [
                t for t in table_names 
                if t not in ["conversation_sessions", "conversation_messages"]
            ]
            
            if conn_info:
                conn_info["table_count"] = len(user_tables)
                conn_info["tables_preview"] = user_tables[:5]  # First 5 tables
    except Exception as e:
        logger.warning(f"Could not fetch schema info: {e}")
    
    return ConnectionCreateResponse(
        success=True,
        message=message,
        connection_info=conn_info
    )


@router.post(
    "/disconnect",
    response_model=ConnectionDisconnectResponse,
    summary="Disconnect session database",
    description="Close the database connection for a session."
)
async def disconnect_connection(request: ConnectionDisconnectRequest) -> ConnectionDisconnectResponse:
    """Disconnect a session's database connection."""
    logger.info(f"Disconnecting session {request.session_id}")
    
    manager = get_connection_manager()
    success = manager.close_connection(request.session_id)
    
    if success:
        return ConnectionDisconnectResponse(
            success=True,
            message="Disconnected successfully"
        )
    else:
        return ConnectionDisconnectResponse(
            success=False,
            message="No active connection found"
        )


@router.get(
    "/status/{session_id}",
    response_model=ConnectionStatusResponse,
    summary="Get connection status",
    description="Check if a session has an active database connection."
)
async def get_connection_status(session_id: str) -> ConnectionStatusResponse:
    """Get the connection status for a session."""
    manager = get_connection_manager()
    conn_info = manager.get_connection_info(session_id)
    
    if conn_info is None:
        return ConnectionStatusResponse(
            connected=False,
            connection_info=None
        )
    
    return ConnectionStatusResponse(
        connected=True,
        connection_info=conn_info
    )


@router.get(
    "/stats",
    summary="Get connection manager statistics",
    description="Get statistics about active connections (for monitoring)."
)
async def get_connection_stats() -> Dict[str, Any]:
    """Get connection manager statistics."""
    manager = get_connection_manager()
    
    return {
        "active_connections": manager.get_active_connection_count()
    }
