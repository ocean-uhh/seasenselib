"""Reader and Writer factories for clean instantiation.

Modern factory pattern with Protocol-based type hints for extensibility.
All format handling is now dynamic via autodiscovery - no hardcoded formats!
"""

import inspect
from typing import Protocol, Optional, Any, List
from .autodiscovery import ReaderDiscovery, WriterDiscovery
from .exceptions import ReaderError, WriterError


class AbstractReader(Protocol):
    """Protocol for reader classes."""

    @property
    def data(self) -> Any:
        """Get data from the reader."""
        ...

    @classmethod
    def format_key(cls) -> str:
        """Return the format key for this reader."""
        ...


class AbstractWriter(Protocol):
    """Protocol for writer classes."""

    def write(self, output_file: str) -> None:
        """Write data to file."""
        ...

    @classmethod
    def file_extension(cls) -> str:
        """Return the file extension for this writer."""
        ...


class ReaderFactory:
    """Factory for creating reader instances with autodiscovery."""

    _COMMON_READER_KWARGS = frozenset({
        "mapping",
        "input_header_file",
        "perform_default_postprocessing",
        "rename_variables",
        "assign_metadata",
        "sort_variables",
        "use_steps",
        "pipeline_config",
        "user_metadata",
    })

    def __init__(self):
        self._discovery = ReaderDiscovery()

    def create_reader(
        self,
        format_key: str,
        input_file: str,
        header_file: Optional[str] = None,
        validate_reader_args: bool = False,
        **kwargs,
    ) -> AbstractReader:
        """Create a reader instance for the given format using signature introspection.
        
        This method uses Python inspect module to automatically match provided
        parameters to the reader constructor signature, eliminating hardcoded
        special cases and enabling plugin readers with custom parameters.
        
        Parameters
        ----------
        format_key : str
            The format key (e.g., 'sbe-cnv', 'rbr-rsk')
        input_file : str
            Path to the input file
        header_file : str, optional
            Path to header file (for formats like Nortek ASCII that need it)
        **kwargs
            All other parameters are matched against the reader constructor
            signature. Common parameters:
            - mapping : dict (variable name mapping, supported by all readers)
            - sanitize_input : bool (for CNV readers)
            - encoding : str (for TOB readers)
            - Any custom parameters for plugin readers
            
        Returns
        -------
        AbstractReader
            Reader instance ready to use
            
        Raises
        -------
        ReaderError
            If reader cannot be created
        """
        # Find the reader class
        reader_class = self._discovery.get_reader_by_format_key(format_key)
        if not reader_class:
            raise ReaderError(f"No reader found for format: {format_key}")

        # Special validation: Nortek ASCII requires header file
        if format_key == "nortek-ascii" and not header_file:
            raise ReaderError(
                "Nortek ASCII format requires a header file. "
                "Use --header-input to specify the header file."
            )

        # Use signature introspection to match parameters
        return self._instantiate_reader(
            reader_class,
            input_file,
            header_file,
            format_key=format_key,
            validate_reader_args=validate_reader_args,
            **kwargs,
        )

    def _instantiate_reader(
        self,
        reader_class: type,
        input_file: str,
        header_file: Optional[str],
        format_key: str | None = None,
        validate_reader_args: bool = False,
        **kwargs,
    ) -> AbstractReader:
        """
        Instantiate reader using signature introspection.
        
        This method inspects the reader __init__ signature and only passes
        parameters that the reader actually accepts, enabling automatic support
        for plugin readers with custom parameters.
        """
        if validate_reader_args:
            self._validate_reader_kwargs(reader_class, kwargs, format_key)

        # Get the constructor signature
        sig = inspect.signature(reader_class.__init__)
        params = sig.parameters
        
        # Build kwargs that match the reader signature
        matched_kwargs = {}
        all_kwargs = {'input_header_file': header_file, **kwargs}
        
        # Check each parameter in the signature
        for param_name, param in params.items():
            if param_name in ('self', 'input_file'):
                continue
            
            # If this parameter exists in our kwargs, include it
            if param_name in all_kwargs and all_kwargs[param_name] is not None:
                matched_kwargs[param_name] = all_kwargs[param_name]
            # If reader accepts **kwargs, pass everything through
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                matched_kwargs.update(all_kwargs)
                break
        
        # Special handling for Nortek ASCII which needs positional header_file_path
        if 'header_file_path' in params and header_file:
            matched_kwargs['header_file_path'] = header_file
            # Remove input_header_file if present (Nortek uses header_file_path)
            matched_kwargs.pop('input_header_file', None)
        
        # Instantiate with matched parameters
        return reader_class(input_file, **matched_kwargs)

    @classmethod
    def _validate_reader_kwargs(
        cls,
        reader_class: type,
        kwargs: dict[str, Any],
        format_key: str | None = None,
    ) -> None:
        """Validate CLI-provided reader kwargs against the reader metadata contract."""
        if not kwargs:
            return

        allowed = set(cls._COMMON_READER_KWARGS)
        try:
            specs = reader_class.reader_args()
        except Exception:
            specs = []

        for spec in specs or []:
            name = spec.get("name")
            if name:
                allowed.add(str(name))

        unknown = sorted(name for name in kwargs if name not in allowed)
        if not unknown:
            return

        display_format = format_key
        if display_format is None:
            try:
                display_format = reader_class.format_key()
            except Exception:
                display_format = reader_class.__name__
        rendered_unknown = ", ".join(name.replace("_", "-") for name in unknown)
        raise ReaderError(
            f"Unsupported reader argument(s) for {display_format}: {rendered_unknown}. "
            f"Use 'seasenselib list reader-args --filter {display_format}' to see supported options."
        )


class WriterFactory:
    """Factory for creating writer instances with dynamic autodiscovery."""

    def __init__(self):
        self._discovery = WriterDiscovery()

    def create_writer(self, format_key: str, data: Any) -> AbstractWriter:
        """
        Create a writer instance for the given format.
        
        Parameters:
        -----------
        format_key : str
            The format key (e.g., 'netcdf', 'csv', 'excel')
        data : Any
            The data to write (typically xarray.Dataset)
            
        Returns:
        --------
        AbstractWriter
            Writer instance ready to use
            
        Raises:
        -------
        WriterError
            If writer cannot be created
        """
        # Find the writer class by format key
        writer_class = self._discovery.get_writer_by_format_key(format_key)
        if not writer_class:
            available_formats = self.get_supported_formats()
            raise WriterError(
                f"No writer found for format: {format_key}. "
                f"Available formats: {', '.join(available_formats)}"
            )

        # Create writer instance with data
        return writer_class(data)

    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported output format keys.
        
        Returns:
        --------
        List[str]
            List of format keys (e.g., ['netcdf', 'csv', 'excel'])
        """
        format_info = self._discovery.get_format_info()
        return [info['key'] for info in format_info]

    def get_format_info(self) -> List[dict]:
        """
        Get detailed format information for all writers.
        
        Returns:
        --------
        List[dict]
            List of format info dicts with keys: 'key', 'name', 'extension', 'class_name'
        """
        return self._discovery.get_format_info()
