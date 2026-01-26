"""
SQL Validator - Ensures generated SQL is safe to execute.

This module validates SQL queries for:
- SELECT statements only (no mutations)
- Allowed tables/columns (whitelist)
- Mandatory LIMIT clause
- SQL injection prevention

Why validation is critical:
1. LLM can generate unsafe SQL
2. Users might try prompt injection
3. Mistakes can expose/modify data
"""
import re
from typing import List, Set, Optional
from dataclasses import dataclass

from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Dangerous SQL keywords that should NEVER appear
FORBIDDEN_KEYWORDS = {
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
    'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'MERGE', 'REPLACE',
    'INTO OUTFILE', 'INTO DUMPFILE', 'LOAD_FILE'
}

# Maximum rows to return
MAX_LIMIT = 100
DEFAULT_LIMIT = 50


@dataclass
class ValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    sql: str  # Possibly modified SQL (with LIMIT added)
    error: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SQLValidator:
    """
    Validates SQL queries for safety before execution.
    
    This validator ensures:
    1. Only SELECT statements are allowed
    2. Only allowed tables are queried
    3. LIMIT clause is present (adds one if missing)
    4. No dangerous SQL keywords
    
    Example:
        >>> validator = SQLValidator(allowed_tables={'movies'})
        >>> result = validator.validate("SELECT * FROM movies")
        >>> if result.is_valid:
        ...     print(result.sql)  # "SELECT * FROM movies LIMIT 50"
    """
    
    def __init__(self, allowed_tables: Set[str] = None):
        """
        Initialize validator with allowed tables.
        
        Args:
            allowed_tables: Set of table names that can be queried.
                          If None, all tables are allowed.
        """
        self.allowed_tables = allowed_tables or set()
        logger.info(f"SQLValidator initialized with {len(self.allowed_tables)} allowed tables")
    
    def validate(self, sql: str) -> ValidationResult:
        """
        Validate an SQL query for safety.
        
        Args:
            sql: The SQL query to validate
            
        Returns:
            ValidationResult with is_valid, sql (possibly modified), error message
        """
        if not sql or not sql.strip():
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error="Empty SQL query"
            )
        
        sql = sql.strip()
        
        # Remove trailing semicolon
        if sql.endswith(';'):
            sql = sql[:-1].strip()
        
        warnings = []
        
        # Check 1: Must start with SELECT
        if not self._is_select_only(sql):
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error="Only SELECT statements are allowed"
            )
        
        # Check 2: No forbidden keywords
        forbidden = self._check_forbidden_keywords(sql)
        if forbidden:
            return ValidationResult(
                is_valid=False,
                sql=sql,
                error=f"Forbidden SQL keyword detected: {forbidden}"
            )
        
        # Check 3: Validate tables (if whitelist is set)
        if self.allowed_tables:
            table_error = self._check_allowed_tables(sql)
            if table_error:
                return ValidationResult(
                    is_valid=False,
                    sql=sql,
                    error=table_error
                )
        
        # Check 4: Ensure LIMIT exists
        sql, limit_added = self._ensure_limit(sql)
        if limit_added:
            warnings.append(f"Added LIMIT {DEFAULT_LIMIT} for safety")
        
        logger.info(f"SQL validation passed: {sql[:50]}...")
        
        return ValidationResult(
            is_valid=True,
            sql=sql,
            warnings=warnings
        )
    
    def _is_select_only(self, sql: str) -> bool:
        """Check if SQL is a SELECT statement."""
        sql_upper = sql.upper().strip()
        return sql_upper.startswith('SELECT')
    
    def _check_forbidden_keywords(self, sql: str) -> Optional[str]:
        """Check for forbidden keywords. Returns the keyword if found."""
        sql_upper = sql.upper()
        
        for keyword in FORBIDDEN_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                logger.warning(f"Forbidden keyword detected: {keyword}")
                return keyword
        
        return None
    
    def _check_allowed_tables(self, sql: str) -> Optional[str]:
        """
        Check if only allowed tables are used.
        Returns error message if invalid table found.
        """
        # Regex to handle quoted (`table`) and unquoted (table) names
        # Captures: 1=backticked, 2=double-quoted, 3=unquoted
        table_pattern = r'\b(?:FROM|JOIN)\s+(?:`([^`]+)`|"([^"]+)"|([a-zA-Z0-9_]+))'
        
        tables_found = set()
        
        # Case-insensitive search on the original SQL to preserve case in quotes
        # (though we lower() later, it's safer to parse original)
        for match in re.finditer(table_pattern, sql, re.IGNORECASE):
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                tables_found.add(name.lower())
        
        # Check against whitelist
        allowed_lower = {t.lower() for t in self.allowed_tables}
        invalid_tables = tables_found - allowed_lower
        
        if invalid_tables:
            return f"Table not allowed: {', '.join(invalid_tables)}"
        
        return None
    
    def _ensure_limit(self, sql: str) -> tuple[str, bool]:
        """
        Ensure SQL has a LIMIT clause.
        
        Returns:
            Tuple of (sql, was_limit_added)
        """
        sql_upper = sql.upper()
        
        # Check if LIMIT already exists
        if 'LIMIT' in sql_upper:
            # Validate the limit value isn't too high
            limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
            if limit_match:
                limit_value = int(limit_match.group(1))
                if limit_value > MAX_LIMIT:
                    # Replace with max limit
                    sql = re.sub(
                        r'\bLIMIT\s+\d+',
                        f'LIMIT {MAX_LIMIT}',
                        sql,
                        flags=re.IGNORECASE
                    )
                    logger.warning(f"Reduced LIMIT from {limit_value} to {MAX_LIMIT}")
            return sql, False
        
        # Add LIMIT
        sql = f"{sql} LIMIT {DEFAULT_LIMIT}"
        return sql, True
