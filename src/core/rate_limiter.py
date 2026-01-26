"""
Rate Limiter - Control request frequency per session.

This module provides simple in-memory rate limiting to:
- Prevent abuse
- Control LLM API costs
- Ensure fair resource usage

For production with multiple instances, upgrade to Redis-backed limiter.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import threading

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Simple sliding window rate limiter.
    
    Tracks requests per session_id within a time window.
    
    Example:
        >>> limiter = RateLimiter(requests_per_minute=30)
        >>> limiter.is_allowed("session-123")  # True
        >>> # ... 30 requests later ...
        >>> limiter.is_allowed("session-123")  # False
    """
    
    def __init__(
        self,
        requests_per_minute: int = 30,
        cleanup_interval_minutes: int = 5
    ):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
            cleanup_interval_minutes: How often to clean old entries
        """
        self.limit = requests_per_minute
        self.window = timedelta(minutes=1)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        
        self._requests: Dict[str, List[datetime]] = {}
        self._lock = threading.RLock()
        self._last_cleanup = datetime.utcnow()
        
        logger.info(f"RateLimiter initialized: {requests_per_minute} requests/minute")
    
    def is_allowed(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if a request is allowed for the given identifier.
        
        Args:
            identifier: Session ID or IP address
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        with self._lock:
            self._maybe_cleanup()
            
            now = datetime.utcnow()
            cutoff = now - self.window
            
            # Get existing requests for this identifier
            if identifier not in self._requests:
                self._requests[identifier] = []
            
            # Filter to only requests within the window
            recent = [t for t in self._requests[identifier] if t > cutoff]
            self._requests[identifier] = recent
            
            # Check limit
            remaining = max(0, self.limit - len(recent))
            
            if len(recent) >= self.limit:
                logger.warning(f"Rate limit exceeded for: {identifier[:8]}...")
                return False, 0
            
            # Record this request
            self._requests[identifier].append(now)
            
            return True, remaining - 1
    
    def get_remaining(self, identifier: str) -> int:
        """
        Get remaining requests for an identifier.
        
        Args:
            identifier: Session ID or IP address
            
        Returns:
            Number of remaining requests in current window
        """
        with self._lock:
            now = datetime.utcnow()
            cutoff = now - self.window
            
            if identifier not in self._requests:
                return self.limit
            
            recent = [t for t in self._requests[identifier] if t > cutoff]
            return max(0, self.limit - len(recent))
    
    def get_reset_time(self, identifier: str) -> datetime:
        """
        Get when the rate limit resets for an identifier.
        
        Args:
            identifier: Session ID or IP address
            
        Returns:
            Datetime when oldest request expires
        """
        with self._lock:
            if identifier not in self._requests or not self._requests[identifier]:
                return datetime.utcnow()
            
            oldest = min(self._requests[identifier])
            return oldest + self.window
    
    def _maybe_cleanup(self) -> None:
        """Remove old entries periodically."""
        now = datetime.utcnow()
        
        if now - self._last_cleanup < self.cleanup_interval:
            return
        
        cutoff = now - self.window
        
        # Remove old timestamps
        for identifier in list(self._requests.keys()):
            self._requests[identifier] = [
                t for t in self._requests[identifier] if t > cutoff
            ]
            # Remove empty entries
            if not self._requests[identifier]:
                del self._requests[identifier]
        
        self._last_cleanup = now
        logger.debug(f"Rate limiter cleanup: {len(self._requests)} active sessions")


# Global rate limiter instance
_rate_limiter: RateLimiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.core.config import get_settings
        settings = get_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=getattr(settings, 'rate_limit_per_minute', 30)
        )
    return _rate_limiter
