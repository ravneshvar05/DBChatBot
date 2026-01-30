"""
FastAPI Application Entry Point.

This module creates and configures the FastAPI application instance.
It handles:
1. Application initialization
2. Router registration
3. Middleware configuration (including audit & security - Phase 7)
4. Exception handlers (custom exceptions - Phase 7)
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
from src.core.exceptions import (
    ChatbotException,
    RateLimitExceeded,
    ValidationError,
    DatabaseError,
)
from src.core.audit import AuditMiddleware, SecurityHeadersMiddleware
from src.api.routes import chat_router, health_router, database_router, session_router, connection_router
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
    logger.info(f"Rate Limit: {settings.rate_limit_per_minute} req/min")
    logger.info(f"Audit Logging: {settings.enable_audit_logging}")
    
    # Initialize persistent memory tables (if enabled)
    # This ensures tables exist in Cloud DB on fresh deploy
    if settings.memory_persistent:
        from src.database.init_db import init_conversation_tables
        try:
            init_conversation_tables()
            logger.info("Checked/Initialized conversation tables.")
        except Exception as e:
            logger.error(f"Failed to auto-init tables: {e}")
    
    
    yield  # Application runs here
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")
    
    # Clean up session connections
    from src.database import get_connection_manager
    try:
        conn_manager = get_connection_manager()
        conn_manager.close_all_connections()
        logger.info("Closed all session connections")
    except Exception as e:
        logger.error(f"Error closing session connections: {e}")


# Create FastAPI application
app = FastAPI(
    title="Data Analytics Assistant API",
    description="""
    A conversational data analytics assistant powered by LLaMA-3.3-70B.
    
    ## Features
    
    - **Natural Language Queries**: Ask questions in plain English
    - **Safe SQL Generation**: Read-only queries with validation ✓
    - **Multi-turn Conversations**: Context-aware follow-ups ✓
    - **Persistent Memory**: Conversations survive restarts ✓
    - **Analytics Insights**: Auto-generated statistics ✓
    - **Rate Limiting**: Abuse prevention ✓
    - **Dynamic Database Connections**: Connect to any MySQL/PostgreSQL database ✓
    
    ## Current Phase: Multi-Database Support
    
    The assistant now allows users to connect to their own databases
    dynamically from the frontend interface.
    """,
    version="0.8.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================
# Middleware Configuration (Order matters!)
# ============================================================

# Security headers middleware (Phase 7)
app.add_middleware(SecurityHeadersMiddleware)

# Audit logging middleware (Phase 7)
if settings.enable_audit_logging:
    app.add_middleware(AuditMiddleware)
    logger.info("Audit logging middleware enabled")

# CORS middleware
if settings.is_development():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.warning("CORS configured for development (all origins allowed)")


# ============================================================
# Exception Handlers
# ============================================================

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers={"Retry-After": str(exc.retry_after)}
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(ChatbotException)
async def chatbot_exception_handler(request: Request, exc: ChatbotException):
    """Handle all custom chatbot exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


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


# ============================================================
# Routers
# ==============================================================

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(database_router)
app.include_router(session_router)
app.include_router(connection_router)  # NEW: Connection management


# ============================================================
# Root Endpoint
# ============================================================

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return {
        "message": "Data Analytics Assistant API",
        "version": "0.7.0",
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
