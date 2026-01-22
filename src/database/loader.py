"""
CSV Data Loader - Load CSV files into PostgreSQL.

This module handles:
- Reading CSV files from the data/ directory
- Creating tables with inferred schemas
- Loading data into PostgreSQL
- Progress logging

Why a dedicated loader:
1. One-time data ingestion is separate from query logic
2. Schema inference handles various CSV formats
3. Clear error handling for data issues
"""
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional

from sqlalchemy import text, Table, Column, MetaData, String, Integer, Float, Boolean, DateTime
from sqlalchemy.exc import SQLAlchemyError

from src.database.connection import get_database
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class CSVLoader:
    """
    Loads CSV files into PostgreSQL tables.
    
    This class handles the complete ETL process:
    1. Read CSV file
    2. Infer column types
    3. Create table (drop if exists)
    4. Insert data in batches
    
    Example:
        >>> loader = CSVLoader()
        >>> loader.load_file("data/products.csv", "products")
        >>> loader.load_all_csvs()  # Load all CSVs in data/
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize CSV loader.
        
        Args:
            data_dir: Directory containing CSV files.
                     Defaults to 'data/' in project root.
        """
        self.db = get_database()
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.metadata = MetaData()
        logger.info(f"CSVLoader initialized: data_dir={self.data_dir}")
    
    def load_file(
        self,
        file_path: Path | str,
        table_name: Optional[str] = None,
        drop_existing: bool = True,
        batch_size: int = 1000
    ) -> int:
        """
        Load a CSV file into a PostgreSQL table.
        
        Args:
            file_path: Path to CSV file
            table_name: Target table name (defaults to filename without extension)
            drop_existing: If True, drop existing table before loading
            batch_size: Number of rows to insert per batch
            
        Returns:
            Number of rows loaded
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            SQLAlchemyError: If database operation fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Use filename as table name if not specified
        if table_name is None:
            table_name = file_path.stem.lower().replace(" ", "_").replace("-", "_")
        
        logger.info(f"Loading CSV: {file_path} -> table '{table_name}'")
        
        # Read CSV and infer schema
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            if not headers:
                raise ValueError(f"CSV file has no headers: {file_path}")
            
            # Read all rows to infer types and load data
            rows = list(reader)
        
        if not rows:
            logger.warning(f"CSV file is empty: {file_path}")
            return 0
        
        # Infer column types from data
        column_types = self._infer_column_types(headers, rows)
        
        # Create table
        self._create_table(table_name, column_types, drop_existing)
        
        # Insert data in batches
        row_count = self._insert_data(table_name, headers, rows, batch_size)
        
        logger.info(f"Loaded {row_count} rows into '{table_name}'")
        return row_count
    
    def load_all_csvs(self, drop_existing: bool = True) -> Dict[str, int]:
        """
        Load all CSV files from the data directory.
        
        Args:
            drop_existing: If True, drop existing tables
            
        Returns:
            Dictionary mapping table names to row counts
        """
        results = {}
        csv_files = list(self.data_dir.glob("*.csv"))
        
        if not csv_files:
            logger.warning(f"No CSV files found in {self.data_dir}")
            return results
        
        logger.info(f"Found {len(csv_files)} CSV files to load")
        
        for csv_file in csv_files:
            try:
                table_name = csv_file.stem.lower().replace(" ", "_").replace("-", "_")
                row_count = self.load_file(csv_file, table_name, drop_existing)
                results[table_name] = row_count
            except Exception as e:
                logger.error(f"Failed to load {csv_file}: {e}")
                results[csv_file.stem] = -1  # Mark as failed
        
        logger.info(f"CSV loading complete: {sum(v for v in results.values() if v > 0)} total rows")
        return results
    
    def _infer_column_types(
        self,
        headers: List[str],
        rows: List[Dict[str, str]]
    ) -> Dict[str, type]:
        """
        Infer SQLAlchemy column types from CSV data.
        
        Samples rows to determine the best type for each column.
        Falls back to String for ambiguous types.
        """
        column_types = {}
        
        for header in headers:
            # Sample values from multiple rows
            sample_values = [
                row.get(header, "")
                for row in rows[:100]  # Sample first 100 rows
                if row.get(header, "").strip()
            ]
            
            if not sample_values:
                column_types[header] = String
                continue
            
            # Try to infer type
            column_types[header] = self._infer_type(sample_values)
        
        return column_types
    
    def _infer_type(self, values: List[str]) -> type:
        """Infer the best SQLAlchemy type for a list of values."""
        # Try Integer
        try:
            for v in values:
                int(v)
            return Integer
        except (ValueError, TypeError):
            pass
        
        # Try Float
        try:
            for v in values:
                float(v)
            return Float
        except (ValueError, TypeError):
            pass
        
        # Try Boolean
        bool_values = {'true', 'false', 'yes', 'no', '1', '0', 't', 'f'}
        if all(v.lower() in bool_values for v in values):
            return Boolean
        
        # Default to String
        return String
    
    def _create_table(
        self,
        table_name: str,
        column_types: Dict[str, type],
        drop_existing: bool
    ):
        """Create the table in PostgreSQL."""
        with self.db.get_session() as session:
            # Drop existing table if requested
            if drop_existing:
                session.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
                session.commit()
                logger.debug(f"Dropped existing table '{table_name}'")
            
            # Build column definitions
            columns = []
            for col_name, col_type in column_types.items():
                # Sanitize column name
                safe_name = col_name.lower().replace(" ", "_").replace("-", "_")
                
                # Set appropriate length for String columns
                if col_type == String:
                    columns.append(Column(safe_name, String(500)))
                else:
                    columns.append(Column(safe_name, col_type))
            
            # Create table
            table = Table(table_name, self.metadata, *columns, extend_existing=True)
            table.create(self.db.engine, checkfirst=True)
            
            logger.debug(f"Created table '{table_name}' with {len(columns)} columns")
    
    def _insert_data(
        self,
        table_name: str,
        headers: List[str],
        rows: List[Dict[str, str]],
        batch_size: int
    ) -> int:
        """Insert data in batches for efficiency."""
        # Sanitize header names to match column names
        header_mapping = {
            h: h.lower().replace(" ", "_").replace("-", "_")
            for h in headers
        }
        
        row_count = 0
        
        with self.db.get_session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                
                # Convert rows to use sanitized column names
                clean_batch = []
                for row in batch:
                    clean_row = {
                        header_mapping[k]: self._convert_value(v)
                        for k, v in row.items()
                        if k in header_mapping
                    }
                    clean_batch.append(clean_row)
                
                # Build INSERT statement
                columns = list(header_mapping.values())
                placeholders = ", ".join([f":{col}" for col in columns])
                column_list = ", ".join([f'"{col}"' for col in columns])
                
                insert_sql = text(
                    f'INSERT INTO "{table_name}" ({column_list}) VALUES ({placeholders})'
                )
                
                session.execute(insert_sql, clean_batch)
                row_count += len(batch)
                
                logger.debug(f"Inserted batch: {row_count}/{len(rows)} rows")
            
            session.commit()
        
        return row_count
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate Python type."""
        if not value or value.strip() == "":
            return None
        
        value = value.strip()
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try boolean
        if value.lower() in ('true', 'yes', '1', 't'):
            return True
        if value.lower() in ('false', 'no', '0', 'f'):
            return False
        
        # Return as string
        return value
