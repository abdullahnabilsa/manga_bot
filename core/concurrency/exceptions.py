# File: core/concurrency/exceptions.py
from __future__ import annotations

class ConcurrencyError(Exception):
    """Base exception for concurrency system."""
    pass

class LeaseExpiredError(ConcurrencyError):
    """Raised when a user's temporary lease has expired."""
    pass

class ConcurrencyLimitReached(ConcurrencyError):
    """Raised when no parallel slots are available."""
    pass