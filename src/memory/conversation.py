"""
Conversation Memory - Data structures for conversation history.

This module provides classes for managing conversation state:
- Message: Individual message in a conversation
- ConversationMemory: Session-based conversation history

Why in-memory storage:
1. Low latency - No database overhead for chat history
2. Simplicity - No additional infrastructure needed
3. Stateless scaling - Each instance manages its own sessions
4. Privacy - Conversations don't persist after session ends
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal


@dataclass
class Message:
    """
    Represents a single message in a conversation.
    
    Attributes:
        role: The role of the message sender (user, assistant, or system)
        content: The message content
        timestamp: When the message was created
        metadata: Optional additional data (e.g., SQL query, row count)
    
    Example:
        >>> msg = Message(role="user", content="What are the top movies?")
        >>> print(msg.to_dict())
        {"role": "user", "content": "What are the top movies?"}
    """
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dict format for LLM API (role + content only)."""
        return {"role": self.role, "content": self.content}
    
    def to_full_dict(self) -> Dict[str, Any]:
        """Convert to full dict including metadata."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ConversationMemory:
    """
    Manages conversation history for a single session.
    
    This class maintains a list of messages for a session, providing
    methods to add messages and retrieve history for LLM context.
    
    Attributes:
        session_id: Unique identifier for this session
        max_messages: Maximum number of messages to retain
        created_at: When the session was created
        last_activity: Last message timestamp
    
    Example:
        >>> memory = ConversationMemory(session_id="abc-123")
        >>> memory.add_user_message("Hello!")
        >>> memory.add_assistant_message("Hi! How can I help?")
        >>> print(memory.get_history_for_llm())
        [{"role": "user", "content": "Hello!"}, 
         {"role": "assistant", "content": "Hi! How can I help?"}]
    """
    
    def __init__(
        self,
        session_id: str,
        max_messages: int = 20
    ):
        """
        Initialize conversation memory.
        
        Args:
            session_id: Unique session identifier
            max_messages: Maximum messages to keep (oldest removed first)
        """
        self.session_id = session_id
        self.max_messages = max_messages
        self.messages: List[Message] = []
        self.created_at = datetime.utcnow()
        self.last_activity = self.created_at
    
    def add_user_message(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a user message to the conversation.
        
        Args:
            content: The user's message text
            metadata: Optional additional data
            
        Returns:
            The created Message object
        """
        message = Message(
            role="user",
            content=content,
            metadata=metadata or {}
        )
        self._add_message(message)
        return message
    
    def add_assistant_message(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add an assistant response to the conversation.
        
        Args:
            content: The assistant's response text
            metadata: Optional data (e.g., SQL query, row count)
            
        Returns:
            The created Message object
        """
        message = Message(
            role="assistant",
            content=content,
            metadata=metadata or {}
        )
        self._add_message(message)
        return message
    
    def add_system_message(self, content: str) -> Message:
        """Add a system message (used for context/instructions)."""
        message = Message(role="system", content=content)
        self._add_message(message)
        return message
    
    def _add_message(self, message: Message) -> None:
        """Internal method to add message and enforce limits."""
        self.messages.append(message)
        self.last_activity = message.timestamp
        
        # Trim if over limit (keep most recent)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
    
    def get_history(self) -> List[Message]:
        """Get all messages in the conversation."""
        return self.messages.copy()
    
    def get_history_for_llm(self) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM API.
        
        Returns:
            List of dicts with 'role' and 'content' keys
        """
        return [msg.to_dict() for msg in self.messages]
    
    def get_recent_history(self, n: int = 5) -> List[Dict[str, str]]:
        """
        Get the N most recent messages for LLM context.
        
        Args:
            n: Number of recent messages to return
            
        Returns:
            List of message dicts
        """
        recent = self.messages[-n:] if n < len(self.messages) else self.messages
        return [msg.to_dict() for msg in recent]
    
    def clear(self) -> None:
        """Clear all messages from the conversation."""
        self.messages = []
        self.last_activity = datetime.utcnow()
    
    @property
    def message_count(self) -> int:
        """Number of messages in the conversation."""
        return len(self.messages)
    
    @property
    def is_empty(self) -> bool:
        """Check if conversation has no messages."""
        return len(self.messages) == 0
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of this conversation session.
        
        Returns:
            Dict with session info (id, counts, timestamps)
        """
        user_count = sum(1 for m in self.messages if m.role == "user")
        assistant_count = sum(1 for m in self.messages if m.role == "assistant")
        
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "user_messages": user_count,
            "assistant_messages": assistant_count,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }
