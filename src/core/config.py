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
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    
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
    return Settings(
        # Application
        app_name=_get_env("APP_NAME", "DataAnalyticsAssistant"),
        app_env=_get_env("APP_ENV", "development"),
        log_level=_get_env("LOG_LEVEL", "DEBUG"),
        
        # Database
        database_url=_get_env("DATABASE_URL"),
        
        # LLM
        groq_api_key=_get_env("GROQ_API_KEY"),
        llm_model=_get_env("LLM_MODEL", "llama-3.3-70b-versatile"),
        llm_temperature=float(_get_env("LLM_TEMPERATURE", "0.1")),
        llm_max_tokens=int(_get_env("LLM_MAX_TOKENS", "2048")),
    )
