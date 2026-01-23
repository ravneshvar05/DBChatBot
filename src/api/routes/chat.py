"""
Chat Routes - API endpoints for conversational interactions.

This module defines the /chat endpoint which supports:
- mode='chat': General conversation (Phase 1)
- mode='sql': Text-to-SQL database queries (Phase 3)
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.core.logging_config import get_logger
from src.models.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.chat_service import ChatService, ChatServiceError
from src.services.sql_service import get_sql_service

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={
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
    
    **Modes:**
    - `mode='sql'` (default): Ask questions about your data. The system will:
      1. Generate SQL from your question
      2. Execute the query safely
      3. Return both the answer and the generated SQL
    
    - `mode='chat'`: General conversation without database access.
    
    **Examples (SQL mode):**
    - "What are the top 5 highest rated movies?"
    - "How many movies are from 1994?"
    - "What's the most popular movie?"
    """
)
async def send_message(request: ChatRequest) -> ChatResponse:
    """
    Process a user message and return the assistant's response.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    logger.info(f"Received request: mode={request.mode}, message={request.message[:50]}...")
    
    try:
        if request.mode == "sql":
            # SQL mode - Text-to-SQL
            sql_service = get_sql_service()
            result = sql_service.query(request.message)
            
            return ChatResponse(
                message=result.answer,
                session_id=session_id,
                timestamp=datetime.utcnow(),
                sql=result.sql,
                data=result.data,
                row_count=result.row_count
            )
        
        else:
            # Chat mode - General conversation
            chat_service = get_chat_service()
            result = chat_service.process_message(request)
            
            return ChatResponse(
                message=result.message,
                session_id=session_id,
                timestamp=datetime.utcnow()
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
