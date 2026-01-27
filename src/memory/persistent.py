"""
Persistent Memory Manager - Database-backed conversation storage.

OPTIMIZED for context-aware SQL generation:
1. Proper metadata serialization (SQL queries preserved)
2. Better message rehydration from DB
3. Debug logging for troubleshooting
4. Ensures Message.to_dict() compatibility

This module provides a MySQL-backed implementation of the MemoryManager
interface. It uses write-through caching for performance:
- Reads: Check in-memory cache first, then DB
- Writes: Save to DB immediately, update cache

This enables Long-Term Memory (LTM) that survives server restarts.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import threading
import json

from sqlalchemy.orm import Session

from src.core.logging_config import get_logger
from src.database.connection import get_database
from src.database.models import ConversationSession, ConversationMessage
from src.memory.conversation import Message, ConversationMemory

logger = get_logger(__name__)


class PersistentMemoryManager:
    """
    Database-backed memory manager with in-memory caching.
    
    OPTIMIZED: Better metadata handling for SQL context preservation.
    
    Provides the same interface as MemoryManager but persists
    conversations to MySQL for long-term storage.
    
    Example:
        >>> manager = PersistentMemoryManager()
        >>> session = manager.get_or_create_session("user-123")
        >>> session.add_user_message("Hello!")
        >>> # Message is now saved to database with metadata
        >>> # Server can restart and session will be restored with full context
    """
    
    def __init__(
        self,
        session_ttl_minutes: int = 1440,  # 24 hours for persistent
        max_messages_per_session: int = 100  # Higher limit for persistent
    ):
        """
        Initialize the persistent memory manager.
        
        Args:
            session_ttl_minutes: Session expiry time (default 24 hours)
            max_messages_per_session: Max messages to keep per session
        """
        self.session_ttl = timedelta(minutes=session_ttl_minutes)
        self.max_messages = max_messages_per_session
        self.db = get_database()
        
        # In-memory cache for fast access
        self._cache: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()
        
        logger.info(
            f"PersistentMemoryManager initialized: "
            f"TTL={session_ttl_minutes}min, max_messages={max_messages_per_session}"
        )
    
    def get_or_create_session(self, session_id: str) -> ConversationMemory:
        """
        Get an existing session or create a new one.
        
        Checks cache first, then loads from DB if needed.
        
        Args:
            session_id: The session identifier
            
        Returns:
            ConversationMemory for the session
        """
        with self._lock:
            # Check cache first
            if session_id in self._cache:
                logger.debug(f"[PERSISTENT] Session cache hit: {session_id}")
                return self._cache[session_id]
            
            # Try to load from database
            with self.db.get_session() as db_session:
                db_conv = db_session.query(ConversationSession).filter(
                    ConversationSession.id == session_id
                ).first()
                
                if db_conv:
                    # Load existing session from DB
                    memory = self._load_from_db(db_conv, db_session)
                    self._cache[session_id] = memory
                    logger.info(
                        f"[PERSISTENT] Loaded session from DB: {session_id} "
                        f"({memory.message_count} messages)"
                    )
                    return memory
                
                # Create new session
                memory = self._create_new_session(session_id, db_session)
                self._cache[session_id] = memory
                logger.info(f"[PERSISTENT] Created new persistent session: {session_id}")
                return memory
    
    def get_session(self, session_id: str) -> Optional[ConversationMemory]:
        """
        Get an existing session, or None if not found.
        
        Args:
            session_id: The session identifier
            
        Returns:
            ConversationMemory if exists, None otherwise
        """
        with self._lock:
            # Check cache
            if session_id in self._cache:
                return self._cache[session_id]
            
            # Check database
            with self.db.get_session() as db_session:
                db_conv = db_session.query(ConversationSession).filter(
                    ConversationSession.id == session_id
                ).first()
                
                if db_conv:
                    memory = self._load_from_db(db_conv, db_session)
                    self._cache[session_id] = memory
                    return memory
                
                return None
    
    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Save a message to the database.
        
        OPTIMIZED: Better metadata serialization for SQL preservation.
        
        Args:
            session_id: Session to add message to
            role: 'user' or 'assistant'
            content: Message content
            metadata: Optional metadata dict (includes SQL, row_count, etc.)
        """
        with self.db.get_session() as db_session:
            # Ensure metadata is JSON-serializable
            safe_metadata = self._serialize_metadata(metadata)
            
            # Create message record
            db_message = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                extra_data=safe_metadata  # Stored as extra_data in DB
            )
            db_session.add(db_message)
            
            # Update session stats
            db_conv = db_session.query(ConversationSession).filter(
                ConversationSession.id == session_id
            ).first()
            
            if db_conv:
                db_conv.message_count += 1
                db_conv.last_activity = datetime.utcnow()
            
            db_session.commit()
            
            # Debug: Log SQL if present
            if safe_metadata and safe_metadata.get('sql'):
                logger.debug(
                    f"[PERSISTENT] Saved message with SQL: session={session_id}, "
                    f"sql={safe_metadata['sql'][:50]}..."
                )
            else:
                logger.debug(f"[PERSISTENT] Saved message: session={session_id}, role={role}")
    
    def clear_session(self, session_id: str) -> bool:
        """
        Remove a session and all its messages.
        
        Args:
            session_id: The session to remove
            
        Returns:
            True if session was removed
        """
        with self._lock:
            # Remove from cache
            if session_id in self._cache:
                del self._cache[session_id]
            
            # Remove from database
            with self.db.get_session() as db_session:
                db_conv = db_session.query(ConversationSession).filter(
                    ConversationSession.id == session_id
                ).first()
                
                if db_conv:
                    db_session.delete(db_conv)
                    db_session.commit()
                    logger.info(f"[PERSISTENT] Deleted session from DB: {session_id}")
                    return True
                
                return False
    
    def clear_session_history(self, session_id: str) -> bool:
        """
        Clear messages but keep the session.
        
        Args:
            session_id: The session to clear
            
        Returns:
            True if session was found and cleared
        """
        with self._lock:
            # Clear cache
            if session_id in self._cache:
                self._cache[session_id].clear()
            
            # Clear from database
            with self.db.get_session() as db_session:
                # Delete messages
                db_session.query(ConversationMessage).filter(
                    ConversationMessage.session_id == session_id
                ).delete()
                
                # Reset session stats
                db_conv = db_session.query(ConversationSession).filter(
                    ConversationSession.id == session_id
                ).first()
                
                if db_conv:
                    db_conv.message_count = 0
                    db_conv.last_activity = datetime.utcnow()
                    db_session.commit()
                    logger.info(f"[PERSISTENT] Cleared history for session: {session_id}")
                    return True
                
                return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        Get session summary information.
        
        Args:
            session_id: The session to query
            
        Returns:
            Session info dict or None
        """
        with self.db.get_session() as db_session:
            db_conv = db_session.query(ConversationSession).filter(
                ConversationSession.id == session_id
            ).first()
            
            if db_conv:
                return {
                    "session_id": db_conv.id,
                    "message_count": db_conv.message_count,
                    "created_at": db_conv.created_at.isoformat(),
                    "last_activity": db_conv.last_activity.isoformat(),
                    "expires_at": (db_conv.last_activity + self.session_ttl).isoformat()
                }
            
            return None
    
    def get_recent_sessions(self, limit: int = 20) -> List[Dict]:
        """
        Get recently active sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session info dicts
        """
        with self.db.get_session() as db_session:
            sessions = db_session.query(ConversationSession).order_by(
                ConversationSession.last_activity.desc()
            ).limit(limit).all()
            
            result = []
            for s in sessions:
                s_dict = s.to_dict()
                # Get first user message for preview
                first_msg = db_session.query(ConversationMessage.content).filter(
                    ConversationMessage.session_id == s.id,
                    ConversationMessage.role == 'user'
                ).order_by(ConversationMessage.timestamp.asc()).limit(1).scalar()
                
                # Truncate preview if too long
                preview = first_msg if first_msg else "New Conversation"
                if len(preview) > 50:
                    preview = preview[:47] + "..."
                
                s_dict['preview'] = preview
                result.append(s_dict)
            
            return result
    
    def get_stats(self) -> Dict:
        """
        Get manager statistics.
        
        Returns:
            Dict with session counts and configuration
        """
        with self.db.get_session() as db_session:
            total_sessions = db_session.query(ConversationSession).count()
            total_messages = db_session.query(ConversationMessage).count()
            
            return {
                "active_sessions": total_sessions,
                "cached_sessions": len(self._cache),
                "total_messages": total_messages,
                "session_ttl_minutes": int(self.session_ttl.total_seconds() / 60),
                "storage": "persistent"
            }
    
    # ==================== OPTIMIZED HELPER METHODS ====================
    
    def _serialize_metadata(self, metadata: Optional[Dict]) -> Optional[Dict]:
        """
        Ensure metadata is JSON-serializable.
        
        Handles datetime objects and other non-serializable types.
        """
        if not metadata:
            return None
        
        try:
            # Test if it's already serializable
            json.dumps(metadata)
            return metadata
        except (TypeError, ValueError):
            # Convert non-serializable types
            safe_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, datetime):
                    safe_metadata[key] = value.isoformat()
                elif isinstance(value, (str, int, float, bool, type(None))):
                    safe_metadata[key] = value
                elif isinstance(value, (list, dict)):
                    try:
                        json.dumps(value)
                        safe_metadata[key] = value
                    except:
                        safe_metadata[key] = str(value)
                else:
                    safe_metadata[key] = str(value)
            
            return safe_metadata
    
    def _deserialize_metadata(self, metadata: Optional[Dict]) -> Dict:
        """
        Deserialize metadata from DB, handling any format issues.
        
        OPTIMIZED: Ensures metadata is always a dict, never None.
        """
        if not metadata:
            return {}
        
        if isinstance(metadata, dict):
            return metadata
        
        # Fallback: try to parse as JSON string
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except:
                logger.warning(f"[PERSISTENT] Failed to parse metadata: {metadata[:100]}")
                return {}
        
        return {}
    
    def _load_from_db(
        self,
        db_conv: ConversationSession,
        db_session: Session
    ) -> ConversationMemory:
        """
        Load a ConversationMemory from database records.
        
        OPTIMIZED: Better metadata handling and debug logging.
        """
        memory = PersistentConversationMemory(
            session_id=db_conv.id,
            manager=self,
            max_messages=self.max_messages
        )
        memory.created_at = db_conv.created_at
        memory.last_activity = db_conv.last_activity
        
        # Load messages
        messages = db_session.query(ConversationMessage).filter(
            ConversationMessage.session_id == db_conv.id
        ).order_by(ConversationMessage.timestamp).all()
        
        logger.debug(f"[PERSISTENT] Loading {len(messages)} messages from DB")
        
        sql_count = 0
        for msg in messages:
            # Deserialize metadata safely
            metadata = self._deserialize_metadata(msg.extra_data)
            
            # Debug: Count messages with SQL
            if metadata.get('sql'):
                sql_count += 1
            
            message = Message(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=metadata
            )
            memory.messages.append(message)
        
        logger.debug(
            f"[PERSISTENT] Loaded session: {db_conv.id}, "
            f"{len(messages)} messages ({sql_count} with SQL context)"
        )
        
        return memory
    
    def _create_new_session(
        self,
        session_id: str,
        db_session: Session
    ) -> ConversationMemory:
        """Create a new session in database and memory."""
        # Create database record
        db_conv = ConversationSession(
            id=session_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            message_count=0
        )
        db_session.add(db_conv)
        db_session.commit()
        
        # Create memory object
        memory = PersistentConversationMemory(
            session_id=session_id,
            manager=self,
            max_messages=self.max_messages
        )
        
        return memory


class PersistentConversationMemory(ConversationMemory):
    """
    ConversationMemory that auto-saves to database.
    
    OPTIMIZED: Ensures metadata (including SQL) is properly persisted.
    
    Extends ConversationMemory to add write-through persistence.
    """
    
    def __init__(
        self,
        session_id: str,
        manager: PersistentMemoryManager,
        max_messages: int = 100
    ):
        super().__init__(session_id, max_messages)
        self._manager = manager
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """
        Add user message and save to database.
        
        Args:
            content: Message content
            metadata: Optional metadata (e.g., query type)
        
        Returns:
            Created Message object
        """
        message = super().add_user_message(content, metadata)
        self._manager.save_message(
            self.session_id, "user", content, metadata
        )
        return message
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> Message:
        """
        Add assistant message and save to database.
        
        CRITICAL: This is where SQL context is saved!
        
        Args:
            content: Message content
            metadata: Optional metadata (MUST include 'sql' key for context)
        
        Returns:
            Created Message object
        """
        message = super().add_assistant_message(content, metadata)
        
        # Debug: Log when SQL is being saved
        if metadata and metadata.get('sql'):
            logger.debug(
                f"[PERSISTENT] Saving assistant message with SQL: "
                f"{metadata['sql'][:50]}..."
            )
        
        self._manager.save_message(
            self.session_id, "assistant", content, metadata
        )
        return message


# Singleton instance
_persistent_manager: Optional[PersistentMemoryManager] = None


def get_persistent_memory_manager() -> PersistentMemoryManager:
    """Get or create the persistent memory manager singleton."""
    global _persistent_manager
    if _persistent_manager is None:
        _persistent_manager = PersistentMemoryManager()
    return _persistent_manager


def reset_persistent_memory_manager() -> None:
    """Reset the persistent memory manager (for testing)."""
    global _persistent_manager
    _persistent_manager = None
