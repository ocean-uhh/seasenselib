"""
Module for reading sensor data from netCDF files into xarray Datasets.
"""

import xarray as xr
from .base import AbstractReader


class NetCdfReader(AbstractReader):
    """ Reads sensor data from a netCDF file into a xarray Dataset. 

    This class is used to read netCDF files, which are commonly used for storing
    multidimensional scientific data. The provided data is expected to be in a
    netCDF format, and this reader is designed to parse that format correctly.

    Attributes:
    ---------- 
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be read from the netCDF file.
    input_file : str
        The path to the input netCDF file containing the sensor data.
    
    Methods:
    -------
    __init__(input_file):
        Initializes the NetCdfReader with the input file.
    __read():
        Reads the netCDF file and processes the data into an xarray Dataset.
    get_data():
        Returns the xarray Dataset containing the sensor data.
    format_name():
        Returns the type of the file being read, which is 'netCDF'.
    file_extension():
        Returns the file extension for this reader, which is '.nc'.
    """

    def __init__(self, input_file: str, mapping: dict | None = None):
        """Initializes the NetCdfReader with the input file.
        Parameters:
        ----------
        input_file : str
            The path to the input netCDF file.
        mapping : dict | None, optional
            A mapping dictionary for renaming variables or attributes in the dataset.
        """

        # Call the base class constructor
        super().__init__(input_file, mapping)

        # Read the netCDF file
        self.__read()

    def __read(self):
        """Reads the netCDF file and processes the data into an xarray Dataset."""

        # Read from netCDF file
        self.data = xr.open_dataset(self.input_file)

        # Validation
        super()._validate_necessary_parameters(self.data, None, None, 'netCDF file')

    @staticmethod
    def format_key() -> str:
        return 'netcdf'

    @staticmethod
    def format_name() -> str:
        return 'netCDF'

    @staticmethod
    def file_extension() -> str | None:
        return '.nc'
