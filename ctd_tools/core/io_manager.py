"""
Data I/O management.

This module provides centralized data reading and writing capabilities
with lazy loading of format-specific dependencies.
"""

import os
from typing import Optional, Any
from .dependencies import DependencyManager
from .format_detection import FormatDetector
from .exceptions import ReaderError, WriterError


class DataIOManager:
    """Manages data reading and writing operations.
    
    This class handles reading data from various formats and writing data
    to specified formats. It uses lazy loading to defer the import of
    format-specific readers and writers until they are actually needed.
    It also provides format detection and validation to ensure the correct
    reader or writer is used based on the file format or user-specified hints.

    Attributes:
    ----------
    dependency_manager : DependencyManager
        Manages the loading of format-specific dependencies.
    format_detector : FormatDetector
        Detects the format of input files.

    Methods:
    -------
    read_data(input_file: str, format_hint: Optional[str] = None,
              header_input_file: Optional[str] = None) -> Any:
        Reads data from the specified input file, using format detection
        and lazy loading of the appropriate reader based on the detected
        or specified format hint.
    write_data(data: Any, output_file: str, format_hint: Optional[str] = None) -> None:
        Writes data to the specified output file, using format validation
        and lazy loading of the appropriate writer based on the detected
        or specified format hint.
    """

    def __init__(self, dependency_manager: DependencyManager):
        """Initializes the DataIOManager with the given dependency manager."""
        self.deps = dependency_manager
        self.format_detector = FormatDetector()

    def read_data(self, input_file: str, format_hint: Optional[str] = None,
                  header_input_file: Optional[str] = None) -> Any:
        """
        Read data from input file with lazy loading of appropriate reader.
        
        Parameters:
        ----------
        input_file : str
            Path to the input file
        format_hint : str, optional
            Format hint to override auto-detection
        header_input_file : str, optional
            Path to header file (for Nortek ASCII files)
            
        Returns:
        --------
        xarray.Dataset
            The loaded data
            
        Raises:
        -------
        ReaderError
            If reading fails
        """
        try:

            # Validate input file
            if not os.path.exists(input_file):
                raise ReaderError("Input file does not exist.")

            # Detect format
            format_key = self.format_detector.detect_format(input_file, format_hint)

            # Get required dependencies
            deps = self.deps.get_data_dependencies()
            readers = deps['readers']

            # Create appropriate reader
            reader = self._create_reader(format_key, input_file, header_input_file, readers)

            # Read and return data
            return reader.get_data()

        except Exception as e:
            raise ReaderError(f"Failed to read data from {input_file}: {e}") from e

    def _create_reader(self, format_key: str, input_file: str, 
                      header_input_file: Optional[str], readers_module: Any) -> Any:
        """Create the appropriate reader for the given format using the registry."""
        
        # Import registry function for dynamic lookup
        # pylint: disable=C0415
        from ..readers.registry import get_reader_by_format_key

        # Get reader metadata from registry
        reader_metadata = get_reader_by_format_key(format_key)
        if not reader_metadata:
            raise ReaderError(f"Unknown format key: {format_key}")

        # Get the reader class from the readers module
        reader_class = getattr(readers_module, reader_metadata.class_name)

        # Handle special cases for reader construction
        return self._instantiate_reader(reader_class, reader_metadata.format_key, 
                                      input_file, header_input_file)

    def _instantiate_reader(self, reader_class: Any, format_key: str, 
                          input_file: str, header_input_file: Optional[str]) -> Any:
        """Instantiate a reader with the correct parameters based on format."""
        # Special case: Nortek ASCII reader requires header file
        if format_key == "nortek-ascii":
            if not header_input_file:
                raise ReaderError("Header input file is required for Nortek ASCII files.")
            return reader_class(input_file, header_input_file)

        # Standard case: most readers only need input_file
        return reader_class(input_file)

    def write_data(self, data: Any, output_file: str, format_hint: Optional[str] = None) -> None:
        """
        Write data to output file with lazy loading of appropriate writer.
        
        Parameters:
        -----------
        data : xarray.Dataset
            The data to write
        output_file : str
            Path to the output file
        format_hint : str, optional
            Format hint to override auto-detection
            
        Raises:
        -------
        WriterError
            If writing fails
        """
        try:
            # Validate output format
            output_format = self.format_detector.validate_output_format(output_file, format_hint)

            # Create output directory if needed
            self._ensure_output_directory(output_file)

            # Get required dependencies
            deps = self.deps.get_data_dependencies()
            writers = deps['writers']

            # Create appropriate writer
            writer = self._create_writer(output_format, data, writers)

            # Write data
            writer.write(output_file)

        except Exception as e:
            raise WriterError(f"Failed to write data to {output_file}: {e}") from e

    def _create_writer(self, output_format: str, data: Any, writers_module: Any) -> Any:
        """Create the appropriate writer for the given format."""
        if output_format == 'netcdf':
            return writers_module.NetCdfWriter(data)
        if output_format == 'csv':
            return writers_module.CsvWriter(data)
        if output_format == 'excel':
            return writers_module.ExcelWriter(data)
        raise WriterError(f"Unknown output format: {output_format}")

    def _ensure_output_directory(self, output_file: str) -> None:
        """Create output directory if it doesn't exist."""
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
