"""
Analytics Package - Data analysis and formatting utilities.

This package provides:
- ResultFormatter: Format query results as tables/lists
- InsightsGenerator: Generate automatic statistics and insights
- QueryClassifier: Detect query intent for appropriate formatting

Example:
    >>> from src.analytics import ResultFormatter, InsightsGenerator, QueryClassifier
    >>> 
    >>> classifier = QueryClassifier()
    >>> query_type = classifier.classify("SELECT ... ORDER BY ... LIMIT 5")
    >>> 
    >>> generator = InsightsGenerator()
    >>> insights = generator.generate_insights(data, query_type.value)
    >>> 
    >>> formatter = ResultFormatter()
    >>> table = formatter.format_as_table(data)
"""
from src.analytics.formatter import ResultFormatter
from src.analytics.insights import InsightsGenerator
from src.analytics.query_classifier import QueryClassifier, QueryType

__all__ = [
    "ResultFormatter",
    "InsightsGenerator",
    "QueryClassifier",
    "QueryType",
]
