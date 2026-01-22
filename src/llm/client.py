"""
LLM Client for Groq API integration.

This module provides a clean interface to the Groq API for LLaMA-3.3-70B.
It handles:
- API client initialization
- Request/response handling
- Error handling and logging
- Rate limiting awareness

Why a separate client class:
1. Encapsulation - LLM details hidden from business logic
2. Testability - Easy to mock for testing
3. Flexibility - Easy to swap to different LLM providers
"""
from typing import Optional

from groq import Groq
from groq import APIError, RateLimitError, APIConnectionError

from src.core.config import get_settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Client for interacting with the Groq LLM API.
    
    This class provides a high-level interface for generating
    LLM completions. It handles authentication, error handling,
    and logging.
    
    Example:
        >>> client = LLMClient()
        >>> response = client.generate("What is 2+2?")
        >>> print(response)
        "2 + 2 equals 4."
    """
    
    def __init__(self):
        """Initialize the LLM client with settings from environment."""
        self.settings = get_settings()
        self.client = Groq(api_key=self.settings.groq_api_key)
        self.model = self.settings.llm_model
        self.temperature = self.settings.llm_temperature
        self.max_tokens = self.settings.llm_max_tokens
        
        logger.info(
            f"LLM client initialized: model={self.model}, "
            f"temperature={self.temperature}, max_tokens={self.max_tokens}"
        )
    
    def generate(
        self,
        user_message: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a completion from the LLM.
        
        Args:
            user_message: The user's input message.
            system_prompt: Optional system prompt to set context.
                          Defaults to a generic assistant prompt.
        
        Returns:
            The LLM's response text.
        
        Raises:
            LLMError: If the API call fails.
        """
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        logger.debug(f"LLM request: {user_message[:100]}...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            result = response.choices[0].message.content
            
            logger.debug(f"LLM response: {result[:100]}...")
            logger.info(
                f"LLM call completed: "
                f"prompt_tokens={response.usage.prompt_tokens}, "
                f"completion_tokens={response.usage.completion_tokens}"
            )
            
            return result
            
        except RateLimitError as e:
            logger.error(f"LLM rate limit exceeded: {e}")
            raise LLMError("Rate limit exceeded. Please try again later.") from e
            
        except APIConnectionError as e:
            logger.error(f"LLM connection error: {e}")
            raise LLMError("Unable to connect to LLM service.") from e
            
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise LLMError(f"LLM service error: {e.message}") from e
            
        except Exception as e:
            logger.exception(f"Unexpected LLM error: {e}")
            raise LLMError("An unexpected error occurred.") from e
    
    def _get_default_system_prompt(self) -> str:
        """
        Get the default system prompt for general conversation.
        
        This prompt is used in Phase 1 for basic chatbot functionality.
        It will be replaced with specialized prompts in later phases.
        """
        return """You are a helpful data analytics assistant. 

Your role is to help users understand their data and answer questions about business metrics, trends, and insights.

In this phase, you are operating in a limited mode without database access. You should:
1. Acknowledge the user's question
2. Explain what kind of analysis you would perform if you had data access
3. Ask clarifying questions if the query is ambiguous

Be concise, professional, and helpful. If you don't know something, say so clearly."""


class LLMError(Exception):
    """
    Custom exception for LLM-related errors.
    
    This exception wraps all LLM API errors into a single type
    for easier handling in the application layer.
    """
    pass
