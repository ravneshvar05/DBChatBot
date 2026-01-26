"""
SQL Service - Orchestrates Text-to-SQL operations with memory and analytics.

This service handles the complete flow:
1. Get schema context
2. Retrieve conversation history for context
3. Generate SQL from natural language
4. Validate the SQL
5. Execute the query
6. Analyze results and generate insights (Phase 5)
7. Format data for display (Phase 5)
8. Store Q&A in session memory
9. Format results with natural language answer

This is the main entry point for text-to-SQL functionality.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from src.core.logging_config import get_logger
from src.core.config import get_settings
from src.database import get_database, SchemaInspector, QueryExecutor
from src.database.validator import SQLValidator, ValidationResult
from src.llm.client import LLMClient, LLMError
from src.llm.prompts import (
    get_sql_system_prompt,
    get_sql_user_prompt,
    get_answer_system_prompt,
    get_answer_user_prompt,
)
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
            history_context = self._get_history_context(memory)
            


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
            sql = self._generate_sql(question, schema, history_context)
            
            if sql.startswith("ERROR:"):
                if store_memory:
                    self._store_error_in_memory(memory, question, sql)
                return SQLResponse(
                    success=False,
                    answer=f"I couldn't generate a query for that question. {sql}",
                    error=sql
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
            answer = self._generate_answer(
                question, sql, result.data, result.row_count, insights
            )
            
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
                query_type=query_type.value
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
    
    def _get_history_context(self, memory: Optional[ConversationMemory]) -> str:
        """
        Format conversation history for SQL generation context.
        
        Returns a string summarizing recent Q&A pairs to help the LLM
        understand follow-up questions.
        """
        if not memory or memory.is_empty:
            return ""
        
        # Get recent messages (last 6 = 3 Q&A pairs)
        recent = memory.get_recent_history(n=6)
        
        if not recent:
            return ""
        
        # Format as conversation context
        context_parts = ["\n--- Previous conversation context ---"]
        
        for msg in recent:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long responses for context
            content = msg["content"][:300]
            if len(msg["content"]) > 300:
                content += "..."
            context_parts.append(f"{role_label}: {content}")
        
        context_parts.append("--- End of context ---\n")
        
        return "\n".join(context_parts)
    
    def _generate_sql(
        self,
        question: str,
        schema: str,
        history_context: str = ""
    ) -> str:
        """Generate SQL from natural language question."""
        system_prompt = get_sql_system_prompt(schema)
        
        # Enhance user prompt with history context
        user_prompt = get_sql_user_prompt(question)
        if history_context:
            user_prompt = f"{history_context}\nCurrent question: {user_prompt}"
        
        logger.debug(f"Generating SQL with LLM (with_context={bool(history_context)})...")
        
        response = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt,
            model=self.settings.llm_model_smart
        )
        
        # Clean up the response
        sql = response.strip()
        
        # Remove markdown code blocks if present
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(lines[1:-1]) if len(lines) > 2 else sql
            sql = sql.strip()
        
        logger.info(f"Generated SQL: {sql[:100]}...")
        return sql
    
    def _generate_answer(
        self,
        question: str,
        sql: str,
        results: list,
        row_count: int,
        insights: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate natural language answer from query results."""
        
        # Handle empty results
        if not results or row_count == 0:
            return "No data found matching your query."
        
        system_prompt = get_answer_system_prompt()
        user_prompt = get_answer_user_prompt(
            question, sql, results, row_count, insights
        )
        
        logger.debug("Generating natural language answer...")
        
        answer = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt,
            model=self.settings.llm_model_smart
        )
        
        return answer.strip()
    
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
            formatted_data_list=formatted_data_list
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
