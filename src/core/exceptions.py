"""
Custom Exceptions - Application-specific error classes.

This module defines a hierarchy of exceptions for clean error handling:
- Each exception has a status code and error code
- Used by the API layer for consistent error responses
- No stack traces leaked in production
"""
from typing import Optional


class ChatbotException(Exception):
    """
    Base exception for all chatbot errors.
    
    Subclass this for specific error types.
    """
    status_code: int = 500
    error_code: str = "internal_error"
    
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
    
    def to_dict(self) -> dict:
        """Convert to error response dict."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class RateLimitExceeded(ChatbotException):
    """Raised when a client exceeds the rate limit."""
    status_code = 429
    error_code = "rate_limit_exceeded"
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Please wait {retry_after} seconds.",
            details=f"retry_after={retry_after}"
        )
        self.retry_after = retry_after


class ValidationError(ChatbotException):
    """Raised when input validation fails."""
    status_code = 400
    error_code = "validation_error"
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, details=f"field={field}" if field else None)
        self.field = field


class DatabaseError(ChatbotException):
    """Raised when database operations fail."""
    status_code = 503
    error_code = "database_error"
    
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)


class LLMError(ChatbotException):
    """Raised when LLM API calls fail."""
    status_code = 503
    error_code = "llm_error"
    
    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(message)


class QueryTimeoutError(ChatbotException):
    """Raised when a SQL query times out."""
    status_code = 504
    error_code = "query_timeout"
    
    def __init__(self, timeout_seconds: int = 30):
        super().__init__(
            message=f"Query timed out after {timeout_seconds} seconds",
            details=f"timeout={timeout_seconds}s"
        )
        self.timeout_seconds = timeout_seconds


class SessionNotFoundError(ChatbotException):
    """Raised when a session is not found."""
    status_code = 404
    error_code = "session_not_found"
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id[:8]}...",
            details=f"session_id={session_id}"
        )


class SQLGenerationError(ChatbotException):
    """Raised when SQL generation fails."""
    status_code = 400
    error_code = "sql_generation_error"
    
    def __init__(self, message: str = "Could not generate SQL for this question"):
        super().__init__(message)


class SQLValidationError(ChatbotException):
    """Raised when generated SQL fails validation."""
    status_code = 400
    error_code = "sql_validation_error"
    
    def __init__(self, message: str):
        super().__init__(message)
