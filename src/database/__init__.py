"""
Database module - PostgreSQL access layer.

This module handles:
- Database connection management
- Schema inspection
- Query execution (read-only)
- CSV data loading
"""
from src.database.connection import DatabaseConnection, get_database
from src.database.schema import SchemaInspector, TableInfo, ColumnInfo
from src.database.loader import CSVLoader
from src.database.executor import QueryExecutor, QueryResult

__all__ = [
    # Connection
    "DatabaseConnection",
    "get_database",
    # Schema
    "SchemaInspector",
    "TableInfo",
    "ColumnInfo",
    # Loader
    "CSVLoader",
    # Executor
    "QueryExecutor",
    "QueryResult",
]
