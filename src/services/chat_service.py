"""
Chat Service - Business logic for conversational interactions.

This service orchestrates the chat flow:
1. Receives user message
2. Calls LLM for response
3. Returns formatted response

Why a service layer:
1. Separation of concerns - Routes stay thin
2. Testability - Service can be tested without HTTP
3. Reusability - Same logic can be used by different routes
4. Future extensibility - Memory, validation, etc. added here
"""
import uuid
from datetime import datetime
from typing import Optional

from src.core.logging_config import get_logger
from src.llm.client import LLMClient, LLMError
from src.models.chat import ChatRequest, ChatResponse

logger = get_logger(__name__)


class ChatService:
    """
    Service for handling chat interactions.
    
    This service manages the conversation flow between
    users and the LLM. In Phase 1, it provides stateless
    interactions without memory or database access.
    
    Example:
        >>> service = ChatService()
        >>> response = service.process_message(
        ...     ChatRequest(message="Hello!")
        ... )
        >>> print(response.message)
        "Hello! How can I help you analyze your data today?"
    """
    
    def __init__(self):
        """Initialize the chat service with LLM client."""
        self.llm_client = LLMClient()
        logger.info("ChatService initialized")
    
    def process_message(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user message and return an LLM response.
        
        Args:
            request: The chat request containing user message
                    and optional session ID.
        
        Returns:
            ChatResponse with LLM response and session info.
        
        Raises:
            ChatServiceError: If message processing fails.
        """
        # Generate or use existing session ID
        session_id = request.session_id or self._generate_session_id()
        
        logger.info(
            f"Processing message: session={session_id}, "
            f"message_length={len(request.message)}"
        )
        
        try:
            # Call LLM for response
            llm_response = self.llm_client.generate(
                user_message=request.message
            )
            
            response = ChatResponse(
                message=llm_response,
                session_id=session_id,
                timestamp=datetime.utcnow()
            )
            
            logger.info(
                f"Message processed: session={session_id}, "
                f"response_length={len(llm_response)}"
            )
            
            return response
            
        except LLMError as e:
            logger.error(f"LLM error during message processing: {e}")
            raise ChatServiceError(str(e)) from e
            
        except Exception as e:
            logger.exception(f"Unexpected error in chat service: {e}")
            raise ChatServiceError("Failed to process message") from e
    
    def _generate_session_id(self) -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())


class ChatServiceError(Exception):
    """
    Custom exception for chat service errors.
    
    This exception is raised when message processing fails
    for any reason (LLM errors, validation, etc.).
    """
    pass
