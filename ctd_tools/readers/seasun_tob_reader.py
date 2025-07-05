"""
Module for reading CTD data from TOB files into xarray Datasets.
"""

import pandas as pd
import xarray as xr
import gsw
import ctd_tools.parameters as params
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
    __read():
        Reads the TOB file, processes the data, and creates an xarray Dataset.
    get_data():
        Returns the xarray Dataset containing the sensor data.
    get_file_type():
        Returns the type of the file being read, which is 'Sea & Sun TOB'.
    get_file_extension():
        Returns the file extension for this reader, which is '.tob'.
    
    """

    def __init__(self, input_file, mapping = None, encoding = 'latin-1'):
        """ Initializes the SeasunTobReader with the input file, optional mapping, and encoding."""
        super().__init__(input_file, mapping)
        self.encoding = encoding
        self.__read()

    def __read(self):
        """ Reads a TOB file from Sea & Sun CTD into a xarray dataset. 
        
        This method processes the TOB file, extracts column names and units,
        and organizes the data into an xarray Dataset. It handles the conversion of
        timestamps to datetime objects and assigns metadata according to CF conventions.
        """

        # Read the file
        with open(self.input_file, 'r', encoding=self.encoding) as file:
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
            encoding=self.encoding,
        )

        # Convert DataFrame to xarray dataset
        ds = xr.Dataset.from_dataframe(data.set_index(params.TIME))

        # Assign units to data fields
        for index, name in enumerate(column_names):
            if name in ds and units[index]:
                ds[name].attrs['units'] = units[index]

        # Rename fields
        ds = ds.rename({
            'SALIN': params.SALINITY,
            'Temp': params.TEMPERATURE,
            'Cond': params.CONDUCTIVITY,
            'Press': params.PRESSURE,
            'SOUND': params.SPEED_OF_SOUND,
            'Vbatt': params.POWER_SUPPLY_INPUT_VOLTAGE,
            'SIGMA': 'sigma',
            'Datasets': 'sample',
        })

        # Convert pressure to depth
        pressure_in_dbar = ds['pressure'].values  # Extract pressure values from the dataset
        depth_in_meters = gsw.z_from_p(pressure_in_dbar, lat=53.8187)  # TODO latitude is for Cuxhaven
        ds['depth'] = (('time',), depth_in_meters)  # Assuming the pressure varies with time
        ds['depth'].attrs['units'] = "m"

        # Ensure 'time' coordinate is datetime type
        ds[params.TIME] = pd.to_datetime(ds[params.TIME], errors='coerce')

        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        # Store processed data
        self.data = ds

    @staticmethod
    def format_key() -> str:
        """Get the default format key for this reader.

        Returns:
        --------
        str
            The format key for this reader, which is 'seasun-tob'.
        """
        return 'seasun-tob'

    @staticmethod
    def format_name() -> str:
        return 'Sea & Sun TOB'

    @staticmethod
    def file_extension() -> str | None:
        return '.tob'
