"""
Memory Package - Conversation history management.

This package provides both short-term (STM) and long-term (LTM) memory:

## Short-Term Memory (In-memory)
- Fast access during conversations
- Lost on server restart
- Good for development/testing

## Long-Term Memory (MySQL-backed)
- Persists across restarts
- Searchable conversation history
- Good for production

Use `get_memory_manager()` to get the appropriate manager based on configuration.

Example:
    >>> from src.memory import get_memory_manager
    >>> manager = get_memory_manager()  # Auto-selects based on config
    >>> session = manager.get_or_create_session("user-123")
    >>> session.add_user_message("Hello!")
"""
from src.core.config import get_settings
from src.memory.conversation import Message, ConversationMemory
from src.memory.manager import (
    MemoryManager,
    get_memory_manager as get_stm_manager,
    reset_memory_manager
)

# Import persistent manager (may fail if tables don't exist yet)
try:
    from src.memory.persistent import (
        PersistentMemoryManager,
        get_persistent_memory_manager,
        reset_persistent_memory_manager
    )
    _PERSISTENT_AVAILABLE = True
except Exception:
    _PERSISTENT_AVAILABLE = False
    PersistentMemoryManager = None
    get_persistent_memory_manager = None
    reset_persistent_memory_manager = None


def get_memory_manager() -> MemoryManager:
    """
    Get the appropriate memory manager based on configuration.
    
    Returns:
        - PersistentMemoryManager if MEMORY_PERSISTENT=true
        - MemoryManager (in-memory) otherwise
    """
    settings = get_settings()
    
    if settings.memory_persistent and _PERSISTENT_AVAILABLE:
        return get_persistent_memory_manager()
    
    return get_stm_manager()


__all__ = [
    # Core classes
    "Message",
    "ConversationMemory",
    "MemoryManager",
    "PersistentMemoryManager",
    # Factory functions
    "get_memory_manager",
    "get_stm_manager",
    "get_persistent_memory_manager",
    # Reset functions (for testing)
    "reset_memory_manager",
    "reset_persistent_memory_manager",
]
