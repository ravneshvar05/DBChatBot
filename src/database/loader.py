"""
CSV Data Loader - Optimized for Large Files.

Key optimizations:
1. Streaming reads (don't load all rows into memory)
2. Larger batch sizes (5000 instead of 1000)
3. Bulk INSERT with executemany
4. Progress logging every batch
5. Schema inference from first N rows only
6. UTF-8 BOM handling
"""
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
from io import StringIO
import re

from sqlalchemy import text, Text, Table, Column, MetaData, String, Integer, Float, Boolean
from sqlalchemy.exc import SQLAlchemyError

from src.database.connection import get_database
from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Optimized settings
BATCH_SIZE = 5000  # Larger batches = fewer DB round-trips
SAMPLE_SIZE = 100  # Rows to sample for type inference


class CSVLoader:
    """
    Loads CSV files into PostgreSQL tables.
    
    Optimized for large files (10k+ rows):
    - Streams CSV instead of loading into memory
    - Uses bulk inserts with large batches
    - Logs progress during loading
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize CSV loader."""
        self.db = get_database()
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data"
        self.metadata = MetaData()
        logger.info(f"CSVLoader initialized: data_dir={self.data_dir}")
    
    def load_file(
        self,
        file_path: Path | str,
        table_name: Optional[str] = None,
        drop_existing: bool = True,
        batch_size: int = BATCH_SIZE
    ) -> int:
        """
        Load a CSV file into PostgreSQL.
        
        Args:
            file_path: Path to CSV file
            table_name: Target table name (defaults to filename)
            drop_existing: Drop existing table before loading
            batch_size: Rows per batch insert
            
        Returns:
            Number of rows loaded
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        if table_name is None:
            # Sanitize table name: remove special chars, keep only alphanumeric and underscores
            raw_name = file_path.stem.lower()
            # Remove everything in parentheses, brackets, etc.
            raw_name = re.sub(r'[\(\)\[\]\{\}]', '', raw_name)
            # Replace spaces, hyphens with underscores
            raw_name = raw_name.replace(" ", "_").replace("-", "_")
            # Remove any remaining special characters
            table_name = re.sub(r'[^a-z0-9_]', '', raw_name)
            # Ensure it doesn't start with a number
            if table_name and table_name[0].isdigit():
                table_name = 't_' + table_name
        
        logger.info(f"Loading CSV: {file_path.name} -> table '{table_name}'")
        
        # Step 1: Read headers and sample rows for schema inference
        headers, sample_rows, total_estimate = self._read_headers_and_sample(file_path)
        
        if not headers:
            raise ValueError(f"No valid headers in CSV: {file_path}")
        
        logger.info(f"Found {len(headers)} columns, ~{total_estimate} rows estimated")
        
        # Step 2: Infer column types from sample
        column_types = self._infer_column_types(headers, sample_rows)
        
        # Step 3: Create table
        self._create_table(table_name, column_types, drop_existing)
        
        # Step 4: Stream and insert data
        row_count = self._stream_insert(file_path, table_name, headers, batch_size)
        
        logger.info(f"✓ Loaded {row_count:,} rows into '{table_name}'")
        return row_count
    
    def load_all_csvs(self, drop_existing: bool = True) -> Dict[str, int]:
        """Load all CSV files from the data directory."""
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
                logger.error(f"Failed to load {csv_file.name}: {e}")
                results[csv_file.stem] = -1
        
        total = sum(v for v in results.values() if v > 0)
        logger.info(f"CSV loading complete: {total:,} total rows")
        return results
    
    def _read_headers_and_sample(
        self, 
        file_path: Path
    ) -> tuple[List[str], List[Dict], int]:
        """Read headers and sample rows without loading entire file."""
        # Get file size for estimation
        file_size = file_path.stat().st_size
        
        # Use utf-8-sig to handle BOM automatically
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            raw_headers = reader.fieldnames or []
            
            # Filter empty headers and strip BOM/whitespace
            headers = [h.strip().lstrip('\ufeff') for h in raw_headers if h and h.strip()]
            
            # Read sample rows
            sample_rows = []
            for i, row in enumerate(reader):
                if i >= SAMPLE_SIZE:
                    break
                sample_rows.append(row)
        
        # Estimate total rows based on file size
        if sample_rows:
            # Rough estimate: file_size / avg_row_size
            avg_row_size = file_size / (len(sample_rows) * 10)  # Conservative estimate
            total_estimate = max(len(sample_rows), int(file_size / max(avg_row_size, 100)))
        else:
            total_estimate = 0
        
        return headers, sample_rows, total_estimate
    
    def _infer_column_types(
        self,
        headers: List[str],
        rows: List[Dict[str, str]]
    ) -> Dict[str, type]:
        """Infer column types from sample rows."""
        column_types = {}
        
        for header in headers:
            sample_values = [
                row.get(header, "")
                for row in rows
                if row.get(header, "").strip()
            ][:50]  # Use first 50 non-empty values
            
            if not sample_values:
                column_types[header] = String
                continue
            
            column_types[header] = self._infer_type(sample_values)
        
        return column_types
    
    def _infer_type(self, values: List[str]) -> type:
        """Infer SQLAlchemy type for a list of values."""
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
        
        return String
    
    def _create_table(
        self,
        table_name: str,
        column_types: Dict[str, type],
        drop_existing: bool
    ):
        """Create table in database (MySQL/PostgreSQL compatible)."""
        with self.db.get_session() as session:
            if drop_existing:
                # Use simple DROP TABLE without CASCADE for MySQL compatibility
                session.execute(text(f'DROP TABLE IF EXISTS `{table_name}`'))
                session.commit()
                logger.debug(f"Dropped existing table '{table_name}'")
            
            columns = []
            
            # FIX: Add Primary Key for Cloud Databases (DigitalOcean/Aiven requirement)
            # using Integer + primary_key=True + autoincrement=True
            columns.append(Column('id', Integer, primary_key=True, autoincrement=True))
            
            for col_name, col_type in column_types.items():
                if not col_name or not col_name.strip():
                    continue
                
                safe_name = col_name.lower().replace(" ", "_").replace("-", "_")
                if not safe_name:
                    safe_name = f"col_{len(columns)}"
                
                if col_type == String:
                    # Use Text instead of String(2000) to avoid MySQL row size limits
                    columns.append(Column(safe_name, Text))
                else:
                    columns.append(Column(safe_name, col_type))
            
            if not columns:
                raise ValueError("No valid columns to create")
            
            table = Table(table_name, self.metadata, *columns, extend_existing=True)
            table.create(self.db.engine, checkfirst=True)
            
            logger.info(f"Created table '{table_name}' with {len(columns)} columns")
    
    def _stream_insert(
        self,
        file_path: Path,
        table_name: str,
        headers: List[str],
        batch_size: int
    ) -> int:
        """Stream CSV and insert in batches."""
        # Build column mapping
        header_mapping = {
            h: h.lower().replace(" ", "_").replace("-", "_")
            for h in headers
            if h and h.strip()
        }
        
        columns = list(header_mapping.values())
        # Use backticks for MySQL compatibility
        column_list = ", ".join([f'`{col}`' for col in columns])
        placeholders = ", ".join([f":{col}" for col in columns])
        
        insert_sql = text(
            f'INSERT INTO `{table_name}` ({column_list}) VALUES ({placeholders})'
        )
        
        row_count = 0
        batch = []
        
        # Use utf-8-sig to handle BOM automatically
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Convert row
                clean_row = {}
                for orig_header, safe_name in header_mapping.items():
                    value = row.get(orig_header, "")
                    clean_row[safe_name] = self._convert_value(value)
                
                batch.append(clean_row)
                
                # Insert batch when full
                if len(batch) >= batch_size:
                    self._execute_batch(insert_sql, batch)
                    row_count += len(batch)
                    logger.info(f"  Progress: {row_count:,} rows inserted...")
                    batch = []
            
            # Insert remaining rows
            if batch:
                self._execute_batch(insert_sql, batch)
                row_count += len(batch)
        
        return row_count
    
    def _execute_batch(self, insert_sql, batch: List[Dict]):
        """Execute batch insert."""
        with self.db.get_session() as session:
            session.execute(insert_sql, batch)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string to appropriate Python type."""
        if not value or value.strip() == "":
            return None
        
        value = value.strip()
        
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        return value
