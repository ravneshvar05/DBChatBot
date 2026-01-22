"""
FastAPI Application Entry Point.

This module creates and configures the FastAPI application instance.
It handles:
1. Application initialization
2. Router registration
3. Middleware configuration
4. Exception handlers
5. Startup/shutdown events

Run with: uvicorn src.api.main:app --reload
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.core.logging_config import setup_logging, get_logger
from src.api.routes import chat_router, health_router, database_router
from src.models.chat import ErrorResponse


# Initialize logging before anything else
settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize services, verify connections
    - Shutdown: Clean up resources, close connections
    """
    # Startup
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode")
    logger.info(f"LLM Model: {settings.llm_model}")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


# Create FastAPI application
app = FastAPI(
    title="Data Analytics Assistant API",
    description="""
    A conversational data analytics assistant powered by LLaMA-3.3-70B.
    
    ## Features
    
    - **Natural Language Queries**: Ask questions in plain English
    - **Safe SQL Generation**: Read-only queries with validation (Phase 3+)
    - **Analytics Insights**: Human-readable summaries (Phase 5+)
    - **Multi-turn Conversations**: Context-aware follow-ups (Phase 4+)
    
    ## Current Phase
    
    **Phase 1**: Basic conversational chatbot without database access.
    The assistant acknowledges queries and explains what analysis it would perform.
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Configure CORS for development
# In production, this should be restricted to specific origins
if settings.is_development():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.warning("CORS configured for development (all origins allowed)")


# Register routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(database_router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions globally.
    
    This ensures all errors return a consistent ErrorResponse format.
    Detailed error information is only included in development mode.
    """
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.is_development() else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Root endpoint redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return {
        "message": "Data Analytics Assistant API",
        "documentation": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development()
    )
