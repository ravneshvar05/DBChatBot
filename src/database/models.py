"""
Database Models - SQLAlchemy ORM models for persistent storage.

This module defines the database schema for:
- Conversation sessions
- Conversation messages

These models enable Long-Term Memory (LTM) persistence.
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class ConversationSession(Base):
    """
    Model for storing conversation sessions.
    
    Each session represents a single conversation thread that can
    contain multiple messages between user and assistant.
    """
    __tablename__ = "conversation_sessions"
    
    id = Column(String(36), primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Optional session metadata (renamed from metadata)
    
    # Relationship to messages
    messages = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.timestamp"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "message_count": self.message_count,
            "extra_data": self.extra_data
        }


class ConversationMessage(Base):
    """
    Model for storing individual messages in a conversation.
    
    Each message belongs to a session and contains the role,
    content, and optional extra data (like SQL queries, row counts).
    """
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    extra_data = Column(JSON, nullable=True)  # SQL query, insights, etc. (renamed from metadata)
    
    # Relationship to session
    session = relationship("ConversationSession", back_populates="messages")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.extra_data  # Return as 'metadata' for API compatibility
        }
    
    def to_llm_format(self) -> Dict[str, str]:
        """Convert to format suitable for LLM API."""
        return {
            "role": self.role,
            "content": self.content
        }
