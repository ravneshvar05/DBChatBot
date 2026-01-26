"""
Query Classifier - Detect query intent and type.

This module analyzes SQL queries to classify them into categories:
- aggregation: COUNT, SUM, AVG queries
- ranking: ORDER BY with LIMIT
- comparison: WHERE with conditions
- lookup: Simple SELECT
- distribution: GROUP BY queries

The classification helps format responses appropriately.
"""
import re
from typing import Optional
from enum import Enum

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class QueryType(str, Enum):
    """Types of SQL queries."""
    AGGREGATION = "aggregation"  # COUNT, SUM, AVG
    RANKING = "ranking"          # ORDER BY + LIMIT
    COMPARISON = "comparison"    # WHERE filtering
    LOOKUP = "lookup"            # Simple SELECT
    DISTRIBUTION = "distribution"  # GROUP BY
    UNKNOWN = "unknown"


class QueryClassifier:
    """
    Classifies SQL queries by their intent.
    
    Used to determine the best way to format and present results.
    
    Example:
        >>> classifier = QueryClassifier()
        >>> query_type = classifier.classify(
        ...     "SELECT title FROM movies ORDER BY rating DESC LIMIT 5"
        ... )
        >>> print(query_type)
        QueryType.RANKING
    """
    
    # Regex patterns for classification
    AGGREGATION_PATTERN = re.compile(
        r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(',
        re.IGNORECASE
    )
    RANKING_PATTERN = re.compile(
        r'ORDER\s+BY\s+.+\s+(DESC|ASC)',
        re.IGNORECASE
    )
    DISTRIBUTION_PATTERN = re.compile(
        r'\bGROUP\s+BY\b',
        re.IGNORECASE
    )
    LIMIT_PATTERN = re.compile(
        r'\bLIMIT\s+(\d+)',
        re.IGNORECASE
    )
    WHERE_PATTERN = re.compile(
        r'\bWHERE\b',
        re.IGNORECASE
    )
    
    def classify(self, sql: str) -> QueryType:
        """
        Classify a SQL query by its type.
        
        Args:
            sql: The SQL query string
            
        Returns:
            QueryType enum value
        """
        if not sql:
            return QueryType.UNKNOWN
        
        sql_upper = sql.upper()
        
        # Check for aggregation functions
        if self.AGGREGATION_PATTERN.search(sql):
            # Pure aggregation without GROUP BY
            if not self.DISTRIBUTION_PATTERN.search(sql):
                return QueryType.AGGREGATION
        
        # Check for GROUP BY (distribution query)
        if self.DISTRIBUTION_PATTERN.search(sql):
            return QueryType.DISTRIBUTION
        
        # Check for ranking (ORDER BY with small LIMIT)
        if self.RANKING_PATTERN.search(sql):
            limit_match = self.LIMIT_PATTERN.search(sql)
            if limit_match:
                limit_val = int(limit_match.group(1))
                if limit_val <= 20:
                    return QueryType.RANKING
        
        # Check for comparison (WHERE clause)
        if self.WHERE_PATTERN.search(sql):
            return QueryType.COMPARISON
        
        # Default to lookup
        return QueryType.LOOKUP
    
    def get_format_hint(self, query_type: QueryType) -> str:
        """
        Get formatting hint based on query type.
        
        Args:
            query_type: The classified query type
            
        Returns:
            Format hint: 'table', 'list', or 'summary'
        """
        hints = {
            QueryType.AGGREGATION: "summary",
            QueryType.RANKING: "list",
            QueryType.DISTRIBUTION: "table",
            QueryType.COMPARISON: "table",
            QueryType.LOOKUP: "table",
            QueryType.UNKNOWN: "table"
        }
        return hints.get(query_type, "table")
    
    def get_description(self, query_type: QueryType) -> str:
        """
        Get human-readable description of query type.
        
        Args:
            query_type: The classified query type
            
        Returns:
            Description string
        """
        descriptions = {
            QueryType.AGGREGATION: "Aggregation query (counting/summing data)",
            QueryType.RANKING: "Ranking query (finding top/bottom items)",
            QueryType.DISTRIBUTION: "Distribution query (grouping data)",
            QueryType.COMPARISON: "Comparison query (filtering by condition)",
            QueryType.LOOKUP: "Lookup query (retrieving records)",
            QueryType.UNKNOWN: "Unknown query type"
        }
        return descriptions.get(query_type, "Unknown")
