"""
Request and Response models for the Chat API.

These Pydantic models define the contract between client and server.
They provide:
- Type validation
- Automatic documentation
- Request/response serialization

Why separate models:
1. Clear API contract
2. Decoupled from internal representations
3. Version control for API changes
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Request model for the /chat endpoint.
    
    Attributes:
        message: The user's natural language question or statement.
        session_id: Optional session identifier for multi-turn conversations.
                   If not provided, a new session will be created.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message or question",
        examples=["What were the top 5 products last month?"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversations. Optional in Phase 1.",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )


class ChatResponse(BaseModel):
    """
    Response model for the /chat endpoint.
    
    Attributes:
        message: The assistant's response to the user's question.
        session_id: Session identifier for tracking conversations.
        timestamp: When the response was generated (ISO 8601 format).
    """
    message: str = Field(
        ...,
        description="The assistant's response"
    )
    session_id: str = Field(
        ...,
        description="Session ID for this conversation"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response generation timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Based on the sales data, the top 5 products last month were...",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:30:45.123456"
            }
        }


class HealthResponse(BaseModel):
    """
    Response model for the /health endpoint.
    
    Used for monitoring and load balancer health checks.
    """
    status: str = Field(
        default="healthy",
        description="Current service status"
    )
    version: str = Field(
        ...,
        description="Application version"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    All API errors return this structure for consistent error handling.
    """
    error: str = Field(
        ...,
        description="Error type or code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    details: Optional[str] = Field(
        default=None,
        description="Additional error details (development only)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the error occurred"
    )
