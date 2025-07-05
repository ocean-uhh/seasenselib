"""
Module for reading Nortek ASCII data files into xarray Datasets.
"""

import re
import pandas as pd
import xarray as xr
import ctd_tools.parameters as params
from .base import AbstractReader


class NortekAsciiReader(AbstractReader):
    """ Reads Nortek ASCII data from a .dat file into a xarray Dataset. 
    
    This class reads Nortek ASCII data files, extracts column names and units from a .hdr file, 
    and organizes the data into an xarray Dataset. It handles duplicate column names by making 
    them unique, converts timestamps to datetime objects, and assigns metadata according to 
    CF conventions.
    
    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    dat_file_path : str
        The path to the .dat file containing the Nortek ASCII data.
    header_file_path : str 
        The path to the .hdr file containing the header information for the Nortek ASCII data.
    
    Methods
    -------
    __init__(dat_file_path, header_file_path):
        Initializes the NortekAsciiReader with the paths to the .dat and .hdr files.
    __read_header(hdr_file_path):
        Reads the .hdr file to extract column names and units.
    __parse_data(dat_file_path, headers):
        Parses the .dat file using the headers information to create a DataFrame.
    __create_xarray_dataset(df, headers):
        Converts the DataFrame to an xarray Dataset, renaming columns and assigning units.
    __read():
        Reads the .dat and .hdr files, processes the data, and creates an xarray Dataset.
    get_data():
        Returns the xarray Dataset containing the sensor data.
    file_type : str
        A string indicating the type of file being read, in this case, 'Nortek ASCII'.
    """

    def __init__(self, dat_file_path, header_file_path):
        """Initializes the NortekAsciiReader with the paths to the .dat and .hdr files."""
        super().__init__(dat_file_path, None, input_header_file=header_file_path)
        self.dat_file_path = dat_file_path
        self.header_file_path = header_file_path
        self.__read()

    def __read_header(self, hdr_file_path):
        """Reads the .hdr file to extract column names and units."""
        headers = []
        with open(hdr_file_path, 'r') as file:
            capture = False
            for line in file:
                if line.strip() == "Data file format":
                    capture = True
                    continue
                if capture:
                    if line.strip() == '':
                        break
                    if line.strip() and not line.startswith('---') and not line.startswith('['):
                        # Use regex to split the line considering whitespace count
                        parts = re.split(r'\s{2,}', line.strip())

                        if len(parts) >= 2:
                            col_number = parts[0]
                            if parts[-1].startswith('(') and parts[-1].endswith(')'):
                                unit = parts[-1].strip('()')
                                col_name = ' '.join(parts[1:-1])
                            else:
                                unit = 'unknown'
                                col_name = ' '.join(parts[1:])
                        else:
                            # Fallback if no unit is provided and the line is not correctly parsed
                            col_number = parts[0].split()[0]
                            col_name = ' '.join(parts[0].split()[1:])
                            unit = 'unknown'

                        headers.append((col_number, col_name, unit))
        return headers

    def __parse_data(self, dat_file_path, headers):
        """Parses the .dat file using headers information."""
        columns = [name for _, name, _ in headers]  # Extract just the names from headers

        # Handle duplicate column names by making them unique
        unique_columns = []
        seen = {}
        for col in columns:
            if col in seen:
                seen[col] += 1
                col = f"{col}_{seen[col]}"
            else:
                seen[col] = 0
            unique_columns.append(col)

        data = pd.read_csv(dat_file_path, sep='\s+', names=unique_columns)
        return data

    def __create_xarray_dataset(self, df, headers):
        # Convert columns to datetime
        df['time'] = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour', 'Minute', 'Second']])

        # Set datetime as the index
        df.set_index('time', inplace=True)

        # Rename columns as specified
        df.rename(columns=params.rename_list, inplace=True)

        # Convert the DataFrame to an xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Renaming and CF meta data enrichment
        for header in headers:
            _, variable, unit = header

            # Rename
            if variable in params.rename_list.keys():
                variable = params.rename_list[variable]

            # Set unit
            ds[variable].attrs['unit'] = unit

        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        return ds

    def __read(self):
        headers = self.__read_header(self.header_file_path)
        data = self.__parse_data(self.dat_file_path, headers)
        ds = self.__create_xarray_dataset(data, headers)
        self.data = ds

    def get_data(self):
        return self.data

    @staticmethod
    def format_key() -> str:
        """Get the default format key for this reader.

        Returns:
        --------
        str
            The format key for this reader, which is 'nortek-ascii'.
        """
        return 'nortek-ascii'

    @staticmethod
    def format_name() -> str:
        return 'Nortek ASCII'

    @staticmethod
    def file_extension() -> str | None:
        return None
