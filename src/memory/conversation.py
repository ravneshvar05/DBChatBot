"""
Conversation Memory - In-memory conversation storage.

OPTIMIZED for persistent memory compatibility:
- Message class now has to_dict() method
- get_recent_history() returns dicts (not Message objects)
- Backward compatible with existing code
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Message:
    """
    A single conversation message.
    
    OPTIMIZED: Now includes to_dict() for compatibility with
    both in-memory and persistent storage.
    """
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Message to dictionary format.
        
        This ensures compatibility between fresh sessions and
        rehydrated sessions from database.
        
        Returns:
            Dict with role, content, timestamp, metadata
        """
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """
        Create Message from dictionary.
        
        Useful for deserializing from storage.
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()
        
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            metadata=data.get("metadata", {})
        )


class ConversationMemory:
    """
    In-memory storage for a single conversation session.
    
    OPTIMIZED: get_recent_history() now returns dicts for
    compatibility with sql_service context extraction.
    
    Example:
        >>> memory = ConversationMemory("session-123")
        >>> memory.add_user_message("Hello!")
        >>> memory.add_assistant_message("Hi there!")
        >>> history = memory.get_recent_history(n=2)
        >>> # Returns: [{'role': 'user', 'content': 'Hello!', ...}, ...]
    """
    
    def __init__(self, session_id: str, max_messages: int = 50):
        """
        Initialize conversation memory.
        
        Args:
            session_id: Unique identifier for this conversation
            max_messages: Maximum messages to keep (oldest removed first)
        """
        self.session_id = session_id
        self.max_messages = max_messages
        self.messages: List[Message] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def add_user_message(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a user message to the conversation.
        
        Args:
            content: The message content
            metadata: Optional metadata (e.g., query type, filters)
            
        Returns:
            The created Message object
        """
        message = Message(
            role="user",
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_activity = datetime.utcnow()
        
        # Trim if too long
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        return message
    
    def add_assistant_message(
        self, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add an assistant message to the conversation.
        
        Args:
            content: The message content
            metadata: Optional metadata (e.g., SQL used, row_count)
            
        Returns:
            The created Message object
        """
        message = Message(
            role="assistant",
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_activity = datetime.utcnow()
        
        # Trim if too long
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        return message
    
    def get_recent_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the last n messages as dictionaries.
        
        OPTIMIZED: Returns dicts instead of Message objects for
        compatibility with sql_service._get_history_context()
        
        Args:
            n: Number of recent messages to return
            
        Returns:
            List of message dictionaries with keys: role, content, timestamp, metadata
        """
        recent_messages = self.messages[-n:] if n > 0 else []
        return [msg.to_dict() for msg in recent_messages]
    
    def get_all_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages as dictionaries.
        
        Returns:
            List of all message dictionaries
        """
        return [msg.to_dict() for msg in self.messages]
    
    def clear(self) -> None:
        """Clear all messages from memory."""
        self.messages.clear()
        self.last_activity = datetime.utcnow()
    
    @property
    def is_empty(self) -> bool:
        """Check if conversation has any messages."""
        return len(self.messages) == 0
    
    @property
    def message_count(self) -> int:
        """Get total number of messages."""
        return len(self.messages)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get conversation summary.
        
        Returns:
            Dict with session_id, message_count, created_at, last_activity
        """
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_empty": self.is_empty
        }
