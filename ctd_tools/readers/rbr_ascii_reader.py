"""
Module for reading RBR ASCII data files into xarray Datasets.
"""

from __future__ import annotations
import pandas as pd
import xarray as xr
import ctd_tools.parameters as params
from .base import AbstractReader


class RbrAsciiReader(AbstractReader):
    """ Reads RBR ASCII data from an ASCII file into an xarray Dataset.

    This class reads RBR ASCII data files, extracts the datetime and data columns,
    and organizes the data into an xarray Dataset. It handles the conversion of
    timestamps to datetime objects and assigns metadata according to CF conventions.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    input_file : str
        The path to the input file containing the RBR ASCII data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.

    Methods
    -------
    __init__(input_file: str, mapping: dict | None = None):
        Initializes the RbrAsciiReader with the input file and optional mapping.
    __create_xarray_dataset(df):
        Converts a pandas DataFrame to an xarray Dataset, assuming 'Datetime' as the index.
    __parse_data(file_path: str):
        Reads RBR data from a .dat file, extracting the datetime and data columns.
    __read():
        Reads the RBR ASCII data file, processes the data, and creates an xarray Dataset.
    get_data():
        Returns the xarray Dataset containing the sensor data.
    """

    def __init__(self, input_file : str, mapping : dict | None = None):
        """Initializes the RbrAsciiReader with the input file and optional mapping.
        Parameters
        ----------
        input_file : str
            The path to the input file containing the RBR ASCII data.
        mapping : dict, optional
            A dictionary mapping names used in the input file to standard names.
        """

        # Initialize the base class with the input file and mapping
        super().__init__(input_file, mapping)
        self.__read()

    def __create_xarray_dataset(self, df) -> xr.Dataset:
        """
        Converts a pandas DataFrame to an xarray Dataset.
        Assumes 'Datetime' as the index of the DataFrame, 
        which will be used as the time dimension.
        """

        # Ensure 'Datetime' is the index; if not, set it
        if 'time' not in df.index.names:
            df = df.set_index('time')

        # Rename columns as specified
        #df.rename(columns=params.rename_list, inplace=True)

        # Convert DataFrame to xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Perform default post-processing
        ds = self._perform_default_postprocessing(ds)

        return ds

    def __parse_data(self, file_path) -> pd.DataFrame:
        """
        Reads RBR data from a .dat file. Assumes that the actual data 
        starts after an empty line, with the first column being datetime 
        and the subsequent columns being the data entries.
        """
        # Open the file and read through it line by line until the data headers are found.
        with open(file_path, 'r') as file:
            lines = file.readlines()

        # Find the first non-empty line after metadata, which should be the header
        # line for data columns.
        start_data_index = 0
        for i, line in enumerate(lines):
            if line.strip() == '':
                start_data_index = i + 1
                break

        # The line right after an empty line contains column headers.
        # We need to handle it accordingly.
        header_line = lines[start_data_index].strip().split()
        header = header_line  # Assuming now 'Datetime' is handled in the next step

        # Now read the actual data, skipping rows up to and including the header line
        data = pd.read_csv(file_path, delimiter="\s+", \
                           names=['Date', 'Time'] + header, skiprows=start_data_index + 1)

        # Concatenate 'Date' and 'Time' columns to create a 'Datetime'
        # column and convert it to datetime type
        data[params.TIME] = pd.to_datetime(data['Date'] + ' ' + \
                                              data['Time'], format='%Y/%m/%d %H:%M:%S')

        # Remove original 'Date' and 'Time' columns
        data.drop(['Date', 'Time'], axis=1, inplace=True) 
        data.set_index(params.TIME, inplace=True)

        return data

    def __read(self):
        data = self.__parse_data(self.input_file)
        ds = self.__create_xarray_dataset(data)
        self.data = ds

    @staticmethod
    def format_key() -> str:
        return 'rbr-ascii'

    @staticmethod
    def format_name() -> str:
        return 'RBR ASCII'

    @staticmethod
    def file_extension() -> str | None:
        return None
