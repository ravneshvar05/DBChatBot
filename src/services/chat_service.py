"""
Chat Service - Business logic for conversational interactions.

This service orchestrates the chat flow:
1. Receives user message
2. Retrieves/creates session memory
3. Calls LLM with conversation history
4. Stores response in memory
5. Returns formatted response

Why a service layer:
1. Separation of concerns - Routes stay thin
2. Testability - Service can be tested without HTTP
3. Reusability - Same logic can be used by different routes
4. Memory management - Session state is handled here
"""
import uuid
from datetime import datetime
from typing import Optional

from src.core.logging_config import get_logger
from src.llm.client import LLMClient, LLMError
from src.models.chat import ChatRequest, ChatResponse
from src.memory import get_memory_manager, MemoryManager

logger = get_logger(__name__)


class ChatService:
    """
    Service for handling chat interactions with conversation memory.
    
    This service manages the conversation flow between users and the LLM,
    including multi-turn conversation support through session memory.
    
    Example:
        >>> service = ChatService()
        >>> response = service.process_message(
        ...     ChatRequest(message="Hello!", session_id="abc-123")
        ... )
        >>> print(response.message)
        "Hello! How can I help you analyze your data today?"
        >>> # Follow-up maintains context
        >>> response2 = service.process_message(
        ...     ChatRequest(message="What can you do?", session_id="abc-123")
        ... )
    """
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        """
        Initialize the chat service.
        
        Args:
            memory_manager: Optional MemoryManager instance.
                          Uses global singleton if not provided.
        """
        self.llm_client = LLMClient()
        self.memory_manager = memory_manager or get_memory_manager()
        logger.info("ChatService initialized with memory support")
    
    def process_message(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user message and return an LLM response.
        
        Maintains conversation context through session memory.
        
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
            # Get or create session memory
            memory = self.memory_manager.get_or_create_session(session_id)
            
            # Get conversation history (before adding current message)
            history = memory.get_history_for_llm()
            
            # Add user message to memory
            memory.add_user_message(request.message)
            
            # Call LLM with conversation history
            llm_response = self.llm_client.generate(
                user_message=request.message,
                history=history if history else None
            )
            
            # Store assistant response in memory
            memory.add_assistant_message(llm_response)
            
            response = ChatResponse(
                message=llm_response,
                session_id=session_id,
                timestamp=datetime.utcnow()
            )
            
            logger.info(
                f"Message processed: session={session_id}, "
                f"response_length={len(llm_response)}, "
                f"history_size={memory.message_count}"
            )
            
            return response
            
        except LLMError as e:
            logger.error(f"LLM error during message processing: {e}")
            raise ChatServiceError(str(e)) from e
            
        except Exception as e:
            logger.exception(f"Unexpected error in chat service: {e}")
            raise ChatServiceError("Failed to process message") from e
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a session's conversation history.
        
        Args:
            session_id: The session to clear
            
        Returns:
            True if session was found and cleared
        """
        return self.memory_manager.clear_session_history(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Get information about a session.
        
        Args:
            session_id: The session to query
            
        Returns:
            Session info dict or None if not found
        """
        return self.memory_manager.get_session_info(session_id)
    
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
