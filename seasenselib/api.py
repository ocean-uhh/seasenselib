"""
Public API functions for SeaSenseLib.

This module provides simple programmatic access to SeaSenseLib functionality
without requiring knowledge of the internal CLI structure.
"""

from typing import List, Dict, Optional, TYPE_CHECKING
from .core import DependencyManager, DataIOManager
from .core.format_registry import get_all_formats

if TYPE_CHECKING:
    import xarray as xr


def read(filename: str, file_format: Optional[str] = None, 
         header_file: Optional[str] = None, **kwargs) -> 'xr.Dataset':  # noqa: A002
    """
    Read a sensor data file and return it as an xarray Dataset.
    
    This function provides programmatic access to SeaSenseLib's data reading
    capabilities, equivalent to using the CLI 'convert' command but returning
    the data as an xarray Dataset for further processing.
    
    Parameters
    ----------
    filename : str
        Path to the input file to read
    file_format : str, optional
        Format key to override automatic format detection.
        Use ssl.formats() to see available formats.
        Common formats: 'sbe-cnv', 'rbr-rsk', 'netcdf', 'csv'
        If None, format will be auto-detected from file extension.
    header_file : str, optional
        Path to header file (required for Nortek ASCII files)
    **kwargs
        Additional arguments passed to the specific writer
        
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
    
    Access the underlying pandas DataFrame:

    ```python
    df = ds.to_dataframe()
    print(df.head())
    ```
    """

    # Initialize the core components
    dependency_manager = DependencyManager()
    io_manager = DataIOManager(dependency_manager)

    try:
        # Use the existing I/O infrastructure to read the data
        data = io_manager.read_data(filename, file_format, header_file, **kwargs)
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


def write(dataset: 'xr.Dataset', filename: str, 
          file_format: Optional[str] = None, **kwargs) -> None:
    """
    Write a xarray Dataset to a file in the specified format.
    
    This function provides programmatic access to SeaSenseLib's data writing
    capabilities, supporting various output formats for oceanographic data.
    
    Parameters
    ----------
    dataset : xarray.Dataset
        The dataset to write to file
    filename : str
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

    # Initialize the core components
    dependency_manager = DependencyManager()
    io_manager = DataIOManager(dependency_manager)

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


def formats() -> List[Dict[str, str]]:
    """
    List all supported input file formats.

    This function returns a list of all file formats that SeaSenseLib can
    read, along with their keys and typical file extensions. This is useful
    to determine which formats are available for reading data.
    
    Returns
    -------
    List[Dict[str, str]]
        List of dictionaries containing format information with keys:
        'name', 'key', 'extension', 'class_name'
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    formats = ssl.formats()
    for format in formats:
        print(f"{format['name']}: '{format['key']}' ({format['extension']})")
    ```
    """
    reader_formats = get_all_formats()
    return [
        {
            'name': fmt.name,
            'key': fmt.key, 
            'extension': fmt.extension,
            'class_name': fmt.class_name
        }
        for fmt in reader_formats
    ]
