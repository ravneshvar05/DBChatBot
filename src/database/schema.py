"""
Schema Inspector - Discover database structure.

This module inspects the PostgreSQL database to discover:
- Available tables
- Column names and types
- Primary keys and constraints

This metadata is used to:
1. Build LLM prompts with schema context
2. Validate generated SQL against allowed tables/columns
3. Provide schema information to users
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from src.database.connection import get_database
from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    type: str
    nullable: bool
    primary_key: bool = False
    default: Any = None


@dataclass
class TableInfo:
    """Information about a database table."""
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    
    def get_column_names(self) -> List[str]:
        """Get list of column names."""
        return [col.name for col in self.columns]


class SchemaInspector:
    """
    Inspects database schema to discover tables and columns.
    
    This class provides methods to:
    - List all tables in the database
    - Get column details for each table
    - Generate schema descriptions for LLM prompts
    
    Example:
        >>> inspector = SchemaInspector()
        >>> tables = inspector.get_all_tables()
        >>> for table in tables:
        ...     print(f"{table.name}: {table.get_column_names()}")
    """
    
    def __init__(self):
        """Initialize schema inspector."""
        self.db = get_database()
        logger.info("SchemaInspector initialized")
    
    def get_table_names(self) -> List[str]:
        """
        Get list of all table names in the database.
        
        Returns:
            List of table names (excluding system tables)
        """
        try:
            inspector = inspect(self.db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Found {len(tables)} tables in database")
            return tables
        except SQLAlchemyError as e:
            logger.error(f"Failed to get table names: {e}")
            raise
    
    def get_table_info(self, table_name: str) -> TableInfo:
        """
        Get detailed information about a specific table.
        
        Args:
            table_name: Name of the table to inspect
            
        Returns:
            TableInfo with columns and row count
        """
        try:
            inspector = inspect(self.db.engine)
            
            # Get column information
            columns = []
            pk_columns = set(inspector.get_pk_constraint(table_name).get('constrained_columns', []))
            
            for col in inspector.get_columns(table_name):
                columns.append(ColumnInfo(
                    name=col['name'],
                    type=str(col['type']),
                    nullable=col.get('nullable', True),
                    primary_key=col['name'] in pk_columns,
                    default=col.get('default'),
                ))
            
            # Get row count (using backticks for MySQL compatibility)
            with self.db.get_session() as session:
                result = session.execute(
                    text(f'SELECT COUNT(*) FROM `{table_name}`')
                )
                row_count = result.scalar()
            
            table_info = TableInfo(
                name=table_name,
                columns=columns,
                row_count=row_count,
            )
            
            logger.debug(f"Table '{table_name}': {len(columns)} columns, {row_count} rows")
            return table_info
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get table info for '{table_name}': {e}")
            raise
    
    def get_all_tables(self) -> List[TableInfo]:
        """
        Get information about all tables in the database.
        
        Returns:
            List of TableInfo objects for all tables
        """
        tables = []
        for table_name in self.get_table_names():
            tables.append(self.get_table_info(table_name))
        return tables
    
    def get_schema_description(self) -> str:
        """
        Generate a human-readable schema description.
        
        This is used in LLM prompts to provide context about
        the database structure.
        
        Returns:
            Formatted string describing all tables and columns
        """
        tables = self.get_all_tables()
        
        if not tables:
            return "No tables found in the database."
        
        lines = ["Database Schema:", "=" * 50]
        
        for table in tables:
            lines.append(f"\nTable: {table.name} ({table.row_count} rows)")
            lines.append("-" * 40)
            
            for col in table.columns:
                pk_marker = " [PK]" if col.primary_key else ""
                null_marker = " (nullable)" if col.nullable else " (required)"
                lines.append(f"  • {col.name}: {col.type}{pk_marker}{null_marker}")
        
        schema_desc = "\n".join(lines)
        logger.debug(f"Generated schema description: {len(lines)} lines")
        return schema_desc
    
    def get_schema_for_prompt(self) -> str:
        """
        Generate a concise schema for LLM prompts.
        
        This is a more compact format optimized for token usage.
        
        Returns:
            Compact schema string for LLM context
        """
        tables = self.get_all_tables()
        
        if not tables:
            return "No tables available."
        
        lines = []
        for table in tables:
            cols = ", ".join([
                f"{col.name} ({col.type})"
                for col in table.columns
            ])
            lines.append(f"TABLE {table.name}: {cols}")
        
        return "\n".join(lines)
