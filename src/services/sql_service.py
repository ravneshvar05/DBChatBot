"""
SQL Service - Orchestrates Text-to-SQL operations.

This service handles the complete flow:
1. Get schema context
2. Generate SQL from natural language
3. Validate the SQL
4. Execute the query
5. Format results with natural language answer

This is the main entry point for text-to-SQL functionality.
"""
from typing import Optional
from dataclasses import dataclass

from src.core.logging_config import get_logger
from src.database import get_database, SchemaInspector, QueryExecutor
from src.database.validator import SQLValidator, ValidationResult
from src.llm.client import LLMClient, LLMError
from src.llm.prompts import (
    get_sql_system_prompt,
    get_sql_user_prompt,
    get_answer_system_prompt,
    get_answer_user_prompt,
)

logger = get_logger(__name__)


@dataclass
class SQLResponse:
    """
    Response from SQL service.
    
    Includes both the generated SQL and natural language answer.
    """
    success: bool
    answer: str  # Natural language answer
    sql: Optional[str] = None  # Generated SQL
    data: Optional[list] = None  # Query results
    row_count: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "answer": self.answer,
            "sql": self.sql,
            "data": self.data,
            "row_count": self.row_count,
            "error": self.error,
        }


class SQLService:
    """
    Service for converting natural language to SQL and executing queries.
    
    Example:
        >>> service = SQLService()
        >>> response = service.query("What are the top 5 movies?")
        >>> print(response.answer)
        "The top 5 highest rated movies are..."
        >>> print(response.sql)
        "SELECT title, vote_average FROM movies ORDER BY vote_average DESC LIMIT 5"
    """
    
    def __init__(self):
        """Initialize SQL service with required components."""
        self.llm = LLMClient()
        self.executor = QueryExecutor()
        self.schema_inspector = SchemaInspector()
        
        # Get allowed tables from database
        self.allowed_tables = set(self.schema_inspector.get_table_names())
        self.validator = SQLValidator(allowed_tables=self.allowed_tables)
        
        # Cache schema for prompts
        self._schema_cache = None
        
        logger.info(f"SQLService initialized with {len(self.allowed_tables)} tables")
    
    def query(self, question: str) -> SQLResponse:
        """
        Process a natural language question and return results.
        
        Args:
            question: User's natural language question
            
        Returns:
            SQLResponse with answer, SQL, and data
        """
        logger.info(f"Processing SQL query: {question[:50]}...")
        
        try:
            # Step 1: Get schema context
            schema = self._get_schema()
            
            # Step 2: Generate SQL from question
            sql = self._generate_sql(question, schema)
            
            if sql.startswith("ERROR:"):
                return SQLResponse(
                    success=False,
                    answer=f"I couldn't generate a query for that question. {sql}",
                    error=sql
                )
            
            # Step 3: Validate SQL
            validation = self.validator.validate(sql)
            
            if not validation.is_valid:
                logger.warning(f"SQL validation failed: {validation.error}")
                return SQLResponse(
                    success=False,
                    answer=f"I generated a query but it didn't pass safety checks. {validation.error}",
                    sql=sql,
                    error=validation.error
                )
            
            # Use validated (possibly modified) SQL
            sql = validation.sql
            
            # Step 4: Execute query
            result = self.executor.execute(sql)
            
            if not result.success:
                logger.error(f"Query execution failed: {result.error}")
                return SQLResponse(
                    success=False,
                    answer="The query failed to execute. Please try rephrasing your question.",
                    sql=sql,
                    error=result.error
                )
            
            # Step 5: Generate natural language answer
            answer = self._generate_answer(question, sql, result.data, result.row_count)
            
            logger.info(f"SQL query successful: {result.row_count} rows returned")
            
            return SQLResponse(
                success=True,
                answer=answer,
                sql=sql,
                data=result.data,
                row_count=result.row_count
            )
            
        except LLMError as e:
            logger.error(f"LLM error in SQL service: {e}")
            return SQLResponse(
                success=False,
                answer="I'm having trouble connecting to the AI service. Please try again.",
                error=str(e)
            )
        except Exception as e:
            logger.exception(f"Unexpected error in SQL service: {e}")
            return SQLResponse(
                success=False,
                answer="An unexpected error occurred. Please try again.",
                error=str(e)
            )
    
    def _get_schema(self) -> str:
        """Get or cache schema description for prompts."""
        if self._schema_cache is None:
            self._schema_cache = self.schema_inspector.get_schema_for_prompt()
            logger.debug(f"Cached schema: {len(self._schema_cache)} chars")
        return self._schema_cache
    
    def _generate_sql(self, question: str, schema: str) -> str:
        """Generate SQL from natural language question."""
        system_prompt = get_sql_system_prompt(schema)
        user_prompt = get_sql_user_prompt(question)
        
        logger.debug("Generating SQL with LLM...")
        
        response = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt
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
        row_count: int
    ) -> str:
        """Generate natural language answer from query results."""
        
        # Handle empty results
        if not results or row_count == 0:
            return "No data found matching your query."
        
        system_prompt = get_answer_system_prompt()
        user_prompt = get_answer_user_prompt(question, sql, results, row_count)
        
        logger.debug("Generating natural language answer...")
        
        answer = self.llm.generate(
            user_message=user_prompt,
            system_prompt=system_prompt
        )
        
        return answer.strip()


# Singleton instance
_sql_service: SQLService | None = None


def get_sql_service() -> SQLService:
    """Get or create SQL service singleton."""
    global _sql_service
    if _sql_service is None:
        _sql_service = SQLService()
    return _sql_service
