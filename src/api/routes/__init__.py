"""
API Routes module - Endpoint definitions.

Each file in this module defines routes for a specific domain:
- chat.py   : Conversational endpoints
- health.py : Health check endpoints
"""
from src.api.routes.chat import router as chat_router
from src.api.routes.health import router as health_router

__all__ = [
    "chat_router",
    "health_router",
]
