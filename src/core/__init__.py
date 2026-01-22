"""
Core module - Configuration and cross-cutting concerns.

This module provides:
- config.py      : Environment-based configuration management
- logging_config.py : Centralized logging setup
"""
from src.core.config import get_settings, Settings
from src.core.logging_config import setup_logging, get_logger, LoggerMixin

__all__ = [
    "get_settings",
    "Settings",
    "setup_logging",
    "get_logger",
    "LoggerMixin",
]
