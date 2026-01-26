"""
Database module - PostgreSQL/MySQL access layer.

This module handles:
- Database connection management
- Schema inspection
- Query execution (read-only)
- CSV data loading
- SQL validation
- Conversation persistence (Phase 6)
"""
from src.database.connection import DatabaseConnection, get_database
from src.database.schema import SchemaInspector, TableInfo, ColumnInfo
from src.database.loader import CSVLoader
from src.database.executor import QueryExecutor, QueryResult
from src.database.validator import SQLValidator, ValidationResult
from src.database.models import ConversationSession, ConversationMessage, Base
from src.database.init_db import init_conversation_tables, drop_conversation_tables

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
    # Validator
    "SQLValidator",
    "ValidationResult",
    # Models (Phase 6)
    "ConversationSession",
    "ConversationMessage",
    "Base",
    # Init
    "init_conversation_tables",
    "drop_conversation_tables",
]
