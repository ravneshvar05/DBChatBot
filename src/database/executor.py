"""
Query Executor - Safe SQL query execution.

This module provides:
- Read-only query execution
- Query timing and logging
- Result formatting
- Safety checks (Phase 3 will add SQL validation)

Why a dedicated executor:
1. Centralized query logging
2. Consistent result formatting
3. Performance monitoring
4. Future: SQL validation layer
"""
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.database.connection import get_database
from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """
    Result of a database query.
    
    Attributes:
        success: Whether the query executed successfully
        data: List of rows as dictionaries
        row_count: Number of rows returned
        columns: List of column names
        execution_time_ms: Query execution time in milliseconds
        error: Error message if query failed
    """
    success: bool
    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float
    error: Optional[str] = None


class QueryExecutor:
    """
    Executes SQL queries safely with logging and timing.
    
    This class provides a controlled interface for query execution:
    - All queries are logged
    - Execution time is measured
    - Results are formatted consistently
    - Errors are captured cleanly
    
    Example:
        >>> executor = QueryExecutor()
        >>> result = executor.execute("SELECT * FROM products LIMIT 10")
        >>> if result.success:
        ...     for row in result.data:
        ...         print(row)
    """
    
    def __init__(self):
        """Initialize query executor."""
        self.db = get_database()
        logger.info("QueryExecutor initialized")
    
    def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 30.0
    ) -> QueryResult:
        """
        Execute a SQL query and return results.
        
        Args:
            sql: SQL query string
            params: Optional parameters for parameterized queries
            timeout_seconds: Query timeout (not enforced in Phase 2)
            
        Returns:
            QueryResult with data or error
            
        Note:
            In Phase 3, this will validate SQL before execution.
            For now, it executes any valid SQL.
        """
        logger.info(f"Executing query: {sql[:100]}...")
        
        start_time = time.perf_counter()
        
        try:
            with self.db.get_session() as session:
                # Execute query
                if params:
                    result = session.execute(text(sql), params)
                else:
                    result = session.execute(text(sql))
                
                # Fetch results
                rows = result.fetchall()
                columns = list(result.keys()) if result.keys() else []
                
                # Convert to list of dicts
                data = [
                    dict(zip(columns, row))
                    for row in rows
                ]
            
            execution_time = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                f"Query completed: {len(data)} rows in {execution_time:.2f}ms"
            )
            
            return QueryResult(
                success=True,
                data=data,
                row_count=len(data),
                columns=columns,
                execution_time_ms=execution_time,
            )
            
        except SQLAlchemyError as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_msg = str(e)
            
            logger.error(f"Query failed: {error_msg}")
            
            return QueryResult(
                success=False,
                data=[],
                row_count=0,
                columns=[],
                execution_time_ms=execution_time,
                error=error_msg,
            )
    
    def execute_with_limit(
        self,
        sql: str,
        limit: int = 100,
        params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute a query with enforced LIMIT.
        
        This is a safety measure to prevent accidentally
        returning massive result sets.
        
        Args:
            sql: SQL query string
            limit: Maximum rows to return
            params: Optional query parameters
            
        Returns:
            QueryResult with at most `limit` rows
        """
        # Simple LIMIT enforcement (will be improved in Phase 3)
        sql_upper = sql.upper().strip()
        
        if "LIMIT" not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {limit}"
            logger.debug(f"Added LIMIT {limit} to query")
        
        return self.execute(sql, params)
