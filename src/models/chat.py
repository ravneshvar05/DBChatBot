"""
Request and Response models for the Chat API.

These Pydantic models define the contract between client and server.
They provide:
- Type validation
- Automatic documentation
- Request/response serialization
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Request model for the /chat endpoint.
    
    Attributes:
        message: The user's natural language question or statement.
        session_id: Optional session identifier for multi-turn conversations.
        mode: Query mode - 'chat' for general, 'sql' for database queries.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message or question",
        examples=["What are the top 5 highest rated movies?"]
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversations"
    )
    mode: str = Field(
        default="sql",
        description="Query mode: 'chat' for general conversation, 'sql' for database queries"
    )
    include_analysis: bool = Field(
        default=False,
        description="If True, performs deep AI analysis on the results (slower). If False, uses fast rule-based summary."
    )


class ChatResponse(BaseModel):
    """
    Response model for the /chat endpoint.
    
    Includes natural language answer, generated SQL, and analytics formatting.
    """
    message: str = Field(
        ...,
        description="The assistant's natural language response"
    )
    session_id: str = Field(
        ...,
        description="Session ID for this conversation"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response generation timestamp"
    )
    # SQL-specific fields
    sql: Optional[str] = Field(
        default=None,
        description="Generated SQL query (if mode='sql')"
    )
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Query results (if mode='sql')"
    )
    row_count: Optional[int] = Field(
        default=None,
        description="Number of rows returned"
    )
    # Analytics formatting fields (Phase 5)
    formatted_data: Optional[str] = Field(
        default=None,
        description="Data formatted as markdown table or list"
    )
    insights: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Automatic statistics and insights from the data"
    )
    query_type: Optional[str] = Field(
        default=None,
        description="Detected query type (aggregation, ranking, comparison, etc.)"
    )
    
    # Phase 9: Multi-Question Support
    sql_queries: List[str] = Field(
        default_factory=list,
        description="List of SQL queries for multi-part questions"
    )
    formatted_data_list: List[str] = Field(
        default_factory=list,
        description="List of formatted data tables for multi-part questions"
    )
    
    # Token Usage
    token_usage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Token usage statistics (prompt_tokens, completion_tokens, total_tokens)"
    )


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: str = Field(default="healthy")
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    message: str
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
