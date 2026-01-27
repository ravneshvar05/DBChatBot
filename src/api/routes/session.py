"""
Session Management Routes - API endpoints for conversation session lifecycle.

Endpoints:
- POST /session/new: Create a new session
- GET /session/{id}: Get session info
- DELETE /session/{id}: Delete a session
- GET /session/{id}/history: Get conversation history
- GET /session/list: List all sessions (Phase 6 - LTM)
"""
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.logging_config import get_logger
from src.core.config import get_settings
from src.memory import get_memory_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/session", tags=["Session Management"])


# ============================================================
# Request/Response Models
# ============================================================

class SessionCreateResponse(BaseModel):
    """Response for session creation."""
    session_id: str = Field(..., description="New session identifier")
    message: str = Field(default="Session created successfully")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    storage: str = Field(default="memory", description="Storage type (memory or persistent)")


class SessionInfoResponse(BaseModel):
    """Response with session information."""
    session_id: str
    message_count: int
    created_at: str
    last_activity: str
    expires_at: str
    user_messages: Optional[int] = None
    assistant_messages: Optional[int] = None


class SessionHistoryResponse(BaseModel):
    """Response with conversation history."""
    session_id: str
    messages: list
    message_count: int


class SessionDeleteResponse(BaseModel):
    """Response for session deletion."""
    session_id: str
    message: str
    deleted: bool


class ManagerStatsResponse(BaseModel):
    """Response with memory manager statistics."""
    active_sessions: int
    total_messages: int
    session_ttl_minutes: int
    storage: str = Field(default="memory", description="Storage type")
    cached_sessions: Optional[int] = None
    max_sessions: Optional[int] = None


class SessionListItem(BaseModel):
    """Single session in list response."""
    id: str
    created_at: str
    last_activity: str
    message_count: int
    preview: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: List[SessionListItem]
    total: int
    storage: str


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/new",
    response_model=SessionCreateResponse,
    summary="Create New Session",
    description="Create a new conversation session and return its ID."
)
async def create_session():
    """
    Create a new conversation session.
    
    Returns a unique session ID that can be used in /chat requests
    to maintain conversation context.
    """
    session_id = str(uuid.uuid4())
    settings = get_settings()
    
    # Pre-create the session in memory manager
    manager = get_memory_manager()
    manager.get_or_create_session(session_id)
    
    storage = "persistent" if settings.memory_persistent else "memory"
    logger.info(f"Created new session via API: {session_id} (storage={storage})")
    
    return SessionCreateResponse(
        session_id=session_id,
        message="Session created successfully. Use this session_id in your /chat requests.",
        storage=storage
    )


@router.get(
    "/list",
    response_model=SessionListResponse,
    summary="List All Sessions",
    description="List all conversation sessions (persistent mode only)."
)
async def list_sessions(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum sessions to return")
):
    """
    List recent conversation sessions.
    
    Only available when MEMORY_PERSISTENT=true.
    """
    settings = get_settings()
    manager = get_memory_manager()
    
    if not settings.memory_persistent:
        # For in-memory, we can still return cached sessions
        stats = manager.get_stats()
        return SessionListResponse(
            sessions=[],
            total=stats.get("active_sessions", 0),
            storage="memory"
        )
    
    # Get recent sessions from persistent manager
    if hasattr(manager, 'get_recent_sessions'):
        sessions = manager.get_recent_sessions(limit=limit)
        return SessionListResponse(
            sessions=[SessionListItem(**s) for s in sessions],
            total=len(sessions),
            storage="persistent"
        )
    
    return SessionListResponse(
        sessions=[],
        total=0,
        storage="memory"
    )


@router.get(
    "/{session_id}",
    response_model=SessionInfoResponse,
    summary="Get Session Info",
    description="Get information about an existing session."
)
async def get_session_info(session_id: str):
    """
    Get information about a conversation session.
    
    Returns message counts, timestamps, and expiration time.
    """
    manager = get_memory_manager()
    info = manager.get_session_info(session_id)
    
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    
    return SessionInfoResponse(**info)


@router.delete(
    "/all",
    summary="Delete All Sessions",
    description="Delete all conversation sessions and messages. Use with caution!"
)
async def delete_all_sessions():
    """
    Delete ALL conversation sessions from the database.
    
    This permanently removes all conversation history.
    """
    settings = get_settings()
    
    if not settings.memory_persistent:
        # For in-memory, just reset the manager
        from src.memory import reset_memory_manager
        reset_memory_manager()
        return {
            "message": "All in-memory sessions cleared",
            "sessions_deleted": 0,
            "messages_deleted": 0
        }
    
    # For persistent storage, delete from database
    try:
        from src.database import get_database
        from src.database.models import ConversationSession, ConversationMessage
        
        db = get_database()
        
        with db.get_session() as session:
            # Count before deletion
            session_count = session.query(ConversationSession).count()
            message_count = session.query(ConversationMessage).count()
            
            # Delete all messages first (foreign key)
            session.query(ConversationMessage).delete()
            # Delete all sessions
            session.query(ConversationSession).delete()
            session.commit()
        
        # Reset in-memory cache too
        from src.memory import reset_memory_manager
        reset_memory_manager()
        
        logger.info(f"Deleted all sessions: {session_count} sessions, {message_count} messages")
        
        return {
            "message": "All conversation history deleted",
            "sessions_deleted": session_count,
            "messages_deleted": message_count
        }
        
    except Exception as e:
        logger.error(f"Failed to delete all sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{session_id}",
    response_model=SessionDeleteResponse,
    summary="Delete Session",
    description="Delete a session and all its conversation history."
)
async def delete_session(session_id: str):
    """
    Delete a conversation session.
    
    This removes all conversation history for the session.
    """
    manager = get_memory_manager()
    deleted = manager.clear_session(session_id)
    
    if not deleted:
        return SessionDeleteResponse(
            session_id=session_id,
            message="Session not found (may have already expired)",
            deleted=False
        )
    
    logger.info(f"Deleted session via API: {session_id}")
    
    return SessionDeleteResponse(
        session_id=session_id,
        message="Session deleted successfully",
        deleted=True
    )


@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="Get Session History",
    description="Get the full conversation history for a session."
)
async def get_session_history(session_id: str):
    """
    Get conversation history for a session.
    
    Returns all messages in the conversation, ordered chronologically.
    """
    manager = get_memory_manager()
    session = manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    
    # Get full message details
    messages = session.get_all_messages()
    
    return SessionHistoryResponse(
        session_id=session_id,
        messages=messages,
        message_count=len(messages)
    )


@router.post(
    "/{session_id}/clear",
    response_model=SessionDeleteResponse,
    summary="Clear Session History",
    description="Clear conversation history but keep the session."
)
async def clear_session_history(session_id: str):
    """
    Clear conversation history for a session.
    
    The session remains active but all messages are removed.
    """
    manager = get_memory_manager()
    cleared = manager.clear_session_history(session_id)
    
    if not cleared:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    
    logger.info(f"Cleared history for session: {session_id}")
    
    return SessionDeleteResponse(
        session_id=session_id,
        message="Session history cleared",
        deleted=False  # Session still exists
    )


@router.get(
    "",
    response_model=ManagerStatsResponse,
    summary="Get Manager Stats",
    description="Get statistics about active sessions."
)
async def get_manager_stats():
    """
    Get memory manager statistics.
    
    Returns counts of active sessions, total messages, and configuration.
    """
    settings = get_settings()
    manager = get_memory_manager()
    stats = manager.get_stats()
    
    # Ensure required fields
    stats.setdefault("storage", "persistent" if settings.memory_persistent else "memory")
    
    return ManagerStatsResponse(**stats)
