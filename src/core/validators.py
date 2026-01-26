"""
Input Validators - Sanitization and validation utilities.

This module provides security-focused input validation:
- Message sanitization
- Session ID validation
- Injection detection
"""
import re
import uuid
from typing import Optional, Tuple

from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Patterns that might indicate SQL injection attempts in messages
SUSPICIOUS_PATTERNS = [
    r";\s*DROP\s+",
    r";\s*DELETE\s+",
    r";\s*UPDATE\s+",
    r";\s*INSERT\s+",
    r"--\s*$",
    r"/\*.*\*/",
    r"'\s*OR\s+'1'\s*=\s*'1",
    r"'\s*OR\s+1\s*=\s*1",
    r"UNION\s+SELECT",
]

# Compiled patterns for efficiency
_SUSPICIOUS_REGEX = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def sanitize_message(message: str, max_length: int = 2000) -> str:
    """
    Sanitize a user message.
    
    - Strips leading/trailing whitespace
    - Removes null bytes
    - Limits length
    - Normalizes whitespace
    
    Args:
        message: Raw user message
        max_length: Maximum allowed length
        
    Returns:
        Sanitized message
    """
    if not message:
        return ""
    
    # Remove null bytes
    cleaned = message.replace("\x00", "")
    
    # Strip whitespace
    cleaned = cleaned.strip()
    
    # Normalize excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Limit length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    return cleaned


def validate_session_id(session_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a session ID is a proper UUID.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id:
        return True, None  # Empty is OK (will be generated)
    
    try:
        # Attempt to parse as UUID
        uuid.UUID(session_id)
        return True, None
    except ValueError:
        return False, "Invalid session_id format (must be UUID)"


def detect_suspicious_patterns(message: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a message contains suspicious patterns.
    
    This is a heuristic check - not a security guarantee.
    The actual SQL is validated separately.
    
    Args:
        message: User message to check
        
    Returns:
        Tuple of (is_suspicious, matched_pattern)
    """
    for pattern in _SUSPICIOUS_REGEX:
        match = pattern.search(message)
        if match:
            logger.warning(
                f"Suspicious pattern detected: {match.group()[:50]}..."
            )
            return True, match.group()
    
    return False, None


def validate_message(message: str) -> Tuple[bool, str, Optional[str]]:
    """
    Full validation and sanitization of a message.
    
    Args:
        message: Raw user message
        
    Returns:
        Tuple of (is_valid, sanitized_message, error_message)
    """
    # Check not empty
    if not message or not message.strip():
        return False, "", "Message cannot be empty"
    
    # Sanitize
    sanitized = sanitize_message(message)
    
    if not sanitized:
        return False, "", "Message cannot be empty after sanitization"
    
    # Check length
    if len(sanitized) < 1:
        return False, "", "Message too short"
    
    if len(sanitized) > 2000:
        return False, "", "Message too long (max 2000 characters)"
    
    # Check for suspicious patterns (warning only, don't block)
    is_suspicious, pattern = detect_suspicious_patterns(sanitized)
    if is_suspicious:
        logger.warning(f"Suspicious message detected but allowed: {pattern}")
    
    return True, sanitized, None


def validate_mode(mode: str) -> Tuple[bool, Optional[str]]:
    """
    Validate the query mode.
    
    Args:
        mode: Query mode ('sql' or 'chat')
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_modes = {'sql', 'chat'}
    
    if mode not in valid_modes:
        return False, f"Invalid mode: {mode}. Must be one of: {valid_modes}"
    
    return True, None
