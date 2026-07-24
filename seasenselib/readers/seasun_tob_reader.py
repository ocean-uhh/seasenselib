"""
Module for reading CTD data from TOB files into xarray Datasets.
"""

from __future__ import annotations
import pandas as pd
import xarray as xr
import seasenselib.parameters as params
from .base import AbstractReader


class SeasunTobReader(AbstractReader):
    """ Reads CTD data from a TOB ASCII file (Sea & Sun) into a xarray Dataset. 
    
    This class reads TOB files, extracts column names and units, and organizes the data
    into an xarray Dataset. It handles the conversion of timestamps to datetime objects 
    and assigns metadata according to CF conventions. The TOB file format is specific to
    Sea & Sun CTD devices, and this reader is designed to parse that format correctly.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    input_file : str
        The path to the input TOB file containing the CTD data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    encoding : str, optional
        The encoding used to read the TOB file, default is 'latin-1'.

    Methods
    -------
    __init__(input_file, mapping = {}, encoding = 'latin-1'):
        Initializes the TobReader with the input file, optional mapping, and encoding.
    _load_data():
        Reads the TOB file, processes the data, and creates an xarray Dataset.
    
    Properties
    ----------
    data : xr.Dataset (read-only)
        Returns the xarray Dataset containing the sensor data.
        For backward compatibility, get_data() method is also available but deprecated.
    format_name():
        Returns the format of the file being read, which is 'Sea & Sun TOB'.
    file_extension():
        Returns the file extension for this reader, which is '.tob'.
    
    """

    def __init__(self, input_file: str,
                 encoding: str = 'latin-1',
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize SeasunTobReader.
        
        Parameters
        ----------
        input_file : str
            Path to the TOB file.
        encoding : str, default='latin-1'
            Character encoding of the input file.
        mapping : dict, optional
            Variable name mapping dictionary.
        **kwargs
            Additional base class parameters:
            
            - input_header_file : str | None
                Path to separate header file (if applicable).
            - perform_default_postprocessing : bool, default=True
                Whether to perform default post-processing.
            - rename_variables : bool, default=True
                Whether to rename variables to standard names.
            - assign_metadata : bool, default=True
                Whether to assign CF-compliant metadata.
            - sort_variables : bool, default=True
                Whether to sort variables alphabetically.
        """
        super().__init__(input_file, mapping, **kwargs)
        self._encoding = encoding
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return valid file extensions for TOB files."""
        return ('.tob', '.txt', '.asc')

    @classmethod
    def _is_extension_validation_strict(cls) -> bool:
        """ASCII formats can have various extensions, so warn only."""
        return False

    @classmethod
    def reader_args(cls) -> list[dict]:
        return [
            cls._reader_arg(
                "encoding",
                "str",
                "latin-1",
                "Character encoding used when reading the TOB text file.",
            ),
        ]

    def _load_data(self) -> xr.Dataset:
        """ Reads a TOB file from Sea & Sun CTD into a xarray dataset. 
        
        This method processes the TOB file, extracts column names and units,
        and organizes the data into an xarray Dataset. It handles the conversion of
        timestamps to datetime objects and assigns metadata according to CF conventions.
        
        Returns
        -------
        xr.Dataset
            The loaded dataset.
        """

        # Read the file
        with open(self.input_file, 'r', encoding=self._encoding) as file:
            lines = file.readlines()

        # Find the line with column names
        header_line_index = next((i for i, line in enumerate(lines) \
                                  if line.startswith('; Datasets')), None)

        if header_line_index is None:
            raise ValueError("Line with column names not found in the file.")

        # Extract column names
        column_names = lines[header_line_index].strip().split()[1:]

        # Extract column units
        units = [None] + lines[header_line_index + 1].replace('[',''). \
            replace(']','').strip().split()[1:]

        # Load data into pandas DataFrame
        data_start_index = header_line_index + 3
        data = pd.read_csv(
            self.input_file,
            skiprows=data_start_index,
            delim_whitespace=True,
            names=column_names,
            parse_dates={params.TIME: ['IntD', 'IntT']},
            encoding=self._encoding,
        )

        # Convert DataFrame to xarray dataset
        ds = xr.Dataset.from_dataframe(data.set_index(params.TIME))

        # Assign units to data fields
        for index, name in enumerate(column_names):
            if name in ds and units[index]:
                ds[name].attrs['units'] = units[index]

        # Ensure 'time' coordinate is datetime type
        if params.TIME in ds.coords:
            ds[params.TIME] = pd.to_datetime(ds[params.TIME], errors='coerce')

        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        return ds

    @classmethod
    def format_mappings(cls) -> dict[str, list]:
        """Return Sea & Sun TOB format-specific variable name mappings.
        
        Returns
        -------
        dict[str, list]
            Dictionary mapping standard names to TOB format-specific aliases.
        """
        return {
            params.SALINITY: ['SALIN'],
            params.TEMPERATURE: ['Temp'],
            params.CONDUCTIVITY: ['Cond'],
            params.PRESSURE: ['Press'],
            params.SPEED_OF_SOUND: ['SOUND'],
            params.POWER_SUPPLY_INPUT_VOLTAGE: ['Vbatt'],
            'sigma': ['SIGMA'],
            'sample': ['Datasets'],
        }

    @classmethod
    def format_key(cls) -> str:
        return 'seasun-tob'

    @classmethod
    def format_name(cls) -> str:
        return 'Sea & Sun TOB'

    @classmethod
    def file_extension(cls) -> str | None:
        return '.tob'
