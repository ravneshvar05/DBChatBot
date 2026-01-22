"""
Centralized logging configuration.

This module provides consistent logging across all application modules.
Logs are written to both console (stdout) and rotating log files.

Why centralized logging:
1. Consistent format - Every log entry follows the same structure
2. Single configuration point - Change format/level in one place
3. Easy to extend - Add handlers (file, remote, etc.) centrally
4. Correlation IDs - Enable request tracing across modules
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Module-level flag to prevent duplicate handler registration
_logging_configured = False


def setup_logging(log_level: str = "DEBUG", log_dir: Optional[Path] = None) -> logging.Logger:
    """
    Configure application-wide logging.
    
    This function should be called once at application startup.
    It configures both console and file logging with consistent formatting.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files. Defaults to 'logs/' in project root.
        
    Returns:
        Configured root logger instance
        
    Example:
        >>> from src.core.logging_config import setup_logging
        >>> logger = setup_logging("INFO")
        >>> logger.info("Application started")
    """
    global _logging_configured
    
    # Prevent duplicate handler registration on repeated calls
    if _logging_configured:
        return logging.getLogger()
    
    # Determine log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create consistent formatter
    # Format: timestamp | level | module:line | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler - always enabled for immediate feedback
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # File handler - daily log files for persistence
    log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # File captures everything
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Allow all levels through
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    # These libraries log excessively at DEBUG level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    _logging_configured = True
    
    # Log that logging is configured (useful for debugging)
    root_logger.debug(f"Logging configured: level={log_level}, file={log_file}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    This is the primary way modules should obtain a logger.
    Using __name__ as the logger name preserves the module hierarchy.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        Logger instance for the specified name
        
    Example:
        >>> from src.core.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing user request")
        2024-01-15 10:30:45 | INFO     | src.api.routes:42 | Processing user request
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capability to any class.
    
    Provides a self.logger attribute that can be used for logging.
    The logger name is automatically set to the class name.
    
    Example:
        >>> class MyService(LoggerMixin):
        ...     def process(self):
        ...         self.logger.info("Processing...")
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger named after this class."""
        return get_logger(self.__class__.__name__)
