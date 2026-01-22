"""
Database Routes - API endpoints for database operations.

These endpoints allow:
- Loading CSV data into PostgreSQL
- Inspecting database schema
- Testing queries (development only)
"""
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


@router.get(
    "/schema",
    response_model=SchemaResponse,
    summary="Get database schema",
    description="Returns information about all tables and columns in the database."
)
async def get_schema() -> SchemaResponse:
    """Get the current database schema."""
    logger.info("Schema inspection requested")
    
    try:
        inspector = SchemaInspector()
        tables = inspector.get_all_tables()
        
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
                for t in tables
            ],
            table_count=len(tables),
        )
    except Exception as e:
        logger.error(f"Schema inspection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/load",
    response_model=LoadResponse,
    summary="Load CSV files into database",
    description="Loads all CSV files from the data/ directory into PostgreSQL tables."
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
