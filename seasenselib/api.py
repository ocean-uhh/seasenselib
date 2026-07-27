"""
Public API functions for SeaSenseLib.

This module provides simple programmatic access to SeaSenseLib functionality
without requiring knowledge of the internal CLI structure.
"""

import os
from typing import List, Dict, Optional, TYPE_CHECKING, Any, Union

from .core import DataIOManager
from ._version import get_version

if TYPE_CHECKING:
    import xarray as xr

PathInput = Union[str, os.PathLike]


def _path_to_str(path: PathInput) -> str:
    """Return a filesystem path as a string, accepting pathlib.Path objects."""
    return os.fsdecode(os.fspath(path))


def _optional_path_to_str(path: Optional[PathInput]) -> Optional[str]:
    """Return an optional filesystem path as a string."""
    if path is None:
        return None
    return _path_to_str(path)


def read(filename: PathInput, file_format: Optional[str] = None,
         header_file: Optional[PathInput] = None, use_steps: bool = True,
         pipeline_apply_stages: Optional[List[str]] = None,
         pipeline_skip_stages: Optional[List[str]] = None,
         pipeline_profile: Optional[str] = None,
         pipeline_file: Optional[PathInput] = None,
         pipeline_apply_handlers: Optional[List[str]] = None,
         pipeline_skip_handlers: Optional[List[str]] = None,
         default_latitude: Optional[float] = None,
         default_longitude: Optional[float] = None,
         mapping: Optional[Dict[str, str]] = None,
         metadata: Optional[Dict[str, Any]] = None,
         metadata_file: Optional[PathInput] = None,
         step_config: Optional[Dict[str, Any]] = None,
         **kwargs) -> 'xr.Dataset':
    """
    Read a sensor data file and return it as an xarray Dataset.
    
    This function provides programmatic access to SeaSenseLib's data reading
    capabilities, equivalent to using the CLI 'convert' command but returning
    the data as an xarray Dataset for further processing.
    
    Parameters
    ----------
    filename : str or os.PathLike
        Path to the input file to read
    file_format : str, optional
        Format key to override automatic format detection.
        Use ssl.formats() to see available formats.
        Common formats: 'sbe-cnv', 'rbr-rsk', 'netcdf', 'csv'
        If None, format will be auto-detected from file extension.
    header_file : str or os.PathLike, optional
        Path to header file (required for Nortek ASCII files)
    use_steps : bool, default=True
        Whether to use the processing step pipeline system.
        If False, returns raw data without any processing.
    pipeline_apply_stages : List[str], optional
        Explicit list of pipeline stage names to apply. If None, uses default pipeline.
        Example: ['mapping', 'metadata_enrichment']
    pipeline_skip_stages : List[str], optional
        Pipeline stage names to skip. If None, uses default pipeline.
    pipeline_profile : str, optional
        Use a predefined pipeline profile (e.g., 'default', 'minimal').
        This is mutually exclusive with pipeline_apply_stages / pipeline_skip_stages.
    pipeline_file : str or os.PathLike, optional
        Path to a pipeline configuration file (.json/.yaml/.toml).
        This is mutually exclusive with pipeline_profile and pipeline_apply_stages/pipeline_skip_stages.
    pipeline_apply_handlers : List[str], optional
        Handlers to apply, in the form ['stage:handler', ...].
    pipeline_skip_handlers : List[str], optional
        Handlers to skip, in the form ['stage:handler', ...].
    default_latitude : float, optional
        Explicit fallback latitude in degrees north for derivations when the
        input data has no latitude. If omitted, no latitude is guessed.
        Depth derivation needs latitude only. TEOS-10 salinity/temperature
        derivations require longitude from the data or ``default_longitude``.
    default_longitude : float, optional
        Explicit fallback longitude in degrees east for derivations when the
        input data has no longitude. If omitted, no longitude is guessed.
        Used with latitude/default_latitude for TEOS-10 absolute salinity and
        conservative temperature derivations.
    mapping : Dict[str, str], optional
        Variable name mapping in the internal form {original_name: canonical_name}.
    metadata : Dict[str, Any], optional
        User metadata overrides with sections {"global": {...}, "variables": {...}}.
    metadata_file : str or os.PathLike, optional
        Path to a metadata JSON file with sections {"global": {...}, "variables": {...}}.
    step_config : Dict[str, Any], optional
        Configuration for specific processing stages.
        Example: {'metadata_enrichment': {'include_acdd': True}}
    **kwargs
        Additional reader-specific parameters. Examples:
        - sanitize_input : bool (for SBE CNV files, default=True)
        - encoding : str (for Sea&Sun TOB files, default='latin-1')
        
    Returns
    -------
    xarray.Dataset
        The sensor data as an xarray Dataset
        
    Raises
    ------
    FileNotFoundError
        If the input file does not exist
    ValueError
        If the file format is not supported or cannot be detected
    RuntimeError
        If there are issues reading or parsing the file
        
    Examples
    --------
    Read a CNV file with automatic format detection:
    
    ```python
    import seasenselib as ssl
    ds = ssl.read('ctd_profile.cnv')
    print(ds)
    ```
    
    Read a Seabird CNV file with explicit format:

    ```python
    ds = ssl.read('ctd_profile.cnv', file_format='sbe-cnv')
    print(ds)
    ```
    
    Read a Nortek ASCII file with header:

    ```python
    ds = ssl.read('adcp_profile.txt', file_format='nortek-ascii', 
                    header_file='adcp_header.hdr')
    ```
    
    Use custom pipeline stages:

    ```python
    ds = ssl.read('data.cnv', 
                  pipeline_apply_stages=['mapping', 'metadata_enrichment'],
                  step_config={'metadata_enrichment': {'include_acdd': True}})
    ```

    Use a predefined pipeline profile:

    ```python
    ds = ssl.read('data.cnv', pipeline_profile='default')
    ```

    Use a custom pipeline configuration file:

    ```python
    ds = ssl.read('data.cnv', pipeline_file='my_profile.json')
    ```

    Use explicit fallback coordinates for derivations:

    ```python
    ds = ssl.read(
        'mooring.cnv',
        default_latitude=54.0,
        default_longitude=10.0,
    )
    ```

    Provide user metadata directly:

    ```python
    ds = ssl.read(
        'data.cnv',
        metadata={
            'global': {'title': 'My Cruise'},
            'variables': {'temperature': {'units': 'degree_C'}}
        }
    )
    ```
    
    Get raw data without any processing:

    ```python
    ds = ssl.read('data.cnv', use_steps=False)
    ```
    
    Access the underlying pandas DataFrame:

    ```python
    df = ds.to_dataframe()
    print(df.head())
    ```
    """

    # Convert paths to strings for internal use
    filename = _path_to_str(filename)
    header_file = _optional_path_to_str(header_file)
    pipeline_file = _optional_path_to_str(pipeline_file)
    metadata_file = _optional_path_to_str(metadata_file)

    # Initialize the I/O manager
    io_manager = DataIOManager()
    
    # Build pipeline config if steps specified
    pipeline_config = None

    if pipeline_file is not None:
        if pipeline_profile is not None:
            raise ValueError("pipeline_file cannot be combined with pipeline_profile")
        if pipeline_apply_stages is not None or pipeline_skip_stages is not None:
            raise ValueError("pipeline_file cannot be combined with pipeline_apply_stages/pipeline_skip_stages")
        if not use_steps:
            raise ValueError("pipeline_file cannot be used when use_steps=False")
        from seasenselib.pipeline import PipelineConfig
        pipeline_config = PipelineConfig.from_file(pipeline_file)
        if step_config:
            for stage_name, config in step_config.items():
                pipeline_config.upsert_stage(stage_name, config=config)
    elif pipeline_profile is not None:
        if pipeline_apply_stages is not None or pipeline_skip_stages is not None:
            raise ValueError("pipeline_profile cannot be combined with pipeline_apply_stages/pipeline_skip_stages")
        if not use_steps:
            raise ValueError("pipeline_profile cannot be used when use_steps=False")
        from seasenselib.pipeline import PipelineConfig
        pipeline_config = PipelineConfig.from_resource(pipeline_profile)
        if step_config:
            for stage_name, config in step_config.items():
                pipeline_config.upsert_stage(stage_name, config=config)
    elif pipeline_apply_stages is not None:
        from seasenselib.pipeline import PipelineConfig
        pipeline_config = PipelineConfig()
        for step_name in pipeline_apply_stages:
            config = step_config.get(step_name, {}) if step_config else {}
            pipeline_config.add_stage(step_name, config=config)
    elif pipeline_skip_stages is not None:
        from seasenselib.pipeline import PipelineConfig, StageRegistry
        registry = StageRegistry.get_instance()
        all_steps = registry.list_stages()
        selected = [s for s in all_steps if s not in pipeline_skip_stages]
        pipeline_config = PipelineConfig()
        for step_name in selected:
            config = step_config.get(step_name, {}) if step_config else {}
            pipeline_config.add_stage(step_name, config=config)

    # Apply handler filters (optional)
    if pipeline_apply_handlers or pipeline_skip_handlers:
        from seasenselib.pipeline.utils import parse_handler_selectors, apply_handler_filters
        apply_map = parse_handler_selectors(pipeline_apply_handlers) if pipeline_apply_handlers else {}
        skip_map = parse_handler_selectors(pipeline_skip_handlers) if pipeline_skip_handlers else {}
        if pipeline_config is None:
            from seasenselib.pipeline import PipelineConfig
            pipeline_config = PipelineConfig.from_resource("default")
        pipeline_config = apply_handler_filters(pipeline_config, apply_map, skip_map)

    if default_latitude is not None or default_longitude is not None:
        if not use_steps:
            raise ValueError("default latitude/longitude cannot be used when use_steps=False")
        from seasenselib.pipeline import (
            PipelineConfig,
            apply_default_latitude,
            apply_default_longitude,
        )
        if pipeline_config is None:
            pipeline_config = PipelineConfig.from_resource("default")
        if default_latitude is not None:
            apply_default_latitude(pipeline_config, default_latitude)
        if default_longitude is not None:
            apply_default_longitude(pipeline_config, default_longitude)

    # Load user metadata (file + inline)
    user_metadata = None
    if metadata_file is not None:
        try:
            import json
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to load metadata file: {metadata_file}") from e
        from seasenselib.pipeline.utils import normalize_user_metadata
        user_metadata = normalize_user_metadata(data)
    if metadata is not None:
        from seasenselib.pipeline.utils import merge_user_metadata
        user_metadata = merge_user_metadata(user_metadata, metadata)

    try:
        # Use the existing I/O infrastructure to read the data
        reader_kwargs = dict(kwargs)
        if mapping is not None:
            reader_kwargs["mapping"] = mapping

        data = io_manager.read_data(
            filename, file_format, header_file,
            use_steps=use_steps,
            pipeline_config=pipeline_config,
            user_metadata=user_metadata,
            **reader_kwargs
        )
        return data

    except (FileNotFoundError, ValueError, RuntimeError):
        # Re-raise specific exceptions as-is
        raise
    except ImportError as e:
        # Handle missing dependencies
        raise RuntimeError(f"Missing required dependencies for reading {filename}: {e}") from e
    except OSError as e:
        # Handle file system issues
        raise FileNotFoundError(f"Cannot access file {filename}: {e}") from e
    except (KeyError, AttributeError, TypeError) as e:
        # Handle data format or parsing issues
        if "does not exist" in str(e):
            raise FileNotFoundError(f"Input file not found: {filename}") from e
        elif "Unknown format" in str(e) or "format detection" in str(e).lower():
            raise ValueError(f"Unsupported or undetectable file format: {filename}") from e
        else:
            raise RuntimeError(f"Error reading file {filename}: {e}") from e


def write(dataset: 'xr.Dataset', filename: PathInput,
          file_format: Optional[str] = None, **kwargs) -> None:
    """
    Write a xarray Dataset to a file in the specified format.
    
    This function provides programmatic access to SeaSenseLib's data writing
    capabilities, supporting various output formats for oceanographic data.
    
    Parameters
    ----------
    dataset : xarray.Dataset
        The dataset to write to file
    filename : str or os.PathLike
        Path to the output file
    file_format : str, optional
        Output format. If None, format will be detected from file extension.
        Supported formats: 'netcdf', 'csv', 'excel'
    **kwargs
        Additional arguments passed to the specific writer
        
    Raises
    ------
    ValueError
        If the file format is not supported or cannot be detected
    RuntimeError
        If there are issues writing the file
        
    Examples
    --------
    Write to NetCDF (recommended for xarray datasets):
    
    ```python
    import seasenselib as ssl
    ds = ssl.read('data.cnv')
    ssl.write(ds, 'output.nc')
    ```
    
    Write to CSV with explicit format:

    ```python
    ssl.write(ds, 'output.csv', file_format='csv')
    ```
    """

    # Convert paths to strings for internal use
    filename = _path_to_str(filename)

    # Initialize the I/O manager
    io_manager = DataIOManager()

    try:
        # Use the existing I/O infrastructure to write the data
        io_manager.write_data(dataset, filename, file_format, **kwargs)

    except (ValueError, RuntimeError):
        # Re-raise specific exceptions as-is
        raise
    except ImportError as e:
        # Handle missing dependencies
        raise RuntimeError(f"Missing required dependencies for writing {filename}: {e}") from e
    except OSError as e:
        # Handle file system issues
        raise RuntimeError(f"Cannot write to file {filename}: {e}") from e
    except Exception as e:
        # Handle unexpected errors
        raise RuntimeError(f"Error writing file {filename}: {e}") from e


def formats() -> List[Dict[str, Any]]:
    """
    List all supported input file formats.

    This function returns a list of all file formats that SeaSenseLib can
    read, along with their keys and typical file extensions. This is useful
    to determine which formats are available for reading data.
    
    Returns
    -------
    List[Dict[str, Any]]
        List of dictionaries containing format information with keys:
        'name', 'key', 'class_name', 'extension', 'extensions', 'is_plugin'
        Note: 'extension' is the primary extension and is always present
        (None if not applicable). 'extensions' contains all advertised
        auto-detect extensions.
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    formats = ssl.formats()
    for fmt in formats:
        ext = fmt['extension'] or 'N/A'
        print(f"{fmt['name']}: '{fmt['key']}' ({ext})")
    ```
    """
    return list_readers()


def list_readers() -> List[Dict[str, Any]]:
    """
    List all available reader formats (including plugins).

    Returns a list of all file formats that SeaSenseLib can read,
    including both built-in readers and those provided by plugins.
    
    Returns
    -------
    List[Dict[str, Any]]
        List of dictionaries containing reader information with keys:
        'name', 'key', 'class_name', 'extension', 'extensions', 'is_plugin'
        Note: 'extension' is the primary extension and is always present
        (None if not applicable). 'extensions' contains all advertised
        auto-detect extensions.
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    readers = ssl.list_readers()
    for reader in readers:
        plugin_marker = ' [P]' if reader['is_plugin'] else ''
        print(f"{reader['name']}{plugin_marker}: {reader['key']}")
    ```
    """
    from .core.autodiscovery import ReaderDiscovery

    discovery = ReaderDiscovery()
    return discovery.get_format_info()


def list_writers() -> List[Dict[str, str]]:
    """
    List all available writer formats (including plugins).

    Returns a list of all file formats that SeaSenseLib can write to,
    including both built-in writers and those provided by plugins.
    
    Returns
    -------
    List[Dict[str, str]]
        List of dictionaries containing writer information with keys:
        'name', 'key', 'class_name', 'extension', 'is_plugin'
        Note: 'extension' is always present (None if not applicable)
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    writers = ssl.list_writers()
    for writer in writers:
        plugin_marker = ' [P]' if writer['is_plugin'] else ''
        print(f"{writer['name']}{plugin_marker}: {writer['key']}")
    ```
    """
    from .core.autodiscovery import WriterDiscovery

    discovery = WriterDiscovery()
    return discovery.get_format_info()


def list_plotters() -> List[Dict[str, str]]:
    """
    List all available plotter types (including plugins).

    Returns a list of all plotter types available in SeaSenseLib,
    including both built-in plotters and those provided by plugins.
    
    Returns
    -------
    List[Dict[str, str]]
        List of dictionaries containing plotter information with keys:
        'name', 'key', 'class_name', 'is_plugin'
        Note: Plotters don't have 'extension' (only readers/writers do)
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    plotters = ssl.list_plotters()
    for plotter in plotters:
        plugin_marker = ' [P]' if plotter['is_plugin'] else ''
        print(f"{plotter['name']}{plugin_marker}: {plotter['key']}")
    ```
    """
    from .core.autodiscovery import PlotterDiscovery

    discovery = PlotterDiscovery()
    return discovery.get_format_info()


def list_parameters() -> List[Dict[str, str]]:
    """
    List canonical parameter names used by the internal data model.

    Returns a list of canonical variable names with short descriptions.

    Returns
    -------
    List[Dict[str, str]]
        List of dictionaries with keys: 'name', 'description'

    Examples
    --------
    ```python
    import seasenselib as ssl
    for item in ssl.list_parameters():
        print(f\"{item['name']}: {item['description']}\")
    ```
    """
    try:
        import seasenselib.parameters as params
        metadata = getattr(params, 'metadata', {}) or {}
        default_mappings = getattr(params, 'default_mappings', {}) or {}
        allowed = params.allowed_parameters()
    except Exception:
        metadata = {}
        default_mappings = {}
        allowed = {}

    names = set()
    if isinstance(default_mappings, dict):
        names.update(default_mappings.keys())
    if isinstance(metadata, dict):
        names.update(metadata.keys())

    if names:
        result = []
        for name in sorted(names):
            if isinstance(metadata, dict) and name in metadata:
                description = _describe_parameter(name, metadata[name])
            else:
                description = allowed.get(name) if isinstance(allowed, dict) else None
                if not description:
                    description = name.replace('_', ' ').title()
            result.append({'name': name, 'description': description})
        return result

    return [{'name': name, 'description': desc} for name, desc in allowed.items()]


def _describe_parameter(name: str, info: Dict[str, Any]) -> str:
    """Build a short description from metadata."""
    if not isinstance(info, dict):
        return name.replace('_', ' ').title()
    long_name = info.get('long_name') or name.replace('_', ' ').title()
    units = info.get('units')
    if units:
        return f"{long_name} ({units})"
    return long_name


def list_all() -> Dict[str, List[Dict[str, str]]]:
    """
    List all available resources: readers, writers, and plotters.

    Returns a comprehensive dictionary containing all available formats
    and plotters, organized by type. Includes both built-in resources
    and those provided by plugins.
    
    Returns
    -------
    Dict[str, List[Dict[str, str]]]
        Dictionary with keys 'readers', 'writers', 'plotters', each
        containing a list of resource information dictionaries
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    all_resources = ssl.list_all()
    
    print(f"Readers: {len(all_resources['readers'])}")
    print(f"Writers: {len(all_resources['writers'])}")
    print(f"Plotters: {len(all_resources['plotters'])}")
    
    # Count plugins
    total_plugins = sum(
        sum(1 for item in items if item.get('is_plugin', False))
        for items in all_resources.values()
    )
    print(f"Total plugins: {total_plugins}")
    ```
    """
    return {
        'readers': list_readers(),
        'writers': list_writers(),
        'plotters': list_plotters()
    }


def plot(plotter_key: str, dataset: 'xr.Dataset', **kwargs) -> None:
    """
    Create a plot using any registered plotter (built-in or plugin).
    
    This function provides a unified interface to all plotters in the system,
    mirroring the CLI's `seasenselib plot <plotter-key>` command. It automatically
    discovers and uses the appropriate plotter based on the provided key.
    
    Parameters
    ----------
    plotter_key : str
        The key identifying which plotter to use. Use `seasenselib.list_plotters()`
        to see all available plotters.
        
        Built-in plotter keys:
        - 'ts-diagram' : Temperature-Salinity diagram with density isolines
        - 'vertical-profile' : Vertical profile plot
        - 'time-series' : Time series plot (single or multiple parameters)
        
    dataset : xarray.Dataset
        The dataset containing the data to plot
        
    **kwargs
        Additional keyword arguments passed to the plotter's plot() method.
        Each plotter accepts different arguments - use the plotter's documentation
        or `seasenselib plot <plotter-key> -h` in the CLI to see available options.
        
        Common arguments:
        - output_file : str or os.PathLike, optional - Path to save the plot. If None, displays interactively.
        - title : str, optional - Custom plot title
        
    Returns
    -------
    None
        The plot is either displayed or saved to a file based on output_file parameter.
        
    Raises
    ------
    ValueError
        If the plotter_key is not recognized or if required arguments are missing.
    KeyError
        If the dataset is missing required variables for the chosen plotter.
        
    Examples
    --------
    Create a T-S diagram:
    
    >>> import seasenselib as ssl
    >>> ds = ssl.read('ctd_profile.cnv')
    >>> ssl.plot('ts-diagram', ds, dot_size=50, colormap='viridis')
    
    Create a time series plot:
    
    >>> ssl.plot('time-series', ds, parameter_names=['temperature'], 
    ...          ylim_min=10, ylim_max=20)
    
    Create a multi-parameter time series with dual axes:
    
    >>> ssl.plot('time-series', ds, 
    ...          parameter_names=['temperature', 'salinity'],
    ...          dual_axis=True, colors=['red', 'blue'])
    
    Create a vertical profile and save to file:
    
    >>> ssl.plot('vertical-profile', ds, output_file='profile.png',
    ...          dot_size=5, show_grid=False)
    
    Use a plugin plotter:
    
    >>> ssl.plot('histogram', ds, parameter_names=['temperature'], bins=50)
    
    List all available plotters:
    
    >>> ssl.list_plotters()
    
    See also
    --------
    list_plotters : List all available plotters with descriptions
    read : Read data from various sensor file formats
    write : Write datasets to various formats
    
    Notes
    -----
    The function uses lazy loading - plotter modules are only imported when needed.
    This keeps import times fast while still providing access to all functionality.
    
    The plotter discovery system automatically finds both built-in plotters and
    any plotters installed as plugins, making the API extensible without code changes.
    """
    # Lazy import to avoid heavy imports at package load time
    from .core.autodiscovery import PlotterDiscovery
    
    # Discover available plotters
    discovery = PlotterDiscovery()
    plotter_class = discovery.get_class_by_key(plotter_key)

    if not plotter_class:
        # Get list of available plotters for error message
        available = discovery.get_format_info()
        keys = [p['key'] for p in available]
        raise ValueError(
            f"Unknown plotter key '{plotter_key}'. "
            f"Available plotters: {', '.join(keys)}. "
            f"Use seasenselib.list_plotters() to see details about each plotter."
        )

    # Instantiate the plotter with the dataset
    plotter = plotter_class(dataset)

    kwargs = dict(kwargs)
    if "output_file" in kwargs:
        kwargs["output_file"] = _optional_path_to_str(kwargs["output_file"])

    # Call the plotter's plot method with provided kwargs
    try:
        plotter.plot(**kwargs)
    except TypeError as e:
        # Provide helpful error message if wrong arguments provided
        raise TypeError(
            f"Error calling plotter '{plotter_key}': {str(e)}. "
            f"Use 'seasenselib plot {plotter_key} -h' in the CLI to see available arguments."
        ) from e
