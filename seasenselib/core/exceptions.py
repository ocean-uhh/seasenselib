"""
Custom exceptions for SeaSenseLib.
"""


class SeaSenseLibError(Exception):
    """Base exception for SeaSenseLib."""
    pass


class FormatDetectionError(SeaSenseLibError):
    """Raised when file format cannot be detected."""
    pass


class DependencyError(SeaSenseLibError):
    """Raised when required dependencies are not available."""
    pass


class ValidationError(SeaSenseLibError):
    """Raised when input validation fails."""
    pass


class ReaderError(SeaSenseLibError):
    """Raised when data reading fails."""
    pass


class WriterError(SeaSenseLibError):
    """Raised when data writing fails."""
    pass
