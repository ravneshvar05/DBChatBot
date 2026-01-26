"""
Memory Manager - Session lifecycle management.

This module provides centralized management of conversation sessions:
- Create and retrieve sessions
- Automatic TTL-based cleanup
- Session statistics

Architecture note:
This is an in-memory implementation suitable for single-instance deployments.
For production multi-instance deployments, consider Redis-backed storage.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import threading

from src.core.logging_config import get_logger
from src.memory.conversation import ConversationMemory

logger = get_logger(__name__)


class MemoryManager:
    """
    Manages multiple conversation sessions with automatic cleanup.
    
    This class provides thread-safe session management with:
    - Lazy session creation
    - TTL-based expiration
    - Periodic cleanup
    
    Example:
        >>> manager = MemoryManager(session_ttl_minutes=60)
        >>> session = manager.get_or_create_session("user-123")
        >>> session.add_user_message("Hello!")
        >>> # ... later ...
        >>> session = manager.get_session("user-123")
        >>> print(session.message_count)
        1
    """
    
    def __init__(
        self,
        session_ttl_minutes: int = 60,
        max_sessions: int = 1000,
        max_messages_per_session: int = 20
    ):
        """
        Initialize the memory manager.
        
        Args:
            session_ttl_minutes: Session expiry time in minutes
            max_sessions: Maximum concurrent sessions
            max_messages_per_session: Max messages per session
        """
        self.session_ttl = timedelta(minutes=session_ttl_minutes)
        self.max_sessions = max_sessions
        self.max_messages = max_messages_per_session
        
        self._sessions: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()
        
        logger.info(
            f"MemoryManager initialized: "
            f"TTL={session_ttl_minutes}min, "
            f"max_sessions={max_sessions}, "
            f"max_messages={max_messages_per_session}"
        )
    
    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: The session identifier
            
        Returns:
            ConversationMemory for the session
        """
        with self._lock:
            # Run cleanup periodically
            self._cleanup_expired()
            
            if session_id in self._sessions:
                session = self._sessions[session_id]
                logger.debug(f"Retrieved existing session: {session_id}")
                return session
            
            # Check session limit
            if len(self._sessions) >= self.max_sessions:
                self._evict_oldest_session()
            
            # Create new session
            session = ConversationMemory(
                session_id=session_id,
                max_messages=self.max_messages
            )
            self._sessions[session_id] = session
            
            logger.info(f"Created new session: {session_id}")
            return session
    
    def get_session(self, session_id: str) -> Optional[ConversationMemory]:
        """
        Get an existing session, or None if not found.
        
        Args:
            session_id: The session identifier
            
        Returns:
            ConversationMemory if exists, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session and self._is_expired(session):
                self._remove_session(session_id)
                return None
            return session
    
    def clear_session(self, session_id: str) -> bool:
        """
        Remove a session completely.
        
        Args:
            session_id: The session to remove
            
        Returns:
            True if session was removed, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                self._remove_session(session_id)
                logger.info(f"Cleared session: {session_id}")
                return True
            return False
    
    def clear_session_history(self, session_id: str) -> bool:
        """
        Clear a session's messages but keep the session.
        
        Args:
            session_id: The session to clear
            
        Returns:
            True if session was found and cleared
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.clear()
                logger.info(f"Cleared history for session: {session_id}")
                return True
            return False
    
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists and is not expired."""
        return self.get_session(session_id) is not None
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        Get session summary information.
        
        Args:
            session_id: The session to query
            
        Returns:
            Session summary dict or None if not found
        """
        session = self.get_session(session_id)
        if session:
            info = session.get_summary()
            info["expires_at"] = (
                session.last_activity + self.session_ttl
            ).isoformat()
            return info
        return None
    
    def get_stats(self) -> Dict:
        """
        Get manager statistics.
        
        Returns:
            Dict with session counts and configuration
        """
        with self._lock:
            active_count = len(self._sessions)
            total_messages = sum(
                s.message_count for s in self._sessions.values()
            )
            
            return {
                "active_sessions": active_count,
                "total_messages": total_messages,
                "max_sessions": self.max_sessions,
                "session_ttl_minutes": int(self.session_ttl.total_seconds() / 60),
            }
    
    def _is_expired(self, session: ConversationMemory) -> bool:
        """Check if a session has expired."""
        return datetime.utcnow() - session.last_activity > self.session_ttl
    
    def _cleanup_expired(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            Number of sessions removed
        """
        expired = [
            sid for sid, session in self._sessions.items()
            if self._is_expired(session)
        ]
        
        for session_id in expired:
            self._remove_session(session_id)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)
    
    def _evict_oldest_session(self) -> None:
        """Remove the oldest session to make room for a new one."""
        if not self._sessions:
            return
        
        oldest_id = min(
            self._sessions.keys(),
            key=lambda sid: self._sessions[sid].last_activity
        )
        
        self._remove_session(oldest_id)
        logger.warning(f"Evicted oldest session: {oldest_id}")
    
    def _remove_session(self, session_id: str) -> None:
        """Internal method to remove a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """
    Get or create the global MemoryManager instance.
    
    Returns:
        The singleton MemoryManager
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def reset_memory_manager() -> None:
    """Reset the global MemoryManager (useful for testing)."""
    global _memory_manager
    _memory_manager = None
