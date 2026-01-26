"""
Query Decomposer Service.

This service is responsible for breaking down complex user queries into 
independent sub-questions that can be executed separately.
"""
import json
from typing import List

from src.core.logging_config import get_logger
from src.core.config import get_settings
from src.llm.client import LLMClient, LLMError
from src.llm.prompts.decomposition import (
    get_decomposition_system_prompt,
    get_decomposition_user_prompt
)

logger = get_logger(__name__)


class QueryDecomposer:
    """
    Decomposes complex queries into simple independent questions.
    """
    
    def __init__(self):
        """Initialize with LLM client."""
        self.llm = LLMClient()
        self.settings = get_settings()
        logger.info("QueryDecomposer initialized")
        
    def decompose(self, question: str) -> List[str]:
        """
        Decompose a question into a list of independent sub-questions.
        
        Args:
            question: The user's original complex question
            
        Returns:
            List of independent sub-questions strings
        """
        # Don't decompose very short questions
        if len(question.split()) < 4:
            return [question]

        # HEURISTIC OPTIMIZATION:
        # If the question is a simple lookup, skip the LLM optimization step to save time (1-3s)
        # and prevent "Double Answer" issues where the LLM invents a context step.
        lower_q = question.strip().lower()
        simple_indicators = [
            "show me", "list", "get", "what are", "count", "how many", "find"
        ]
        
        # Check if it looks like a single-table filter request
        # e.g. "Show me nike shoes", "List all products"
        is_simple = any(lower_q.startswith(ind) for ind in simple_indicators)
        has_complex_joins = " and " in lower_q and " then " in lower_q # "Do X and THEN do Y"
        has_multistep_delimiters = "?" in lower_q or ";" in lower_q
        
        # Only preserve "simple" status if no splitters are found
        if is_simple and not has_complex_joins and not has_multistep_delimiters:
            logger.info(f"Skipping decomposition for simple query: '{question}'")
            return [question]
            
        # RULE-BASED DECOMPOSITION (Optimized for Speed/Tokens)
        # The user requested to disable the LLM here to save tokens.
        # We split by common delimiters: '?', ';', ' and then '
        
        import re
        
        # 1. Normalize delimiters to a common one (e.g., <SPLIT>)
        # Regex explanation:
        # \? -> Literal question mark
        # ; -> Literal semicolon
        # \s+and\s+then\s+ -> " and then " (case insensitive handled by .lower() earlier, but let's be safe)
        
        split_pattern = r'\?|;| and then '
        
        # split() will remove the delimiters, so we might lose the '?' at the end.
        # That's fine for SQL generation, but if we want to preserve it, we'd need capture groups.
        # For now, simple split is sufficient.
        
        parts = re.split(split_pattern, question, flags=re.IGNORECASE)
        
        # Filter empty strings and strip whitespace
        questions = [p.strip() for p in parts if p.strip()]
        
        if len(questions) > 1:
            logger.info(f"Rule-based decomposition found {len(questions)} parts: {questions}")
            return questions
            
        return [question]

        # LLM LOGIC COMMENTED OUT FOR NOW (To restore, uncomment below)
        # system_prompt = get_decomposition_system_prompt()
        # user_prompt = get_decomposition_user_prompt(question)
        # 
        # try:
        #     response = self.llm.generate(
        #         user_message=user_prompt,
        #         system_prompt=system_prompt,
        #         model=self.settings.llm_model_fast
        #     )
        #     
        #     # Parse JSON output
        #     try:
        #         # Clean up potential markdown code blocks
        #         if "```json" in response:
        #             response = response.split("```json")[1].split("```")[0].strip()
        #         elif "```" in response:
        #             response = response.split("```")[1].split("```")[0].strip()
        #         
        #         questions = json.loads(response)
        #         
        #         if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
        #             logger.info(f"Decomposed '{question}' into {len(questions)} sub-questions")
        #             return questions
        #         
        #         logger.warning(f"Invalid decomposition format, returning original: {response}")
        #         return [question]
        #         
        #     except json.JSONDecodeError:
        #         logger.warning(f"Failed to parse decomposition JSON: {response}")
        #         return [question]
        #         
        # except Exception as e:
        #     logger.error(f"Error during query decomposition: {e}")
        #     return [question]
