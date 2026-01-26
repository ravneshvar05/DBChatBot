"""
Database Initialization - Create tables for LTM.

This module provides functions to initialize the conversation
tables in the database for Long-Term Memory persistence.
"""
from src.core.logging_config import get_logger
from src.database.connection import get_database
from src.database.models import Base

logger = get_logger(__name__)


def init_conversation_tables() -> bool:
    """
    Create conversation tables if they don't exist.
    
    This should be called once during application startup
    when persistent memory is enabled.
    
    Returns:
        True if tables were created successfully
    """
    try:
        db = get_database()
        engine = db.engine
        
        # Create all tables defined in models
        Base.metadata.create_all(engine)
        
        logger.info("Conversation tables initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize conversation tables: {e}")
        raise


def drop_conversation_tables() -> bool:
    """
    Drop conversation tables (use with caution!).
    
    This is mainly for testing/development purposes.
    
    Returns:
        True if tables were dropped successfully
    """
    try:
        db = get_database()
        engine = db.engine
        
        Base.metadata.drop_all(engine)
        
        logger.warning("Conversation tables dropped")
        return True
        
    except Exception as e:
        logger.error(f"Failed to drop conversation tables: {e}")
        raise


if __name__ == "__main__":
    # Allow running directly to create tables
    print("Initializing conversation tables...")
    init_conversation_tables()
    print("Done!")
