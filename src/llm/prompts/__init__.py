"""
Prompts module - LLM prompt templates.

Prompts are stored as separate Python files for:
- Version control of prompt changes
- Easy A/B testing
- Clear documentation of prompt purpose
"""
from src.llm.prompts.sql_prompts import (
    get_sql_system_prompt,
    get_sql_user_prompt,
    get_answer_system_prompt,
    get_answer_user_prompt,
)

__all__ = [
    "get_sql_system_prompt",
    "get_sql_user_prompt",
    "get_answer_system_prompt",
    "get_answer_user_prompt",
]
