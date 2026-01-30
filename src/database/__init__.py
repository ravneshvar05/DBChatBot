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
from src.database.connection_manager import (
    SessionConnectionManager, 
    get_connection_manager,
    DatabaseCredentials,
    ConnectionInfo
)
from src.database.session_helper import (
    ensure_default_connection,
    get_session_components
)
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
    # Connection Manager (new)
    "SessionConnectionManager",
    "get_connection_manager",
    "DatabaseCredentials",
    "ConnectionInfo",
    # Session Helpers (new)
    "ensure_default_connection",
    "get_session_components",
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
