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
import google.generativeai as genai
from typing import Optional, List, Dict
from groq import Groq, APIError, RateLimitError, APIConnectionError

from src.core.config import get_settings
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Hybrid Client for interacting with Groq and Google Gemini APIs.
    
    Features:
    - Multi-provider support (Groq, Google)
    - Automatic fallback on failure (Groq -> Google, Google -> Groq)
    - Dynamic model selection
    """
    
    def __init__(self):
        """Initialize clients for both providers."""
        self.settings = get_settings()
        
        # Initialize Groq
        self.groq_client = Groq(api_key=self.settings.groq_api_key)
        
        # Initialize Google
        genai.configure(api_key=self.settings.google_api_key)
        
        # Default models
        self.default_model = self.settings.llm_model_smart
        self.google_model_name = "models/gemini-flash-latest" # Hardcoded fallback for now, or use config
        
        self.temperature = self.settings.llm_temperature
        self.max_tokens = self.settings.llm_max_tokens
        
        logger.info("Hybrid LLM Client initialized (Groq + Google)")
    
    def generate(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        stop: Optional[List[str]] = None
    ) -> str:
        """
        Generate completion with robust 4-layer fallback.
        """
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
            
        # Define the Fallback Cascade (The "Bulletproof" Arsenal)
        # Priority: Groq 70B -> Gemini 2.0 -> Groq 8B -> Gemini 1.5
        model_cascade = [
            {"provider": "groq", "model": self.settings.llm_model_smart}, # Llama-3.3-70b
            {"provider": "google", "model": "gemini-2.0-flash"},         # Separate Quota
            {"provider": "groq", "model": "llama-3.1-8b-instant"},       # Separate Quota
            {"provider": "google", "model": "gemini-1.5-flash"},         # Volume Model
        ]
        
        # If user requested a specific model (e.g. for small tasks), try that first
        if model:
            # Insert at top of cascade
            is_google = "gemini" in model.lower()
            model_cascade.insert(0, {"provider": "google" if is_google else "groq", "model": model})
            
        import time
        last_error = None
        
        for i, attempt in enumerate(model_cascade):
            provider = attempt["provider"]
            target_model = attempt["model"]
            
            try:
                if i > 0:
                    logger.info(f"Attempt {i+1}: Falling back to {provider.title()} ({target_model})...")
                    time.sleep(1 * i) # Linear backoff: 0s, 1s, 2s, 3s
                
                if provider == "google":
                    return self._generate_google(user_message, system_prompt, history, target_model, stop)
                else:
                    return self._generate_groq(user_message, system_prompt, history, target_model, stop)
                    
            except Exception as e:
                # Log usage error vs rate limit
                error_msg = str(e).lower()
                is_rate_limit = "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg
                
                log_level = logger.warning if is_rate_limit else logger.error
                log_level(f"Provider failed ({provider}/{target_model}): {e}")
                
                last_error = e
                # Continue to next model in cascade...
                
        # If we get here, ALL models failed
        logger.critical("ALL LLM PROVIDERS FAILED.")
        raise LLMError(f"All 4 layers of LLM defense failed. Last error: {last_error}")

    def _generate_groq(self, user_message, system_prompt, history, model, stop=None):
        """Execute request using Groq."""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.groq_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stop=stop
            )
            return response.choices[0].message.content
        except Exception as e:
            raise e

    def _generate_google(self, user_message, system_prompt, history, model, stop=None):
        """Execute request using Google Gemini."""
        try:
            # Map common model names if needed
            if "gemini" not in model:
                model = "gemini-2.0-flash"
                
            model_instance = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_prompt
            )
            
            # Convert history format (OpenAI -> Google)
            chat_history = []
            if history:
                for msg in history:
                    role = "user" if msg["role"] == "user" else "model"
                    chat_history.append({"role": role, "parts": [msg["content"]]})
            
            # Configure generation config if stop sequences provided
            generation_config = genai.types.GenerationConfig(
                stop_sequences=stop
            ) if stop else None

            chat = model_instance.start_chat(history=chat_history)
            response = chat.send_message(user_message, generation_config=generation_config)
            return response.text
        except Exception as e:
            # Google sometimes blocks content, handle gracefully
            if hasattr(e, "finish_reason") and e.finish_reason == 3: # SAFETY
                 raise Exception("Content blocked by Google Safety filters")
            raise e

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt."""
        return "You are a helpful assistant."


class LLMError(Exception):
    """
    Custom exception for LLM-related errors.
    
    This exception wraps all LLM API errors into a single type
    for easier handling in the application layer.
    """
    pass
