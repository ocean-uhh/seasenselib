"""
Module for reading CTD data from CSV files into xarray Datasets.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import csv
import xarray as xr
import ctd_tools.parameters as params
from .base import AbstractReader


class CsvReader(AbstractReader):
    """ Reads CTD data from a CSV file into a xarray Dataset.

    This class reads CTD data from a CSV file, processes the data into a dictionary of columns,
    and organizes it into an xarray Dataset. It handles the conversion of timestamps to 
    datetime objects and assigns metadata according to CF conventions.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    input_file : str
        The path to the input CSV file containing the CTD data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.

    Methods
    -------
    __init__(input_file: str, mapping: dict | None = None)
        Initializes the CsvReader with the input file and optional mapping.
    __read()
        Reads the CSV file and processes the data into an xarray Dataset.
    get_data()
        Returns the xarray Dataset containing the sensor data.
    get_file_type()
        Returns the type of the file being read, which is 'CSV'.
    get_file_extension()
        Returns the file extension for this reader, which is '.csv'.
    """

    def __init__(self, input_file: str, mapping: dict | None = None):
        super().__init__(input_file, mapping)
        self.__read()

    def __read(self):
        # Read the CSV into a dictionary of columns
        with open(self.input_file, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            # Initialize a defaultdict of lists
            data = defaultdict(list)
            for row in reader:
                for key, value in row.items():
                    # Append the value from the row to the right list in data
                    data[key].append(value)

            # Convert defaultdict to dict
            data = dict(data)

            # Validation
            super()._validate_necessary_parameters(data, None, None, 'CSV file')

            # Convert 'time' values to datetime objects
            data[params.TIME] = [
                datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f') \
                    for timestamp in data[params.TIME]
            ]

            # Convert all other columns to floats
            for key in data.keys():
                if key != params.TIME and key in params.default_mappings: 
                    data[key] = [float(value) for value in data[key]]

            # Create xarray Dataset
            ds = self._get_xarray_dataset_template( 
                data[params.TIME],data[params.DEPTH],
                data[params.LATITUDE][0], data[params.LONGITUDE][0]
            )

            # Assign parameter values and meta information for each parameter to xarray Dataset
            for key in data.keys():
                super()._assign_data_for_key_to_xarray_dataset(ds, key, data[key])
                super()._assign_metadata_for_key_to_xarray_dataset( ds, key )
    
            # Store processed data
            self.data = ds

    @staticmethod
    def format_key() -> str:
        return 'csv'
    
    @staticmethod
    def format_name() -> str:
        return 'CSV'

    @staticmethod
    def file_extension() -> str | None:
        return '.csv'
