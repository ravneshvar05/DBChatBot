"""
LLM module - Language model integration.

This module handles all LLM interactions:
- Prompt construction
- API calls to Groq
- Response parsing
- Error handling for LLM failures
"""
from src.llm.client import LLMClient, LLMError

__all__ = [
    "LLMClient",
    "LLMError",
]
