"""
Database Routes - API endpoints for database operations.

These endpoints allow:
- Uploading CSV files
- Loading CSV data into database
- Inspecting database schema
- Testing queries (development only)
"""
import shutil
from pathlib import Path
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.core.config import get_settings
from src.core.logging_config import get_logger
from src.database import (
    CSVLoader,
    SchemaInspector,
    QueryExecutor,
    get_database,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/database",
    tags=["Database"],
)

# Data directory for CSV files
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


# Response models
class TableSchema(BaseModel):
    """Schema information for a single table."""
    name: str
    columns: List[Dict[str, Any]]
    row_count: int


class SchemaResponse(BaseModel):
    """Response containing database schema."""
    tables: List[TableSchema]
    table_count: int


class LoadResponse(BaseModel):
    """Response from CSV loading operation."""
    tables_loaded: Dict[str, int]
    total_rows: int
    message: str


class UploadResponse(BaseModel):
    """Response from file upload."""
    filename: str
    table_name: str
    message: str
    rows_loaded: int


class QueryRequest(BaseModel):
    """Request to execute a test query."""
    sql: str = Field(..., description="SQL query to execute")
    limit: int = Field(default=100, le=1000, description="Maximum rows to return")


class QueryResponse(BaseModel):
    """Response from query execution."""
    success: bool
    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float
    error: str | None = None


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and load a CSV file",
    description="""
    Upload a CSV file and load it into the session's connected database.
    
    The file will be:
    1. Saved to the data/ directory
    2. Automatically loaded into a database table
    
    The table name is derived from the filename (e.g., products.csv → products table).
    """
)
async def upload_csv(
    session_id: str,
    file: UploadFile = File(..., description="CSV file to upload")
) -> UploadResponse:
    """Upload a CSV file and load it into the session's database."""
    
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )
    
    # Sanitize filename
    safe_filename = file.filename.replace(" ", "_").lower()
    file_path = DATA_DIR / safe_filename
    
    logger.info(f"Uploading CSV for session {session_id}: {safe_filename}")
    
    try:
        from src.database import get_session_components
        
        # Get session-specific components
        db_conn, inspector, executor, loader = get_session_components(session_id)
        
        if loader is None:
            raise HTTPException(
                status_code=400,
                detail="No database connection found. Please connect to a database first."
            )
        
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Saved file to: {file_path}")
        
        # Load into database using session connection
        table_name = file_path.stem.lower().replace(" ", "_").replace("-", "_")
        
        # Check if table already exists
        existing_tables = inspector.get_table_names()
        
        if table_name in existing_tables:
            # Don't overwrite - return error
            raise HTTPException(
                status_code=409,  # Conflict
                detail=f"Table '{table_name}' already exists. Delete it first or use a different filename."
            )
        
        rows_loaded = loader.load_file(file_path, table_name, drop_existing=False)
        
        return UploadResponse(
            filename=safe_filename,
            table_name=table_name,
            message=f"Successfully loaded {rows_loaded} rows into table '{table_name}'",
            rows_loaded=rows_loaded
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # Clean up file if loading failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()


@router.get(
    "/files",
    summary="List uploaded CSV files",
    description="Returns a list of CSV files in the data directory."
)
async def list_files() -> Dict[str, Any]:
    """List all CSV files in the data directory."""
    try:
        files = []
        for f in DATA_DIR.glob("*.csv"):
            files.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "table_name": f.stem.lower().replace(" ", "_").replace("-", "_")
            })
        
        return {
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/files/{filename}",
    summary="Delete a CSV file",
    description="Delete a CSV file from the data directory."
)
async def delete_file(filename: str) -> Dict[str, str]:
    """Delete a CSV file."""
    file_path = DATA_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    if not filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files can be deleted")
    
    try:
        file_path.unlink()
        logger.info(f"Deleted file: {filename}")
        return {"message": f"Deleted {filename}"}
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/schema",
    response_model=SchemaResponse,
    summary="Get database schema",
    description="Returns information about all tables and columns in the session's connected database."
)
async def get_schema(session_id: str = None) -> SchemaResponse:
    """Get the current database schema for a session."""
    logger.info(f"Schema inspection requested for session: {session_id}")
    
    try:
        from src.database import get_session_components
        
        # Get session-specific components
        db_conn, inspector, executor, loader = get_session_components(session_id)
        
        if inspector is None:
            raise HTTPException(
                status_code=400,
                detail="No database connection found. Please connect to a database first."
            )
        
        tables = inspector.get_all_tables()
        
        # Filter out system tables
        user_tables = [
            t for t in tables 
            if t.name not in ["conversation_sessions", "conversation_messages"]
        ]
        
        return SchemaResponse(
            tables=[
                TableSchema(
                    name=t.name,
                    columns=[
                        {
                            "name": c.name,
                            "type": c.type,
                            "nullable": c.nullable,
                            "primary_key": c.primary_key,
                        }
                        for c in t.columns
                    ],
                    row_count=t.row_count,
                )
                for t in user_tables
            ],
            table_count=len(user_tables),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schema inspection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/load",
    response_model=LoadResponse,
    summary="Load all CSV files into database",
    description="Loads all CSV files from the data/ directory into database tables."
)
async def load_csv_files() -> LoadResponse:
    """Load all CSVs from the data directory."""
    logger.info("CSV loading requested")
    
    try:
        loader = CSVLoader()
        results = loader.load_all_csvs(drop_existing=True)
        
        total_rows = sum(v for v in results.values() if v > 0)
        
        return LoadResponse(
            tables_loaded=results,
            total_rows=total_rows,
            message=f"Loaded {len(results)} tables with {total_rows} total rows",
        )
    except Exception as e:
        logger.error(f"CSV loading failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Execute a test query (dev only)",
    description="Execute a raw SQL query. Only available in development mode."
)
async def execute_query(request: QueryRequest) -> QueryResponse:
    """Execute a test query (development only)."""
    settings = get_settings()
    
    if not settings.is_development():
        raise HTTPException(
            status_code=403,
            detail="Raw query execution is only available in development mode"
        )
    
    logger.info(f"Test query requested: {request.sql[:50]}...")
    
    executor = QueryExecutor()
    result = executor.execute_with_limit(request.sql, limit=request.limit)
    
    return QueryResponse(
        success=result.success,
        data=result.data,
        row_count=result.row_count,
        columns=result.columns,
        execution_time_ms=result.execution_time_ms,
        error=result.error,
    )


@router.get(
    "/health",
    summary="Database health check",
    description="Check if the database connection is healthy."
)
async def database_health() -> Dict[str, Any]:
    """Check database connectivity."""
    db = get_database()
    is_healthy = db.check_connection()
    
    return {
        "healthy": is_healthy,
        "message": "Database connection OK" if is_healthy else "Database connection failed"
    }


@router.delete(
    "/tables/{table_name}",
    summary="Delete a database table",
    description="Drop a table from the session's connected database. Use with caution!"
)
async def delete_table(table_name: str, session_id: str) -> Dict[str, Any]:
    """
    Delete a table from the session's database.
    
    This permanently removes the table and all its data.
    """
    # Basic validation to prevent SQL injection
    # Allow existing tables even with special chars, but block dangerous patterns
    if not table_name or len(table_name) > 200 or '--' in table_name or ';' in table_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid table name"
        )
    
    # Don't allow deleting system tables
    protected_tables = {"conversation_sessions", "conversation_messages"}
    if table_name.lower() in protected_tables:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete protected system table: {table_name}"
        )
    
    try:
        from src.database import get_session_components
        
        # Get session-specific components
        db_conn, inspector, executor, loader = get_session_components(session_id)
        
        if db_conn is None:
            raise HTTPException(
                status_code=400,
                detail="No database connection found. Please connect to a database first."
            )
        
        # Check if table exists
        if table_name not in inspector.get_table_names():
            raise HTTPException(
                status_code=404,
                detail=f"Table not found: {table_name}"
            )
        
        # Drop the table
        with db_conn.get_session() as session:
            session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
            session.commit()
        
        logger.info(f"Deleted table: {table_name} for session {session_id}")
        
        return {
            "message": f"Successfully deleted table '{table_name}'",
            "table_name": table_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete table: {e}")
        raise HTTPException(status_code=500, detail=str(e))
