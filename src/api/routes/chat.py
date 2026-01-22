"""
Chat Routes - API endpoints for conversational interactions.

This module defines the /chat endpoint and related routes.
Routes are thin wrappers that:
1. Validate input (via Pydantic)
2. Call service layer
3. Format output
4. Handle errors

No business logic should live in routes.
"""
from fastapi import APIRouter, HTTPException

from src.core.logging_config import get_logger
from src.models.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.chat_service import ChatService, ChatServiceError

logger = get_logger(__name__)

# Create router with prefix and tags for API documentation
router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

# Initialize service (singleton pattern via module-level instance)
# In production, this would be dependency-injected for better testing
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """
    Get or create the chat service instance.
    
    This lazy initialization pattern prevents service
    creation before the application is fully configured.
    """
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
    
    The assistant will respond with helpful information about data analysis.
    In the current phase, the assistant operates without database access.
    
    **Session Management:**
    - If `session_id` is not provided, a new session will be created
    - Use the returned `session_id` for follow-up messages (Phase 4+)
    """,
    responses={
        200: {
            "description": "Successful response",
            "model": ChatResponse
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponse
        },
        503: {
            "description": "LLM service unavailable",
            "model": ErrorResponse
        }
    }
)
async def send_message(request: ChatRequest) -> ChatResponse:
    """
    Process a user message and return the assistant's response.
    
    This endpoint accepts natural language queries and returns
    AI-generated responses. The response includes a session ID
    for conversation continuity.
    """
    logger.info(f"Received chat request: message_length={len(request.message)}")
    
    try:
        service = get_chat_service()
        response = service.process_message(request)
        
        logger.info(f"Chat response sent: session={response.session_id}")
        return response
        
    except ChatServiceError as e:
        logger.error(f"Chat service error: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_error",
                "message": str(e),
                "details": "The LLM service is currently unavailable"
            }
        )
    except Exception as e:
        logger.exception(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": str(e) if logger.isEnabledFor(10) else None  # DEBUG level
            }
        )
