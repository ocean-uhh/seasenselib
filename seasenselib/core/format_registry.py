"""
Format registry for readers.

This module provides metadata about supported formats without loading
the heavy reader classes. Now uses the centralized reader registry.
"""

from typing import List, NamedTuple, Optional

# Import the centralized reader registry
from ..readers.registry import READER_REGISTRY, get_reader_by_format_key


class FormatInfo(NamedTuple):
    """
    Information about a supported format.

    This class holds metadata about a specific data format, including
    its name, key, file extension, and the associated reader class.

    Attributes:
    ----------
    name : str
        The name of the format.
    key : str
        The unique key for the format.
    extension : str
        The file extension associated with the format.
    class_name: str
        The class name of the reader for this format.
    """
    name: str
    key: str
    extension: str
    class_name: str


def get_all_formats() -> List[FormatInfo]:
    """Get all supported format information from the reader registry."""
    formats = []
    for reader in READER_REGISTRY:
        formats.append(FormatInfo(
            name=reader.format_name,
            key=reader.format_key,
            extension=reader.file_extension or '',
            class_name=reader.class_name
        ))
    return formats


def get_format_by_key(key: str) -> FormatInfo:
    """Get format information by format key."""
    reader = get_reader_by_format_key(key)
    if not reader:
        raise ValueError(f"Unknown format key: {key}")

    return FormatInfo(
        name=reader.format_name,
        key=reader.format_key,
        extension=reader.file_extension or '',
        class_name=reader.class_name
    )


def get_format_by_extension(extension: str) -> Optional[FormatInfo]:
    """Get format information by file extension."""
    for reader in READER_REGISTRY:
        if reader.file_extension == extension:
            return FormatInfo(
                name=reader.format_name,
                key=reader.format_key,
                extension=reader.file_extension or '',
                class_name=reader.class_name
            )
    return None
