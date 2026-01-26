"""
API Routes module - Endpoint definitions.

Each file in this module defines routes for a specific domain:
- chat.py     : Conversational endpoints
- health.py   : Health check endpoints
- database.py : Database operations (schema, loading)
- session.py  : Session management endpoints
"""
from src.api.routes.chat import router as chat_router
from src.api.routes.health import router as health_router
from src.api.routes.database import router as database_router
from src.api.routes.session import router as session_router

__all__ = [
    "chat_router",
    "health_router",
    "database_router",
    "session_router",
]
