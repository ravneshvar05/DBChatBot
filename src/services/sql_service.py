"""
SQL Service - Orchestrated Text-to-SQL operations with OPTIMIZED memory and analytics.

KEY OPTIMIZATIONS:
1. Enhanced history context with structured formatting
2. Better SQL extraction and reuse logic
3. Smarter context window management
4. Improved relevance filtering for context
5. Better handling of multi-turn conversations

This service handles the complete flow:
1. Get schema context
2. Retrieve conversation history for context (OPTIMIZED)
3. Generate SQL from natural language
4. Validate the SQL
5. Execute the query
6. Analyze results and generate insights (Phase 5)
7. Format data for display (Phase 5)
8. Store Q&A in session memory
9. Format results with natural language answer

This is the main entry point for text-to-SQL functionality.
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import re

from src.core.logging_config import get_logger
from src.core.config import get_settings
from src.database import get_database, SchemaInspector, QueryExecutor
from src.database.validator import SQLValidator, ValidationResult
from src.llm.client import LLMClient, LLMError
from src.llm.prompts import (
    get_sql_system_prompt,
    get_sql_user_prompt,
    get_answer_user_prompt,
)
from src.llm.prompts.analysis_prompts import FAST_MODE_SYSTEM_PROMPT
from src.memory import get_memory_manager, MemoryManager, ConversationMemory
from src.analytics import ResultFormatter, InsightsGenerator, QueryClassifier
from src.analytics.decomposer import QueryDecomposer

logger = get_logger(__name__)


@dataclass
class SQLResponse:
    """
    Response from SQL service.
    
    Includes generated SQL, natural language answer, and analytics.
    """
    success: bool
    answer: str  # Natural language answer
    sql: Optional[str] = None  # Generated SQL
    data: Optional[list] = None  # Query results
    row_count: int = 0
    error: Optional[str] = None
    # Analytics fields (Phase 5)
    formatted_data: Optional[str] = None  # Markdown table/list
    insights: Optional[Dict[str, Any]] = None  # Statistics
    query_type: Optional[str] = None  # Detected type
    
    # Phase 9: Multi-Question Support
    sql_queries: List[str] = field(default_factory=list)
    formatted_data_list: List[str] = field(default_factory=list)
    token_usage: Optional[Dict[str, int]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "answer": self.answer,
            "sql": self.sql,
            "data": self.data,
            "row_count": self.row_count,
            "error": self.error,
            "formatted_data": self.formatted_data,
            "insights": self.insights,
            "query_type": self.query_type,
            "token_usage": self.token_usage,
        }


class SQLService:
    """
    Service for converting natural language to SQL and executing queries.
    
    Supports multi-turn conversations with session memory for
    context-aware SQL generation. Includes analytics formatting (Phase 5).
    
    Example:
        >>> service = SQLService()
        >>> response = service.query("What are the top 5 movies?", session_id="abc")
        >>> print(response.answer)
        "The top 5 highest rated movies are..."
        >>> print(response.query_type)
        "ranking"
        >>> print(response.formatted_data)
        "| title | rating |\\n|---|---|\\n..."
    """
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        """
        Initialize SQL service with required components.
        
        Args:
            memory_manager: Optional MemoryManager instance.
                          Uses global singleton if not provided.
        """
        self.llm = LLMClient()
        self.settings = get_settings()
        self.executor = QueryExecutor()
        self.schema_inspector = SchemaInspector()
        self.memory_manager = memory_manager or get_memory_manager()
        
        # Analytics components (Phase 5)
        self.formatter = ResultFormatter()
        self.insights_generator = InsightsGenerator()
        self.query_classifier = QueryClassifier()
        self.decomposer = QueryDecomposer()
        
        # Get allowed tables from database
        self.allowed_tables = set(self.schema_inspector.get_table_names())
        self.validator = SQLValidator(allowed_tables=self.allowed_tables)
        
        # Cache schema for prompts
        self._schema_cache = None
        
        logger.info(
            f"SQLService initialized with {len(self.allowed_tables)} tables, "
            f"memory support, and analytics formatting"
        )
        
    def _merge_usage(self, u1: Optional[Dict], u2: Optional[Dict]) -> Dict[str, int]:
        """Helper to merge token usage dictionaries."""
        if not u1: return u2 or {}
        if not u2: return u1
        return {k: u1.get(k, 0) + u2.get(k, 0) for k in set(u1) | set(u2)}
    
    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        include_analysis: bool = False
    ) -> SQLResponse:
        """
        Process a natural language question and return results.
        Supports multi-part questions via decomposition.
        """
        logger.info(f"Processing SQL query: {question[:50]}...")
        
        # Get session memory if session_id provided
        memory: Optional[ConversationMemory] = None
        if session_id:
            memory = self.memory_manager.get_or_create_session(session_id)
        
        try:
            # Phase 9: Decomposition
            sub_questions = self.decomposer.decompose(question)
            
            # Get common context
            schema = self._get_schema()
            history_context = self._get_history_context(memory, question)  # OPTIMIZED: Pass current question
            
            if len(sub_questions) <= 1:
                # Single path (optimized) -- Return directly, NO aggregation wrapper
                qs = sub_questions[0] if sub_questions else question
                return self._process_single_question(
                    qs, memory, schema, history_context, store_memory=True,
                    include_analysis=include_analysis
                )
            
            # Multi path
            logger.info(f"Executing {len(sub_questions)} sub-questions")
            results = []
            for sub_q in sub_questions:
                # Execute without storing individual steps in memory
                res = self._process_single_question(
                    sub_q, memory, schema, history_context, store_memory=False
                )
                results.append(res)
            
            # Aggregate results
            return self._aggregate_results(question, results, memory)
            
        except Exception as e:
            logger.exception(f"Unexpected error in SQL service: {e}")
            return SQLResponse(
                success=False,
                answer="An unexpected error occurred. Please try again.",
                error=str(e)
            )
            
    def _process_single_question(
        self,
        question: str,
        memory: Optional[ConversationMemory],
        schema: str,
        history_context: str,
        store_memory: bool = True,
        include_analysis: bool = False
    ) -> SQLResponse:
        """Process a single atomic question."""
        try:
            # Step 3: Generate SQL
            sql, sql_usage = self._generate_sql(question, schema, history_context)
            
            if sql.startswith("ERROR:"):
                if store_memory:
                    self._store_error_in_memory(memory, question, sql)
                return SQLResponse(
                    success=False,
                    answer=f"I couldn't generate a query for that question. {sql}",
                    error=sql,
                    token_usage=sql_usage
                )
            
            # Step 4: Validate SQL
            validation = self.validator.validate(sql)
            
            if not validation.is_valid:
                logger.warning(f"SQL validation failed: {validation.error}")
                if store_memory:
                    self._store_error_in_memory(memory, question, validation.error)
                return SQLResponse(
                    success=False,
                    answer=f"I generated a query but it didn't pass safety checks. {validation.error}",
                    sql=sql,
                    error=validation.error
                )
            
            # Use validated (possibly modified) SQL
            sql = validation.sql
            
            # Step 5: Classify query type
            query_type = self.query_classifier.classify(sql)
            
            # Step 6: Execute query
            result = self.executor.execute(sql)
            
            if not result.success:
                logger.error(f"Query execution failed: {result.error}")
                if store_memory:
                    self._store_error_in_memory(memory, question, result.error)
                return SQLResponse(
                    success=False,
                    answer="The query failed to execute. Please try rephrasing your question.",
                    sql=sql,
                    error=result.error,
                    query_type=query_type.value
                )
            
            # Step 7: Generate analytics
            insights = self.insights_generator.generate_insights(
                result.data, 
                query_type.value,
                include_analysis=include_analysis
            )
            formatted_data = self._format_results(result.data, query_type)
            
            # Step 8: Generate natural language answer
            answer, answer_usage = self._generate_answer(
                question, sql, result.data, result.row_count, insights
            )
            
            # Combine usage
            total_usage = self._merge_usage(sql_usage, answer_usage)
            
            # Step 9: Store Q&A in session memory
            if store_memory:
                self._store_success_in_memory(memory, question, answer, sql, result.row_count)
            
            return SQLResponse(
                success=True,
                answer=answer,
                sql=sql,
                data=result.data,
                row_count=result.row_count,
                formatted_data=formatted_data,
                insights=insights,
                query_type=query_type.value,
                token_usage=total_usage
            )
            
        except LLMError as e:
            logger.error(f"LLM error in SQL service: {e}")
            return SQLResponse(
                success=False,
                answer=f"I'm having trouble connecting to the AI service. Error: {str(e)}",
                error=str(e)
            )
    
    def _format_results(self, data: list, query_type) -> str:
        """Format results based on query type."""
        if not data:
            return ""
        
        format_hint = self.query_classifier.get_format_hint(query_type)
        
        if format_hint == "summary":
            return self.formatter.format_summary(data)
        elif format_hint == "list":
            return self.formatter.format_as_list(data)
        else:
            return self.formatter.format_as_table(data)
    
    def _get_schema(self) -> str:
        """Get or cache schema description for prompts."""
        if self._schema_cache is None:
            self._schema_cache = self.schema_inspector.get_enhanced_schema_for_prompt()
            logger.debug(f"Cached enhanced schema: {len(self._schema_cache)} chars")
        return self._schema_cache
    
    # ==================== OPTIMIZED CONTEXT HANDLING ====================
    
    def _extract_sql_from_message(self, content: str) -> Optional[str]:
        """
        Extract SQL query from message content.
        Handles both inline [SQL Used: ...] format and code blocks.
        """
        # Try to extract from [SQL Used: ...] tag
        sql_match = re.search(r'\[SQL Used:\s*(.+?)\]', content, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Try to extract from code blocks
        code_match = re.search(r'```sql?\n(.+?)\n```', content, re.DOTALL | re.IGNORECASE)
        if code_match:
            return code_match.group(1).strip()
        
        return None
    
    def _extract_key_entities(self, question: str) -> Dict[str, List[str]]:
        """
        Extract key entities from the question for context matching.
        Returns dict with entity types and values.
        """
        entities = {
            'tables': [],
            'columns': [],
            'conditions': [],
            'numbers': []
        }
        
        # Extract potential table names from schema
        for table in self.allowed_tables:
            if table.lower() in question.lower():
                entities['tables'].append(table)
        
        # Extract numbers (useful for "same as before", "top N", etc.)
        numbers = re.findall(r'\b\d+\b', question)
        entities['numbers'].extend(numbers)
        
        # Extract comparison operators and conditions
        conditions = re.findall(r'\b(greater than|less than|equal to|more than|at least|top|bottom|first|last)\b', 
                               question.lower())
        entities['conditions'].extend(conditions)
        
        return entities
    
    def _is_follow_up_question(self, question: str) -> bool:
        """
        Detect if the question is a follow-up that depends on previous context.
        """
        follow_up_indicators = [
            # Reference to previous results
            r'\b(same|similar|those|these|that|them|it)\b',
            r'\b(previous|last|earlier|above)\b',
            
            # Modification requests
            r'\b(also|too|additionally|furthermore)\b',
            r'\b(but|except|without|excluding)\b',
            r'\b(instead|rather than)\b',
            
            # Comparison or extension
            r'\b(compared to|versus|vs|difference)\b',
            r'\b(add|include|show me more)\b',
            
            # Refinement
            r'\b(only|just|specifically)\b',
            r'\b(change|update|modify)\b',
            
            # Direct references
            r'\b(and|with)\b.*\?$',  # "and what about...?"
        ]
        
        question_lower = question.lower()
        
        for pattern in follow_up_indicators:
            if re.search(pattern, question_lower):
                logger.debug(f"Follow-up detected via pattern: {pattern}")
                return True
        
        return False
    
    def _calculate_relevance_score(
        self, 
        current_question: str, 
        past_question: str, 
        past_sql: Optional[str]
    ) -> float:
        """
        Calculate how relevant a past conversation turn is to the current question.
        Returns score between 0.0 and 1.0.
        """
        score = 0.0
        current_lower = current_question.lower()
        past_lower = past_question.lower()
        
        # 1. Check for shared entities (tables, columns)
        current_entities = self._extract_key_entities(current_question)
        past_entities = self._extract_key_entities(past_question)
        
        # Shared tables = high relevance
        shared_tables = set(current_entities['tables']) & set(past_entities['tables'])
        if shared_tables:
            score += 0.4 * min(len(shared_tables) / max(len(current_entities['tables']), 1), 1.0)
        
        # 2. Check for word overlap (simple but effective)
        current_words = set(current_lower.split())
        past_words = set(past_lower.split())
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'what', 'how', 'show', 'me', 'get', 'find'}
        current_words = current_words - stop_words
        past_words = past_words - stop_words
        
        if current_words and past_words:
            overlap = len(current_words & past_words) / len(current_words | past_words)
            score += 0.3 * overlap
        
        # 3. SQL similarity (if past SQL exists)
        if past_sql:
            # Check if current question mentions columns/tables from past SQL
            sql_lower = past_sql.lower()
            sql_entities = re.findall(r'\b(\w+)\b', sql_lower)
            
            current_mentions_sql_entity = any(
                entity in current_lower for entity in sql_entities 
                if len(entity) > 3  # Ignore short words
            )
            
            if current_mentions_sql_entity:
                score += 0.3
        
        return min(score, 1.0)
    
    def _get_history_context(
        self, 
        memory: Optional[ConversationMemory],
        current_question: str = ""
    ) -> str:
        """
        OPTIMIZED: Format conversation history for SQL generation context.
        
        Improvements:
        1. Detects follow-up questions and adjusts context accordingly
        2. Ranks past messages by relevance to current question
        3. Includes more structured SQL information
        4. Better truncation and formatting
        5. Highlights reusable SQL patterns
        
        Returns a string summarizing relevant Q&A pairs to help the LLM
        understand follow-up questions.
        """
        if not memory or memory.is_empty:
            return ""
        
        # Detect if this is a follow-up question
        is_follow_up = self._is_follow_up_question(current_question)
        
        # Adjust how many messages to retrieve based on follow-up detection
        # Follow-ups need more context; standalone questions need less
        n_messages = 10 if is_follow_up else 6
        
        # Get recent messages
        recent = memory.get_recent_history(n=n_messages)
        
        logger.debug(f"[MEMORY_OPTIMIZED] Retrieved {len(recent)} messages for context (follow_up={is_follow_up})")
        
        if not recent:
            return ""
        
        # Score and filter messages by relevance
        scored_messages = []
        for i in range(0, len(recent), 2):  # Process Q&A pairs
            if i + 1 >= len(recent):
                break
            
            user_msg = recent[i]
            assistant_msg = recent[i + 1]
            
            if user_msg['role'] != 'user' or assistant_msg['role'] != 'assistant':
                continue
            
            past_question = user_msg['content']
            past_answer = assistant_msg['content']
            past_sql = assistant_msg.get('metadata', {}).get('sql')
            past_row_count = assistant_msg.get('metadata', {}).get('row_count', 0)
            
            # Calculate relevance
            relevance = self._calculate_relevance_score(
                current_question, 
                past_question, 
                past_sql
            )
            
            # For follow-up questions, keep all recent context
            # For standalone questions, filter by relevance
            if is_follow_up or relevance > 0.2:
                scored_messages.append({
                    'question': past_question,
                    'answer': past_answer,
                    'sql': past_sql,
                    'row_count': past_row_count,
                    'relevance': relevance,
                    'index': i // 2
                })
        
        if not scored_messages:
            return ""
        
        # Sort by relevance (highest first) but keep chronological order for ties
        scored_messages.sort(key=lambda x: (-x['relevance'], -x['index']))
        
        # Take top N most relevant (limit context size)
        max_context_pairs = 3 if is_follow_up else 2
        relevant_messages = scored_messages[:max_context_pairs]
        
        # Re-sort by chronological order for natural flow
        relevant_messages.sort(key=lambda x: x['index'])
        
        # Format context with enhanced structure
        context_parts = []
        
        if is_follow_up:
            context_parts.append(
                "\n=== CONVERSATION CONTEXT (Follow-up detected) ==="
            )
        else:
            context_parts.append(
                "\n=== RELEVANT CONVERSATION HISTORY ==="
            )
        
        for idx, msg in enumerate(relevant_messages, 1):
            # Format question
            context_parts.append(f"\n[Q{idx}] {msg['question']}")
            
            # Format SQL with key details highlighted
            if msg['sql']:
                sql_preview = msg['sql']
                
                # Extract key SQL components for easy reuse
                tables_used = re.findall(r'FROM\s+(\w+)', msg['sql'], re.IGNORECASE)
                where_clause = re.search(r'WHERE\s+(.+?)(?:GROUP BY|ORDER BY|LIMIT|$)', 
                                        msg['sql'], re.IGNORECASE | re.DOTALL)
                order_by = re.search(r'ORDER BY\s+(.+?)(?:LIMIT|$)', 
                                    msg['sql'], re.IGNORECASE)
                limit = re.search(r'LIMIT\s+(\d+)', msg['sql'], re.IGNORECASE)
                
                # Build structured SQL context
                sql_details = []
                if tables_used:
                    sql_details.append(f"Tables: {', '.join(set(tables_used))}")
                if where_clause:
                    sql_details.append(f"Filters: {where_clause.group(1).strip()[:100]}")
                if order_by:
                    sql_details.append(f"Sorting: {order_by.group(1).strip()}")
                if limit:
                    sql_details.append(f"Limit: {limit.group(1)}")
                
                context_parts.append(f"   [SQL Used: {sql_preview}]")
                if sql_details:
                    context_parts.append(f"   [Key Components: {' | '.join(sql_details)}]")
                
                if msg['row_count'] > 0:
                    context_parts.append(f"   [Result: {msg['row_count']} rows returned]")
            
            # Format answer (truncated)
            answer_preview = msg['answer'][:200]
            if len(msg['answer']) > 200:
                answer_preview += "..."
            context_parts.append(f"[A{idx}] {answer_preview}")
        
        context_parts.append("\n=== END OF CONTEXT ===")
        context_parts.append(
            "\nIMPORTANT: If the current question refers to 'same', 'those', 'that', etc., "
            "reuse the relevant SQL filters, tables, and conditions from above.\n"
        )
        
        formatted_context = "\n".join(context_parts)
        
        logger.debug(
            f"[MEMORY_OPTIMIZED] Generated context with {len(relevant_messages)} relevant pairs "
            f"(avg relevance: {sum(m['relevance'] for m in relevant_messages) / len(relevant_messages):.2f})"
        )
        
        return formatted_context
    
    # ==================== END OPTIMIZED CONTEXT HANDLING ====================
    
    def _generate_sql(
        self,
        question: str,
        schema: str,
        history_context: str = ""
    ) -> Tuple[str, Optional[Dict[str, int]]]:
        """Generate SQL from natural language question."""
        system_prompt = get_sql_system_prompt(schema)
        
        # Enhance user prompt with history context
        if history_context:
            # OPTIMIZED: Explicitly link context to the new question to force context awareness
            user_prompt = (
                f"{history_context}\n\n"
                f"═══════════════════════════════════════════════════════════\n"
                f"CURRENT REQUEST (Follow-up)\n"
                f"═══════════════════════════════════════════════════════════\n"
                f"Based on the conversation history above, write a SQL query for the following question.\n"
                f"CRITICAL: Reuse filters, tables, and logic from the history where appropriate (e.g. 'same', 'those', 'only').\n\n"
                f"Question: {question}\n\n"
                f"SQL:"
            )
        else:
            # Default prompt for new questions
            user_prompt = get_sql_user_prompt(question)
        
        logger.debug(f"Generating SQL with LLM (with_context={bool(history_context)})...")
        
        response = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt,
            model=self.settings.llm_model_smart
        )
        
        # Clean up the response
        sql = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```" in sql:
            # Find the first code block
            start = sql.find("```")
            # Check if there's a language tag (e.g., ```sql)
            newline = sql.find("\n", start)
            if newline != -1:
                start = newline + 1
            else:
                start = start + 3 # Fallback if no newline after ```
            
            # Find the end of the block
            end = sql.find("```", start)
            if end != -1:
                sql = sql[start:end]
            else:
                # If no closing block, assume rest of string is code (handles truncation)
                sql = sql[start:]
            
            sql = sql.strip()
        
        logger.info(f"Generated SQL: {sql[:100]}...")
        return sql, response.token_usage
    
    def _generate_answer(
        self,
        question: str,
        sql: str,
        results: list,
        row_count: int,
        insights: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Optional[Dict[str, int]]]:
        """Generate natural language answer from query results."""
        
        # Handle empty results
        if not results or row_count == 0:
            return "No data found matching your query.", None
        
        # STRICT ANALYST MODE: Use the Fast Mode Prompt (Factual, Minimal)
        # Deep analysis (Strategy) is handled separately by InsightsGenerator.
        system_prompt = FAST_MODE_SYSTEM_PROMPT
        
        user_prompt = get_answer_user_prompt(
            question, sql, results, row_count, insights
        )
        
        logger.debug("Generating natural language answer...")
        
        llm_response = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt,
            model=self.settings.llm_model_fast
        )
        
        return llm_response.content.strip(), llm_response.token_usage
    
    def _store_success_in_memory(
        self,
        memory: Optional[ConversationMemory],
        question: str,
        answer: str,
        sql: str,
        row_count: int
    ) -> None:
        """Store successful Q&A in session memory."""
        if not memory:
            return
        
        memory.add_user_message(
            question,
            metadata={"type": "sql_question"}
        )
        memory.add_assistant_message(
            answer,
            metadata={
                "type": "sql_answer",
                "sql": sql,
                "row_count": row_count
            }
        )
    
    def _store_error_in_memory(
        self,
        memory: Optional[ConversationMemory],
        question: str,
        error: str
    ) -> None:
        """Store failed query attempt in memory for context."""
        if not memory:
            return
        
        memory.add_user_message(
            question,
            metadata={"type": "sql_question"}
        )
        memory.add_assistant_message(
            f"I couldn't answer that question. Error: {error}",
            metadata={"type": "sql_error", "error": error}
        )
    
    def _aggregate_results(
        self,
        original_question: str,
        results: List[SQLResponse],
        memory: Optional[ConversationMemory]
    ) -> SQLResponse:
        """Aggregate multiple SQL responses into one."""
        if not results:
             return SQLResponse(
                 success=False, 
                 answer="No results generated.", 
                 sql=None, 
                 data=None, 
                 row_count=0
             )
             
        # Combine answers
        answers = []
        for i, res in enumerate(results):
            if res.success:
                answers.append(f"**Part {i+1}:** {res.answer}")
            else:
                answers.append(f"**Part {i+1}:** {res.answer} (Error: {res.error})")
                
        combined_answer = "\n\n".join(answers)
        
        # Collect SQLs and Data
        sql_queries = [r.sql for r in results if r.sql]
        formatted_data_list = [r.formatted_data for r in results if r.formatted_data]
        
        # Calculate total rows
        total_rows = sum(r.row_count for r in results)
        
        # Aggregate token usage
        total_usage = {}
        for r in results:
            total_usage = self._merge_usage(total_usage, r.token_usage)
        
        # Store aggregared result in memory
        self._store_success_in_memory(
            memory, 
            original_question, 
            combined_answer, 
            sql="; ".join(sql_queries), 
            row_count=total_rows
        )
        
        # For legacy fields (sql, data), we use the first result as a fallback
        primary_sql = sql_queries[0] if sql_queries else None
        primary_data = results[0].data if results and results[0].data else None
        primary_formatted = formatted_data_list[0] if formatted_data_list else None
        
        return SQLResponse(
            success=any(r.success for r in results),
            answer=combined_answer,
            sql=primary_sql,
            data=primary_data,
            row_count=total_rows,
            formatted_data=primary_formatted,
            insights={}, # Aggregated insights is complex, skipping for now
            query_type="multi_query",
            sql_queries=sql_queries,
            formatted_data_list=formatted_data_list,
            token_usage=total_usage
        )
        
    def clear_cache(self) -> None:
        """Clear the schema cache (useful after schema changes)."""
        self._schema_cache = None
        logger.info("SQL service schema cache cleared")


# Singleton instance
_sql_service: SQLService | None = None


def get_sql_service() -> SQLService:
    """Get or create SQL service singleton."""
    global _sql_service
    if _sql_service is None:
        _sql_service = SQLService()
    return _sql_service


def reset_sql_service() -> None:
    """Reset the SQL service singleton (useful for testing)."""
    global _sql_service
    _sql_service = None