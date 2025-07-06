"""
File format detection utilities.

This module provides lightweight format detection without importing heavy dependencies.
Now uses the centralized reader registry.
"""

import os
from pathlib import Path
from typing import Optional
from .exceptions import FormatDetectionError

# Import functions from the centralized registry
from ..readers.registry import get_extension_map, get_input_formats

# Get mappings from the centralized registry
EXTENSION_MAP = get_extension_map()
INPUT_FORMATS = list(get_input_formats().keys())

# Output formats (these are separate from readers)
OUTPUT_FORMATS = ['netcdf', 'csv', 'excel']


class FormatDetector:
    """Lightweight file format detection."""

    @staticmethod
    def detect_format(input_file: str, format_hint: Optional[str] = None) -> str:
        """
        Detect file format without importing readers.
        
        Parameters:
        -----------
        input_file : str
            Path to the input file
        format_hint : str, optional
            Explicit format hint to override detection
            
        Returns:
        --------
        str
            The detected format key
            
        Raises:
        -------
        FormatDetectionError
            If format cannot be determined
        """
        if format_hint:
            if format_hint in INPUT_FORMATS:
                return format_hint
            else:
                raise FormatDetectionError(f"Unknown format hint: {format_hint}")

        # Check if file exists
        if not os.path.exists(input_file):
            raise FormatDetectionError(f"Input file does not exist: {input_file}")

        # Get file extension
        file_path = Path(input_file)
        extension = file_path.suffix.lower()

        # Map extension to format
        if extension in EXTENSION_MAP:
            detected_format = EXTENSION_MAP[extension]
            return detected_format

        # If no extension match, raise an error
        raise FormatDetectionError(
            f"Cannot determine format for file: {input_file}. "
            f"Extension '{extension}' not recognized and content detection failed."
        )


    @staticmethod
    def validate_output_format(output_file: str, format_hint: Optional[str] = None) -> str:
        """
        Validate and determine output format.
        
        Parameters:
        -----------
        output_file : str
            Path to the output file
        format_hint : str, optional
            Explicit format hint
            
        Returns:
        --------
        str
            The validated output format
        """
        if format_hint:
            if format_hint in OUTPUT_FORMATS:
                return format_hint
            else:
                raise FormatDetectionError(f"Unknown output format: {format_hint}")

        # Detect from file extension
        file_path = Path(output_file)
        extension = file_path.suffix.lower()

        if extension == '.nc':
            return 'netcdf'
        elif extension == '.csv':
            return 'csv'
        elif extension in ['.xlsx', '.xls']:
            return 'excel'
        else:
            raise FormatDetectionError(
                f"Output file must be a netCDF (.nc), CSV (.csv), or Excel (.xlsx) file. "
                f"Got: {extension}"
            )
