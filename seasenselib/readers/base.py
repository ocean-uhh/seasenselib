"""
Module for abstract base class for reading sensor data from various file formats.

This module defines the `AbstractReader` class, which serves as a base class for
all reader implementations in the SeaSenseLib package. Concrete reader classes should
inherit from this class and implement the methods for reading and processing data
from specific file formats (e.g., CNV, TOB, NetCDF, CSV, RBR, Nortek).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import inspect
import re
import warnings
import logging
import xarray as xr
import seasenselib.parameters as params
from seasenselib.readers.utils import TimeConverter, DatasetProcessor, DatasetBuilder
from seasenselib.pipeline.utils import apply_user_metadata, normalize_user_metadata

MODULE_NAME = 'seasenselib'
logger = logging.getLogger(__name__)


class AbstractReader(ABC):
    """ Abstract super class for reading sensor data. 

    Must be subclassed to implement specific file format readers.
    
    This class supports the context manager protocol for automatic resource cleanup:
    
    >>> with SomeReader('data.cnv') as reader:
    ...     ds = reader.data
    ...     # process data
    >>> # data automatically released
    
    Attributes
    ---------- 
    input_file : str (read-only property)
        The path to the input file containing sensor data.
    input_header_file : str | None (read-only property)
        The path to separate header file, or None if not applicable.
    mapping : dict (read-only property)
        A dictionary mapping names used in the input file to standard names.
    data : xr.Dataset | None (read-only property)
        The processed sensor data as a xarray Dataset, or None if not yet processed.
        This is a read-only property. Use :meth:`get_data()` for backward compatibility.
    is_loaded : bool (read-only property)
        Whether data has been loaded from the file.
    metadata : dict (read-only property)
        File metadata (size, modification time, etc.) without loading data.
    perform_default_postprocessing : bool
        Whether to perform default post-processing on the data.
    rename_variables : bool
        Whether to rename xarray variables to standard names.
    assign_metadata : bool
        Whether to assign metadata to xarray variables.
    sort_variables : bool
        Whether to sort xarray variables by name.
    
    Methods
    -------
    __init__(input_file: str, mapping: dict | None = None, 
                    perform_default_postprocessing: bool = True,
                    rename_variables: bool = True, assign_metadata: bool = True, 
                    sort_variables: bool = True)
            Initializes the reader with the input file and optional mapping.
    __enter__() -> AbstractReader
            Context manager entry point.
    __exit__(exc_type, exc_val, exc_tb) -> None
            Context manager exit - releases data from memory.
    reload() -> AbstractReader
            Force reload data from file, clearing any cached data.
    _perform_default_postprocessing(ds: xr.Dataset) -> xr.Dataset
            Performs default post-processing on the xarray Dataset.
    get_data() -> xr.Dataset | None
            Returns the processed data as an xarray Dataset (deprecated, use `data` property).
    """

    _READER_ARG_EXCLUDE = frozenset({
        "self",
        "input_file",
        "dat_file_path",
        "mapping",
        "input_header_file",
        "header_file_path",
        "perform_default_postprocessing",
        "rename_variables",
        "assign_metadata",
        "sort_variables",
        "use_steps",
        "pipeline_config",
        "user_metadata",
        "kwargs",
    })

    @classmethod
    def _reader_arg(
        cls,
        name: str,
        type_name: str = "",
        default: Any = None,
        description: str = "",
        choices: list[str] | tuple[str, ...] | None = None,
        required: bool = False,
        cli_name: str | None = None,
        source: str = "declared",
    ) -> dict[str, Any]:
        """Build a structured reader argument description for CLI discovery."""
        spec = {
            "name": name,
            "cli_name": cli_name or name.replace("_", "-"),
            "type": type_name,
            "default": default,
            "required": bool(required),
            "description": description,
            "source": source,
        }
        if choices:
            spec["choices"] = list(choices)
        return spec

    @classmethod
    def _format_reader_arg_annotation(cls, annotation: Any) -> str:
        """Return a compact type label for an introspected reader argument."""
        if annotation is inspect.Signature.empty:
            return ""
        if isinstance(annotation, str):
            return annotation.replace("typing.", "")
        name = getattr(annotation, "__name__", None)
        if name:
            return name
        return str(annotation).replace("typing.", "")

    @classmethod
    def reader_args(cls) -> list[dict[str, Any]]:
        """
        Return CLI-discoverable reader-specific arguments.

        Reader subclasses should override this when they can provide concise,
        user-facing descriptions. The fallback introspects explicit constructor
        parameters, which keeps plugin readers discoverable even without a custom
        metadata hook.
        """
        try:
            signature = inspect.signature(cls.__init__)
        except (TypeError, ValueError):
            return []

        specs: list[dict[str, Any]] = []
        for name, parameter in signature.parameters.items():
            if name in cls._READER_ARG_EXCLUDE:
                continue
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            required = parameter.default is inspect.Signature.empty
            default = None if required else parameter.default
            specs.append(
                cls._reader_arg(
                    name=name,
                    type_name=cls._format_reader_arg_annotation(parameter.annotation),
                    default=default,
                    required=required,
                    description="Reader constructor argument inferred from the reader signature.",
                    source="signature",
                )
            )

        return specs

    def __init__(self, input_file: str, mapping: dict | None = None,
                 input_header_file: str | None = None,
                 perform_default_postprocessing: bool = True, rename_variables: bool = True,
                 assign_metadata: bool = True, sort_variables: bool = True,
                 use_steps: bool = True, pipeline_config: Any = None,
                 user_metadata: Dict[str, Any] | None = None,
                 **kwargs):
        """Initializes the AbstractReader with the input file and optional mapping.

        This constructor sets the input file, initializes the data attribute to None,
        and sets the mapping for variable names. It also allows for configuration of
        default post-processing, renaming of variables, assignment of metadata, and 
        sorting of variables.

        Parameters
        ---------- 
        input_file : str
            The path to the input file containing sensor data.
        mapping : dict, optional
            A dictionary mapping names used in the input file to standard names.
        input_header_file : str, optional
            The path to separate header file, or None if not applicable.
        perform_default_postprocessing : bool, optional
            Whether to perform default post-processing on the data. Default is True.
        rename_variables : bool, optional
            Whether to rename xarray variables to standard names. Default is True.
        assign_metadata : bool, optional
            Whether to assign CF metadata to xarray variables. Default is True.
        sort_variables : bool, optional
            Whether to sort xarray variables by name. Default is True.
        use_steps : bool, optional
            Whether to use the processing step pipeline system. Default is True.
            If False, returns raw data without any processing.
        pipeline_config : PipelineConfig, optional
            Custom pipeline configuration. If None, uses default pipeline.
        user_metadata : dict, optional
            Optional metadata overrides with sections {"global": {...}, "variables": {...}}.
        **kwargs
            Additional reader-specific parameters. These are accepted but not used
            by the base class, allowing subclasses to define their own parameters
            without modifying the base class signature.
        """

        self._input_file = input_file
        self._input_header_file = input_header_file
        self._data = None
        self._mapping = mapping if mapping is not None else {}
        self._config_perform_postprocessing = perform_default_postprocessing
        self._config_rename_variables = rename_variables
        self._config_assign_metadata = assign_metadata
        self._config_sort_variables = sort_variables
        self._config_use_steps = use_steps
        self._pipeline_config = pipeline_config
        self._processing_metadata = None
        self._postprocessed = False
        self._user_metadata = normalize_user_metadata(user_metadata) if user_metadata else None
        # **kwargs is intentionally not stored - subclasses handle their own parameters
        logger.info(
            "Initialized reader %s for '%s'",
            self.__class__.__name__,
            self._input_file
        )

    # =========================================================================
    # File Validation Methods (Override in subclasses for format-specific validation)
    # =========================================================================

    def _validate_file(self) -> None:
        """Validate the input file before reading.
        
        This method performs basic file validation (existence, not empty).
        Subclasses can override to add format-specific validation such as
        checking file extensions or file headers.
        
        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the file is not a regular file, is empty, or has an invalid
            extension (only if strict validation is enabled).
            
        Note
        ----
        This method is called automatically by subclasses that implement
        the modern reader pattern. For backward compatibility with existing
        readers that don't call this method, validation failures won't break
        the instantiation process unless explicitly called.
        
        Extension validation behavior depends on `_is_extension_validation_strict()`:
        - True (default): Invalid extension raises ValueError
        - False: Invalid extension logs a warning but continues
        
        Examples
        --------
        >>> class MyReader(AbstractReader):
        ...     def __init__(self, input_file, **kwargs):
        ...         super().__init__(input_file, **kwargs)
        ...         self._validate_file()  # Validate before data is accessed
        """
        path = Path(self._input_file)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {self._input_file}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {self._input_file}")
        
        if path.stat().st_size == 0:
            raise ValueError(f"File is empty: {self._input_file}")
        
        # Check extension if subclass specifies valid extensions
        valid_ext = self._get_valid_extensions()
        if valid_ext is not None:
            if path.suffix.lower() not in valid_ext:
                message = (
                    f"Unexpected file extension '{path.suffix}' for {self.__class__.__name__}. "
                    f"Expected one of: {', '.join(valid_ext)}"
                )
                if self._is_extension_validation_strict():
                    raise ValueError(message)
                else:
                    import logging
                    logging.getLogger(__name__).warning(message)

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for this reader.
        
        Subclasses should override this method to specify which file extensions
        are valid for their format. Return None to skip extension validation.
        
        Returns
        -------
        tuple[str, ...] | None
            Tuple of valid extensions (e.g., ('.cnv', '.CNV')) or None to skip validation.
            Extensions should include the leading dot and be lowercase.
            
        Examples
        --------
        >>> class MyReader(AbstractReader):
        ...     @classmethod
        ...     def _get_valid_extensions(cls) -> tuple[str, ...]:
        ...         return ('.myformat', '.myf')
        """
        return None  # Default: no extension validation

    @classmethod
    def _is_extension_validation_strict(cls) -> bool:
        """Return whether extension validation should raise an error or just warn.
        
        Override this method in subclasses to control validation behavior:
        - Return True (default): Invalid extension raises ValueError
        - Return False: Invalid extension logs a warning but continues
        
        Typically return False for ASCII/text-based formats that can have
        various extensions (.dat, .txt, .asc, etc.), and True for binary
        or proprietary formats with specific extensions (.rsk, .mat, .cnv).
        
        Returns
        -------
        bool
            True for strict validation (error), False for soft validation (warning).
            
        Examples
        --------
        >>> class AsciiReader(AbstractReader):
        ...     @classmethod
        ...     def _is_extension_validation_strict(cls) -> bool:
        ...         return False  # Warn only for ASCII formats
        """
        return True  # Default: strict validation

    # =========================================================================
    # Data Loading Methods (Override _load_data in subclasses)
    # =========================================================================

    def _load_data(self) -> xr.Dataset:
        """Load data from the input file.
        
        Subclasses SHOULD override this method to implement format-specific
        data loading logic. This method is called by the `data` property
        when lazy loading is enabled, or by `__init__` for eager loading.
        
        The default implementation raises NotImplementedError to indicate
        that subclasses using the legacy pattern (with private `__read()` methods)
        should continue working as before.
        
        Returns
        -------
        xr.Dataset
            The loaded dataset.
            
        Raises
        ------
        NotImplementedError
            If the subclass does not override this method.
            
        Note
        ----
        For backward compatibility, existing readers that use `__read()` 
        methods called from `__init__` will continue to work. New readers
        should implement `_load_data()` and call it from `__init__` or
        let the `data` property handle lazy loading.
        
        Examples
        --------
        >>> class MyReader(AbstractReader):
        ...     def _load_data(self) -> xr.Dataset:
        ...         # Read file and return raw Dataset
        ...         ds = xr.open_dataset(self.input_file)
        ...         return ds
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _load_data() method. "
            "See AbstractReader documentation for the expected interface."
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def input_file(self) -> str:
        """Get the input file path (read-only).
        
        Returns
        -------
        str
            Path to the input data file
        """
        return self._input_file

    @property
    def input_header_file(self) -> str | None:
        """Get the input header file path (read-only).
        
        Returns
        -------
        str | None
            Path to the separate header file, or None if not applicable
        """
        return self._input_header_file

    @property
    def mapping(self) -> dict:
        """Get the variable name mapping (read-only).
        
        Returns
        -------
        dict
            Dictionary mapping custom variable names to standard names
        """
        return self._mapping

    @property
    def is_loaded(self) -> bool:
        """Check if data has been loaded from file.
        
        Returns
        -------
        bool
            True if data has been loaded, False otherwise.
            
        Examples
        --------
        >>> reader = SomeReader('data.cnv')
        >>> print(reader.is_loaded)  # False until data property is accessed
        """
        return self._data is not None

    @property
    def metadata(self) -> Dict[str, Any]:
        """Get file-level metadata without loading data.
        
        This property provides access to file-level metadata such as
        file size and modification time without requiring the full
        data to be loaded into memory.
        
        For dataset-specific information (variables, dimensions, attributes),
        access the `data` property and inspect the xarray Dataset directly.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary containing file metadata:
            - file_path: Absolute path to the file
            - file_name: Base name of the file
            - file_size: Size in bytes
            - file_size_human: Human-readable size (e.g., "1.5 MB")
            - modified_time: Last modification timestamp (ISO format)
            - format_key: Reader format key
            - format_name: Reader format name
            
        Examples
        --------
        >>> reader = SomeReader('data.cnv')
        >>> print(f"File: {reader.metadata['file_name']}")
        >>> print(f"Size: {reader.metadata['file_size_human']}")
        >>> print(f"Format: {reader.metadata['format_name']}")
        >>> 
        >>> # For dataset info, use reader.data:
        >>> ds = reader.data
        >>> print(f"Variables: {list(ds.data_vars)}")
        >>> print(f"Dimensions: {dict(ds.dims)}")
        """
        path = Path(self._input_file)
        stat = path.stat()
        
        # Human-readable file size
        size_bytes = stat.st_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                size_human = f"{size_bytes:.1f} {unit}"
                break
            size_bytes /= 1024
        else:
            size_human = f"{size_bytes:.1f} PB"
        
        return {
            'file_path': str(path.absolute()),
            'file_name': path.name,
            'file_size': stat.st_size,
            'file_size_human': size_human,
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'format_key': self.format_key(),
            'format_name': self.format_name(),
        }

    def reload(self) -> 'AbstractReader':
        """Force reload data from file.
        
        Clears any cached data and re-reads from the file.
        This is useful when the underlying file has been modified
        or to free memory temporarily.
        
        Returns
        -------
        AbstractReader
            Returns self for method chaining.
            
        Note
        ----
        After calling reload(), the data will be re-read when the `data`
        property is next accessed (for lazy-loading readers) or you may
        need to create a new reader instance (for eager-loading readers).
        
        Examples
        --------
        >>> reader = SomeReader('data.cnv')
        >>> reader.reload()  # Clear cached data
        >>> ds = reader.data  # Re-read from file (lazy loading)
        """
        self._data = None
        self._processing_metadata = None
        self._postprocessed = False
        logger.info("Reload requested for '%s'", self._input_file)
        return self

    def __enter__(self) -> 'AbstractReader':
        """Context manager entry point.
        
        Returns
        -------
        AbstractReader
            Returns self for use in with statement.
            
        Examples
        --------
        >>> with SomeReader('data.cnv') as reader:
        ...     ds = reader.data
        ...     # process data
        >>> # data automatically released
        """
        logger.debug("Entering reader context for '%s'", self._input_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - releases data from memory.
        
        Parameters
        ----------
        exc_type : type
            Exception type if an exception was raised.
        exc_val : BaseException
            Exception value if an exception was raised.
        exc_tb : TracebackType
            Traceback if an exception was raised.
        """
        self._data = None
        logger.debug("Exiting reader context for '%s'", self._input_file)

    def __repr__(self) -> str:
        """String representation of the reader.
        
        Returns
        -------
        str
            Human-readable string showing class name, file, and load status.
        """
        loaded_str = "loaded" if self.is_loaded else "not loaded"
        return f"{self.__class__.__name__}('{self._input_file}', {loaded_str})"

    # =========================================================================
    # Time Conversion Methods (deprecated - use TimeConverter directly)
    # =========================================================================
    
    def _julian_to_gregorian(self, julian_days, start_date):
        """Convert Julian days to Gregorian datetime.
        
        .. deprecated:: 0.4.0
            Use :meth:`TimeConverter.julian_to_gregorian` directly instead.
            This wrapper will be removed in version 1.0.0.
        """
        warnings.warn(
            "AbstractReader._julian_to_gregorian() is deprecated. "
            "Use TimeConverter.julian_to_gregorian() directly instead. "
            "This method will be removed in version 1.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        return TimeConverter.julian_to_gregorian(julian_days, start_date)

    def _elapsed_seconds_since_jan_1970_to_datetime(self, elapsed_seconds):
        """Convert elapsed seconds since Jan 1970 to datetime.
        
        .. deprecated:: 0.4.0
            Use :meth:`TimeConverter.elapsed_seconds_since_jan_1970_to_datetime` directly.
            This wrapper will be removed in version 1.0.0.
        """
        warnings.warn(
            "AbstractReader._elapsed_seconds_since_jan_1970_to_datetime() is deprecated. "
            "Use TimeConverter.elapsed_seconds_since_jan_1970_to_datetime() directly instead. "
            "This method will be removed in version 1.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        return TimeConverter.elapsed_seconds_since_jan_1970_to_datetime(elapsed_seconds)

    def _elapsed_seconds_since_jan_2000_to_datetime(self, elapsed_seconds):
        """Convert elapsed seconds since Jan 2000 to datetime.
        
        .. deprecated:: 0.4.0
            Use :meth:`TimeConverter.elapsed_seconds_since_jan_2000_to_datetime` directly.
            This wrapper will be removed in version 1.0.0.
        """
        warnings.warn(
            "AbstractReader._elapsed_seconds_since_jan_2000_to_datetime() is deprecated. "
            "Use TimeConverter.elapsed_seconds_since_jan_2000_to_datetime() directly instead. "
            "This method will be removed in version 1.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        return TimeConverter.elapsed_seconds_since_jan_2000_to_datetime(elapsed_seconds)

    def _elapsed_seconds_since_offset_to_datetime(self, elapsed_seconds, offset_datetime):
        """Convert elapsed seconds since offset to datetime.
        
        .. deprecated:: 0.4.0
            Use :meth:`TimeConverter.elapsed_seconds_since_offset_to_datetime` directly.
            This wrapper will be removed in version 1.0.0.
        """
        warnings.warn(
            "AbstractReader._elapsed_seconds_since_offset_to_datetime() is deprecated. "
            "Use TimeConverter.elapsed_seconds_since_offset_to_datetime() directly instead. "
            "This method will be removed in version 1.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        return TimeConverter.elapsed_seconds_since_offset_to_datetime(elapsed_seconds, offset_datetime)

    def _validate_necessary_parameters(self, data, longitude, latitude, entity: str):
        if not params.TIME and not params.TIME_J and not params.TIME_Q \
                and not params.TIME_N in data:
            raise ValueError(f"Parameter '{params.TIME}' is missing in {entity}.")
        if not params.PRESSURE in data and not params.DEPTH:
            raise ValueError(f"Parameter '{params.PRESSURE}' is missing in {entity}.")

    # =========================================================================
    # Dataset Building Methods (thin wrappers for backward compatibility)
    # =========================================================================

    def _get_xarray_dataset_template(self, time_array, depth_array, 
                latitude, longitude, depth_name = params.DEPTH):
        """Create an xarray Dataset template with coordinates.
        
        This is a thin wrapper around :meth:`DatasetBuilder.create_template`
        for backward compatibility with subclasses.
        
        Parameters
        ----------
        time_array : array-like
            Array of datetime values for the time coordinate.
        depth_array : array-like or None
            Array of depth values, or None if not available.
        latitude : float
            Latitude coordinate value.
        longitude : float  
            Longitude coordinate value.
        depth_name : str, optional
            Name for the depth variable. Defaults to params.DEPTH.
            
        Returns
        -------
        xr.Dataset
            Empty xarray Dataset with coordinates set up.
        """
        return DatasetBuilder.create_template(
            time_array, depth_array, latitude, longitude, depth_name
        )

    def _assign_data_for_key_to_xarray_dataset(self, ds: xr.Dataset, key: str, data):
        """Assign a data array to the dataset.
        
        This is a thin wrapper around :meth:`DatasetBuilder.assign_data`
        for backward compatibility with subclasses.
        
        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to add data to.
        key : str
            The variable name for the data.
        data : array-like
            The data values to assign.
        """
        DatasetBuilder.assign_data(ds, key, data)

    def _assign_metadata_for_key_to_xarray_dataset(self, ds: xr.Dataset, key: str, 
                    label = None, unit = None):
        if not ds[key].attrs:
            ds[key].attrs = {}
        # Check for numbered standard names (e.g., temperature_1, temperature_2)
        base_key = key
        m = re.match(r"^([a-zA-Z0-9_]+?)(?:_\d{1,2})?$", key)
        if m:
            base_key = m.group(1)
        # Use metadata for base_key if available
        if base_key in params.metadata:
            for attribute, value in params.metadata[base_key].items():
                if attribute not in ds[key].attrs:
                    ds[key].attrs[attribute] = value
        if unit:
            ds[key].attrs['units'] = unit
        if label:
            if unit:
                label = label.replace(f"[{unit}]", '').strip() # Remove unit from label
            ds[key].attrs['long_name'] = label

    # =========================================================================
    # Dataset Processing Methods (delegates to DatasetProcessor)
    # =========================================================================

    def _derive_oceanographic_parameters(self, ds: xr.Dataset) -> xr.Dataset:
        """Derive oceanographic parameters from temperature, pressure, and salinity.
        
        This method calculates derived parameters like density and potential temperature
        using the Gibbs SeaWater (GSW) oceanographic toolbox when temperature, pressure,
        and salinity data are available in the xarray Dataset.
        
        For multiple sensors (e.g., temperature_1, temperature_2), it will use the first
        available sensor (temperature_1) or the base parameter name if only one exists.
        
        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset containing the sensor data and to add derived parameters to.
            
        Returns
        -------
        xr.Dataset
            The xarray Dataset with derived parameters added.
        """
        # Create callback for metadata assignment if enabled
        metadata_callback = None
        if self._config_assign_metadata:
            metadata_callback = self._assign_metadata_for_key_to_xarray_dataset
        
        return DatasetProcessor.derive_oceanographic_parameters(ds, metadata_callback)

    def _sort_xarray_variables(self, ds: xr.Dataset) -> xr.Dataset:
        """Sort variables in an xarray Dataset alphabetically by name.
        
        Variables with the same base name (e.g., temperature_1, temperature_2)
        are grouped together due to alphabetical sorting.
        
        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to be sorted.
            
        Returns
        -------
        xr.Dataset
            The xarray Dataset with variables sorted by their names.
        """
        return DatasetProcessor.sort_variables(ds)

    def _rename_xarray_parameters(self, ds: xr.Dataset) -> xr.Dataset:
        """Rename variables in an xarray Dataset according to standard mappings.
        
        Handles aliases with or without trailing numbering and ensures unique 
        standard names with numbering. If a standard name only occurs once, 
        it will not have a numbering suffix.
        
        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset with variables to rename.
            
        Returns
        -------
        xr.Dataset
            The xarray Dataset with renamed variables.
        """
        return DatasetProcessor.rename_parameters(ds)

    def _assign_default_global_attributes(self, ds: xr.Dataset) -> xr.Dataset:
        """Assign default global attributes to the xarray Dataset.
        
        Sets CF-compliant global attributes including history, conventions,
        and processor information.
        
        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to which the global attributes will be assigned.
            
        Returns
        -------
        xr.Dataset
            The xarray Dataset with global attributes assigned.
        """
        return DatasetProcessor.assign_default_global_attributes(
            ds,
            input_file=self._input_file,
            format_name=self.format_name(),
            reader_class_name=self.__class__.__name__
        )

    def _perform_default_postprocessing(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Perform default post-processing on the xarray Dataset.
        This includes renaming variables and assigning metadata.

        Note
        ----
        This method is invoked automatically by the ``data`` property.
        Reader subclasses should return raw datasets from ``_load_data()``
        and must not call this method directly.

        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to be processed.

        Returns
        -------
        xr.Dataset
            The processed xarray Dataset.
        """

        # NEW: Use processing step pipeline if enabled (default)
        if self._config_use_steps:
            try:
                from seasenselib.pipeline import default_pipeline, create_pipeline, PipelineConfig
                
                # Build metadata context
                metadata = {
                    'source_file': self._input_file,
                    'format_name': self.format_name(),
                    'reader_class': self.__class__.__name__,
                    'reader_module': self.__class__.__module__,
                    'reader_mapping': self._mapping,  # Pass reader mapping to stages
                    'format_key': self.format_key(),  # Pass format key for format-specific mapping
                }
                if hasattr(self, "_raw_header") and getattr(self, "_raw_header"):
                    metadata['raw_header'] = getattr(self, "_raw_header")
                if hasattr(self, "_raw_metadata_blocks") and getattr(self, "_raw_metadata_blocks"):
                    metadata['raw_metadata_blocks'] = getattr(self, "_raw_metadata_blocks")
                if hasattr(self, "_raw_metadata_variables") and getattr(self, "_raw_metadata_variables"):
                    metadata['raw_metadata_variables'] = getattr(self, "_raw_metadata_variables")
                if self._user_metadata:
                    metadata['user_metadata'] = self._user_metadata
                reader_groups = self.reader_groups()
                if reader_groups:
                    metadata['reader_groups'] = list(reader_groups)
                reader_transformations = self.pipeline_transformations(ds)
                if reader_transformations:
                    metadata['reader_transformations'] = list(reader_transformations)
                
                # Create pipeline (custom or default)
                if self._pipeline_config is not None:
                    if getattr(self, "_default_latitude_configured", False):
                        if any(stage.name == "derivation" for stage in self._pipeline_config.pipeline):
                            self._pipeline_config.upsert_stage('derivation', config={
                                'depth': {
                                    'use_default_latitude': bool(getattr(self, "_use_default_latitude")),
                                    'default_latitude': float(getattr(self, "_default_latitude", 45.0)),
                                }
                            })
                    pipeline = create_pipeline(config=self._pipeline_config)
                else:
                    # Create default pipeline profile with reader-specific config
                    config = PipelineConfig.from_resource("default")
                    
                    # Get format-specific mappings from the reader class
                    reader_mappings = self.format_mappings()
                    
                    # Configure mapping stage with reader mapping
                    config.upsert_stage('mapping', config={
                        'custom_mappings': self._mapping if self._mapping else {},
                        'reader_mappings': reader_mappings if reader_mappings else {},
                        'preserve_original': True
                    })

                    if getattr(self, "_default_latitude_configured", False):
                        config.upsert_stage('derivation', config={
                            'depth': {
                                'use_default_latitude': bool(getattr(self, "_use_default_latitude")),
                                'default_latitude': float(getattr(self, "_default_latitude", 45.0)),
                            }
                        })
                    
                    pipeline = create_pipeline(config=config)
                
                # Track applied stages
                metadata['stages_applied'] = pipeline.get_stage_order()
                
                # Execute pipeline
                ds = pipeline.execute(ds, metadata)

                # Store processing metadata for optional logging
                self._processing_metadata = metadata

                if self._user_metadata and not metadata.get('user_metadata_applied'):
                    warning = (
                        "User metadata was provided but not applied. "
                        "Ensure the 'user_metadata' handler is enabled in the metadata_enrichment stage."
                    )
                    warnings.warn(warning)
                    metadata.setdefault('warnings', []).append(warning)

                return ds
                
            except ImportError as e:
                # Stages not available, fall back to legacy
                warnings.warn(
                    f"Stage system not available ({e}). "
                    "Falling back to legacy postprocessing. "
                    "This should not happen in normal operation.",
                    RuntimeWarning
                )
                return ds
        
        # RAW MODE: When use_steps=False, return dataset as-is (no transformations)
        # This is used for --raw-only CLI option to get original variable names from the file
        else:
            if self._user_metadata:
                try:
                    # Prevent user metadata from overriding RAW/provenance fields
                    reserved_prefixes = ("raw_", "processor_")
                    filtered = {"global": {}, "variables": {}}
                    for key, value in self._user_metadata.get("global", {}).items():
                        if key.startswith(reserved_prefixes):
                            continue
                        filtered["global"][key] = value
                    for var_name, attrs in self._user_metadata.get("variables", {}).items():
                        if isinstance(attrs, dict):
                            new_attrs = {
                                k: v for k, v in attrs.items()
                                if not k.startswith(reserved_prefixes)
                            }
                            filtered["variables"][var_name] = new_attrs
                        else:
                            filtered["variables"][var_name] = attrs
                    logger.debug("Applying user metadata in raw mode for '%s'", self._input_file)
                    ds, _ = apply_user_metadata(ds, filtered, warn_missing=False)
                except Exception as e:
                    raise ValueError(f"Invalid user metadata: {e}") from e
            return ds
        
        # Note: Legacy postprocessing code has been removed. All processing is handled
        # by the pipeline system. If the pipeline import fails (which should never happen in normal
        # operation), the code returns raw data above.
        # 
        # The legacy code did:
        # - Variable name mapping --> now: variable_mapping step  
        # - Metadata assignment --> now: cf_convention + metadata_extraction steps
        # - Global attributes --> now: global_attributes step
        # - Variable sorting --> now: sorting step
        # 
        # If old behavior needed, set use_steps=True (default) and use the processing pipeline.

    def _postprocess_after_pipeline(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Optional hook for reader-specific adjustments after the pipeline ran.

        Override in subclasses if you need to apply small, format-specific
        tweaks after the standard pipeline completes. The default implementation
        returns the dataset unchanged.
        """
        return ds

    @property
    def processing_metadata(self) -> Dict[str, Any] | None:
        """Return processing metadata from the stage pipeline (if available)."""
        return self._processing_metadata

    @property
    def data(self) -> xr.Dataset | None:
        """Get the processed sensor data as an xarray Dataset (lazy loading).
        
        This property provides read-only access to the data. The data is loaded
        lazily on first access - subsequent accesses return the cached dataset.
        
        Returns
        -------
        xr.Dataset | None
            The processed sensor data.
            
        Raises
        ------
        NotImplementedError
            If the subclass does not implement `_load_data()`.
        RuntimeError
            If data loading fails.
            
        Examples
        --------
        >>> reader = SomeReader('data.cnv')
        >>> print(reader.is_loaded)  # False - not loaded yet
        >>> ds = reader.data  # Triggers lazy load
        >>> print(reader.is_loaded)  # True - now loaded
        >>> ds2 = reader.data  # Returns cached data
        >>> assert ds is ds2  # Same object
        """
        if self._data is None:
            try:
                logger.info("Loading data from '%s'", self._input_file)
                self._data = self._load_data()
                logger.debug(
                    "Loaded dataset from '%s' with %d variables and %d coords",
                    self._input_file,
                    len(self._data.data_vars),
                    len(self._data.coords)
                )
            except NotImplementedError:
                # Re-raise NotImplementedError with clear message
                raise
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load data from {self._input_file}: {e}"
                ) from e

        if not self._postprocessed:
            if self._config_perform_postprocessing:
                logger.debug("Applying postprocessing pipeline for '%s'", self._input_file)
                self._data = self._perform_default_postprocessing(self._data)
                if self._processing_metadata is not None:
                    self._data = self._postprocess_after_pipeline(self._data)
            self._postprocessed = True
        else:
            logger.debug("Returning cached dataset for '%s'", self._input_file)
        return self._data

    def get_data(self) -> xr.Dataset | None:
        """Returns the processed data as an xarray Dataset.
        
        .. deprecated:: 0.4.0
            Use the :attr:`data` property instead: ``reader.data``
            This method will be removed in version 1.0.0.
            
        Returns
        -------
        xr.Dataset | None
            The processed sensor data, or None if not yet read.
        """
        import warnings
        warnings.warn(
            "get_data() is deprecated and will be removed in version 1.0.0. "
            "Use the 'data' property instead: reader.data",
            DeprecationWarning,
            stacklevel=2
        )
        return self.data

    @classmethod
    @abstractmethod
    def format_name(cls) -> str:
        """Get the format name for this reader.

        This property must be implemented by all subclasses.

        Returns:
        --------
        str
            The format (e.g., 'SeaBird CNV', 'Nortek ASCII', 'RBR RSK').

        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Reader classes must define a format name")

    @classmethod
    @abstractmethod
    def format_key(cls) -> str:
        """Get the format key for this reader.

        This property must be implemented by all subclasses.
        
        Returns:
        --------
        str
            The format key (e.g., 'sbe-cnv', 'nortek-ascii', 'rbr-rsk').

        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Writer classes must define a format key")

    @classmethod
    @abstractmethod
    def file_extension(cls) -> str | None:
        """Get the primary file extension for this reader.

        This property must be implemented by all subclasses.
        The primary extension must be unique over all registered readers.
        If a reader does not specify a unique primary file extension, just
        return `None`.

        Returns:
        --------
        str | None
            The primary file extension (e.g., '.cnv', '.tob', '.rsk'), or
            None when there is no single primary extension (see :meth:`file_extensions`).

        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Reader classes must define a file extension")

    @classmethod
    def file_extensions(cls) -> tuple[str, ...]:
        """Get all extensions that can be auto-detected for this reader.

        Subclasses with multiple unique file suffixes should override this
        method. The default keeps backward compatibility by exposing only the
        primary extension returned by :meth:`file_extension`.

        Returns:
        --------
        tuple[str, ...]
            Supported auto-detect extensions. The first entry should match
            :meth:`file_extension` when a primary extension exists.
        """
        extension = cls.file_extension()
        return (extension,) if extension else ()
    
    @classmethod
    def format_mappings(cls) -> Dict[str, list]:
        """
        Get format-specific variable name mappings for this reader.
        
        Returns format-specific mappings that extend or override the default 
        mappings from parameters.py. This allows each reader to provide
        sensor-specific variable name patterns without hard-coding them in stages.
        
        The stage system will use these mappings after user custom mappings
        and before default mappings.
        
        Returns:
        --------
        dict
            Dictionary mapping canonical parameter names to list of format-specific
            variable name patterns. Empty dict means no format-specific mappings.
            
        Example:
        --------
        >>> class SbeCnvReader(AbstractReader):
        ...     @classmethod
        ...     def format_mappings(cls):
        ...         import seasenselib.parameters as params
        ...         return {
        ...             params.TEMPERATURE: ['t090C', 't068', 'tv290C'],
        ...             params.SALINITY: ['sal00', 'sal11'],
        ...             params.CONDUCTIVITY: ['c0mS/cm', 'c0S/m']
        ...         }
        
        Notes:
        ------
        - Override this method in subclasses to provide format-specific mappings
        - Default implementation returns empty dict (no format-specific mappings)
        - Keeps format-specific knowledge with the reader, not in stages
        - Supports flexible, extensible architecture
        """
        return {}  # Default: no format-specific mappings

    @classmethod
    def reader_groups(cls) -> tuple[str, ...]:
        """Return optional reader-group identifiers for pipeline controls.

        Reader groups allow pipeline stages to enable/disable behavior for
        related formats such as ``nortek-ascii`` and ``nortek-csv`` without
        coupling the stage to concrete reader classes. The default derives the
        group from the format key prefix before the first hyphen.
        """
        try:
            format_key = cls.format_key()
        except Exception:
            return ()
        if not isinstance(format_key, str) or "-" not in format_key:
            return ()
        group = format_key.split("-", 1)[0].strip().lower()
        return (group,) if group else ()

    def pipeline_transformations(self, ds: xr.Dataset) -> list[Any]:
        """Return optional transformation handlers for this concrete dataset.

        Readers can override this hook when a transformation depends on data,
        header metadata, or reader state. The transformation stage accepts
        objects implementing ``ITransformation``. The default performs no
        transformations.
        """
        return []
