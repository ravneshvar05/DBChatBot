"""
Chat Routes - API endpoints for conversational interactions.

This module defines the /chat endpoint which supports:
- mode='chat': General conversation with memory (Phase 1 + 4)
- mode='sql': Text-to-SQL database queries with context (Phase 3 + 4)

Phase 7 adds rate limiting, input validation, and enhanced error handling.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response

from src.core.logging_config import get_logger
from src.core.rate_limiter import get_rate_limiter
from src.core.validators import validate_message, validate_session_id, validate_mode
from src.core.exceptions import RateLimitExceeded, ValidationError
from src.models.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.chat_service import ChatService, ChatServiceError
from src.services.sql_service import get_sql_service

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

# Initialize services
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Get or create the chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the assistant",
    description="""
    Send a natural language message to the data analytics assistant.
    
    **Rate Limiting (Phase 7):**
    Requests are limited to 30 per minute per session.
    Check X-RateLimit-Remaining header for remaining requests.
    
    **Multi-turn Conversations (Phase 4):**
    Include a `session_id` to maintain conversation context across requests.
    The assistant will remember previous questions and answers in the session.
    
    **Modes:**
    - `mode='sql'` (default): Ask questions about your data. The system will:
      1. Generate SQL from your question (with conversation context)
      2. Execute the query safely
      3. Return both the answer and the generated SQL
    
    - `mode='chat'`: General conversation with memory support.
    
    **Examples (SQL mode with follow-ups):**
    - First: "What are the top 5 highest rated movies?"
    - Follow-up: "What about the lowest rated ones?"
    - Follow-up: "Show me movies from 1994"
    """
)
async def send_message(request: ChatRequest, response: Response) -> ChatResponse:
    """
    Process a user message and return the assistant's response.
    
    Includes rate limiting and input validation (Phase 7).
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    # ============================================================
    # Phase 7: Input Validation
    # ============================================================
    
    # Validate session_id format if provided
    if request.session_id:
        is_valid, error = validate_session_id(request.session_id)
        if not is_valid:
            raise ValidationError(error, field="session_id")
    
    # Validate and sanitize message
    is_valid, sanitized_message, error = validate_message(request.message)
    if not is_valid:
        raise ValidationError(error, field="message")
    
    # Validate mode
    is_valid, error = validate_mode(request.mode)
    if not is_valid:
        raise ValidationError(error, field="mode")
    
    # ============================================================
    # Phase 7: Rate Limiting
    # ============================================================
    
    rate_limiter = get_rate_limiter()
    is_allowed, remaining = rate_limiter.is_allowed(session_id)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    
    if not is_allowed:
        reset_time = rate_limiter.get_reset_time(session_id)
        retry_after = max(1, int((reset_time - datetime.utcnow()).total_seconds()))
        raise RateLimitExceeded(retry_after=retry_after)
    
    # ============================================================
    # Process Request
    # ============================================================
    
    logger.info(
        f"Processing request: mode={request.mode}, "
        f"session={session_id[:8]}..., "
        f"message={sanitized_message[:50]}..."
    )
    
    try:
        if request.mode == "sql":
            # SQL mode - Text-to-SQL with session context
            # Get session-specific database components
            from src.database import get_session_components
            from src.services.sql_service import SQLService
            
            db_conn, inspector, executor, loader = get_session_components(session_id)
            
            if inspector is None or executor is None:
                raise HTTPException(
                    status_code=400,
                    detail="No database connection found. Please connect to a database first via the frontend."
                )
            
            # Initialize SQL service with session components
            sql_service = SQLService(
                memory_manager=None,  # Will use global singleton
                executor=executor,
                schema_inspector=inspector
            )
            
            result = sql_service.query(
                question=sanitized_message,  # Use sanitized message
                session_id=session_id,
                include_analysis=request.include_analysis
            )
            
            return ChatResponse(
                message=result.answer,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                sql=result.sql,
                data=result.data,
                row_count=result.row_count,
                # Analytics fields (Phase 5)
                formatted_data=result.formatted_data,
                insights=result.insights,
                query_type=result.query_type,
                # Phase 9: Multi-Question Support
                sql_queries=result.sql_queries,
                formatted_data_list=result.formatted_data_list,
                token_usage=result.token_usage
            )
        
        else:
            # Chat mode - General conversation with memory
            chat_service = get_chat_service()
            
            # Ensure session_id is in request for memory tracking
            request_with_session = ChatRequest(
                message=sanitized_message,  # Use sanitized message
                session_id=session_id,
                mode=request.mode
            )
            
            result = chat_service.process_message(request_with_session)
            
            return ChatResponse(
                message=result.message,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                token_usage=result.token_usage
            )
            
    except ChatServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": "service_error", "message": str(e)}
        )
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)}
        )
