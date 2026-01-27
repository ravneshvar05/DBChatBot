"""
Configuration management via environment variables.

This module loads configuration from .env file using python-dotenv.
All configuration values are accessed through the Settings class.

Why environment variables:
1. Security - Secrets never committed to Git
2. Flexibility - Different values per environment (dev/staging/prod)
3. 12-factor app compliance - Configuration in environment
4. Easy CI/CD override - No code changes needed per environment
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# Load .env file from project root
# This must happen before accessing os.environ
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


@dataclass(frozen=True)
class Settings:
    """
    Application settings loaded from environment variables.
    
    frozen=True makes the dataclass immutable, preventing accidental
    modification of settings at runtime.
    
    Attributes:
        app_name: Application identifier for logging
        app_env: Environment name (development, staging, production)
        log_level: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        database_url: PostgreSQL connection string
        groq_api_key: API key for Groq LLM service
        google_api_key: API key for Google Gemini service
        llm_model: Model identifier for LLaMA
        llm_temperature: LLM creativity (0.0 = deterministic, 1.0 = creative)
        llm_max_tokens: Maximum response length
    """
    # Application settings
    app_name: str
    app_env: str
    log_level: str
    
    # Database settings
    database_url: str
    
    # LLM settings
    groq_api_key: str
    google_api_key: str
    llm_model: str
    llm_model_fast: str
    llm_model_smart: str
    llm_model_analysis: str
    llm_temperature: float
    llm_max_tokens: int
    
    # Memory settings (Phase 6)
    memory_persistent: bool
    
    # Safety settings (Phase 7)
    rate_limit_per_minute: int
    query_timeout_seconds: int
    enable_audit_logging: bool
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"


def _get_env(key: str, default: Optional[str] = None) -> str:
    """
    Get environment variable with optional default.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If required variable is not set and no default provided
    """
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(
            f"Required environment variable '{key}' is not set. "
            f"Please check your .env file."
        )
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Why lru_cache:
    - Settings are read once at startup
    - Avoids re-parsing .env on every access
    - Thread-safe singleton pattern
    - maxsize=1 ensures only one instance exists
    
    Returns:
        Settings instance with all configuration values
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Get database URL and fix dialect if needed
    # Priority:
    # 1. DATABASE_URL (Cloud/Aiven)
    # 2. Local Components (DB_HOST, DB_USER, etc)
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        # Fallback to constructing from components (Local MySQL)
        try:
            host = _get_env("DB_HOST", "localhost")
            port = _get_env("DB_PORT", "3306")
            user = _get_env("DB_USER", "root")
            password = _get_env("DB_PASSWORD", "")
            name = _get_env("DB_NAME", "footwear_db")
            
            # Construct MySQL URL
            database_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
        except ValueError:
             # If components are also missing, raise error
             raise ValueError("Missing database configuration. Set DATABASE_URL or (DB_HOST, DB_USER, ...)")

    # FIX: Ensure we use the correct driver for SQLAlchemy
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+pymysql://", 1)
        
    # FIX: Remove ssl-mode parameter (not supported by pymysql driver)
    # Aiven URLs often include this, but it crashes the python driver.
    # We strip it to allow connection (pymysql handles SSL negotiation automatically or via different means)
    if "ssl-mode=" in database_url:
        import re
        # Remove ssl-mode param (either at start of query string or middle)
        database_url = re.sub(r"[?&]ssl-mode=[^&]+", "", database_url)
        
        # Ensure if we removed the first param but left others, we clean up the syntax
        # e.g. /db&other=1 -> /db?other=1 is not handled here but usually ssl-mode is the ONLY param
        # Simplest fix for common Aiven URLs which end with it:
        if "?" not in database_url and "&" in database_url:
           database_url = database_url.replace("&", "?", 1) # simple patch if needed but re.sub usually safe enough for trailing
    
    return Settings(
        # Application
        app_name=_get_env("APP_NAME", "DataAnalyticsAssistant"),
        app_env=_get_env("APP_ENV", "development"),
        log_level=_get_env("LOG_LEVEL", "DEBUG"),
        
        # Database
        database_url=database_url,
        
        # LLM
        groq_api_key=_get_env("GROQ_API_KEY"),
        google_api_key=_get_env("GOOGLE_API_KEY"),
        llm_model=_get_env("LLM_MODEL", "llama-3.3-70b-versatile"),
        llm_model_fast=_get_env("LLM_MODEL_FAST", "llama-3.1-8b-instant"),
        llm_model_smart=_get_env("LLM_MODEL_SMART", "llama-3.3-70b-versatile"),
        llm_model_analysis=_get_env("LLM_MODEL_ANALYSIS", "models/gemini-flash-latest"),
        llm_temperature=float(_get_env("LLM_TEMPERATURE", "0.1")),
        llm_max_tokens=int(_get_env("LLM_MAX_TOKENS", "2048")),
        
        # Memory (Phase 6)
        memory_persistent=_get_env("MEMORY_PERSISTENT", "false").lower() == "true",
        
        # Safety (Phase 7)
        rate_limit_per_minute=int(_get_env("RATE_LIMIT_PER_MINUTE", "30")),
        query_timeout_seconds=int(_get_env("QUERY_TIMEOUT_SECONDS", "30")),
        enable_audit_logging=_get_env("ENABLE_AUDIT_LOGGING", "true").lower() == "true",
    )
