"""
CTD Tools Core Module

Core functionality including dependency management, I/O operations, and utilities.
"""

from .dependencies import DependencyManager
from .io_manager import DataIOManager
from .format_detection import FormatDetector
from .format_registry import get_all_formats, get_format_by_key, get_format_by_extension
from .exceptions import CTDToolsError, FormatDetectionError, DependencyError, ValidationError

__all__ = [
    'DependencyManager',
    'DataIOManager', 
    'FormatDetector',
    'get_all_formats',
    'get_format_by_key', 
    'get_format_by_extension',
    'CTDToolsError',
    'FormatDetectionError',
    'DependencyError',
    'ValidationError'
]
