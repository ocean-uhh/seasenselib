"""
Custom exceptions for CTD Tools.
"""


class CTDToolsError(Exception):
    """Base exception for CTD Tools."""
    pass


class FormatDetectionError(CTDToolsError):
    """Raised when file format cannot be detected."""
    pass


class DependencyError(CTDToolsError):
    """Raised when required dependencies are not available."""
    pass


class ValidationError(CTDToolsError):
    """Raised when input validation fails."""
    pass


class ReaderError(CTDToolsError):
    """Raised when data reading fails."""
    pass


class WriterError(CTDToolsError):
    """Raised when data writing fails."""
    pass
