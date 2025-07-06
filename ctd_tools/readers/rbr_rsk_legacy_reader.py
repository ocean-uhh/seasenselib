"""
Module for reading RBR legacy .rsk files into xarray Datasets.
"""

import sqlite3
import pandas as pd
import xarray as xr
from .base import AbstractReader


class RbrRskLegacyReader(AbstractReader):
    """
    Reads sensor data from a RBR .rsk file (legacy format) into a xarray Dataset.

    This class is specifically designed to read RBR legacy files that are stored 
    in a SQLite database format. It extracts channel information and measurement 
    data, converts timestamps, and organizes the data into an xarray Dataset.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    input_file : str
        The path to the input file containing the RBR legacy data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    """

    def __init__(self, input_file : str, mapping : dict | None = None):
        """ Initializes the RbrRskLegacyReader with the input file and optional mapping.

        Parameters
        ----------
        input_file : str
            The path to the input file containing the data.
        mapping : dict, optional
            A dictionary mapping names used in the input file to standard names.
        """
        super().__init__(input_file, mapping)
        self.__read()

    def _read_instrument_data(self, con: sqlite3.Connection) -> dict:
        """ Reads instrument data from the RSK file. 
        
        This method retrieves the instrument information from the database 
        and returns it as a dictionary.

        Parameters
        ----------
        con : sqlite3.Connection
            The SQLite connection object to the RSK file.

        Returns
        -------
        dict
            A dictionary containing instrument information such as instrumentID, 
            serialID, model, firmwareVersion, firmwareType, and partNumber. If no 
            instrument data is found, an empty dictionary is returned.
        """
        query = "SELECT * FROM instruments"
        df = pd.read_sql_query(query, con)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}

    def _read_database_information(self, con: sqlite3.Connection) -> dict:
        """ Reads database information from the RSK file. 
        
        This method retrieves the database information from the database 
        and returns it as a dictionary.

        Parameters
        ----------
        con : sqlite3.Connection
            The SQLite connection object to the RSK file.

        Returns
        -------
        dict
            A dictionary containing database information such as version and type. 
            If no database information is found, an empty dictionary is returned.
        """
        query = "SELECT version, type FROM dbInfo"
        df = pd.read_sql_query(query, con)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}

    def _read_channel_data(self, con: sqlite3.Connection) -> pd.DataFrame:
        """ Reads channel data from the RSK file. 
        
        This method retrieves channel information from the database and returns it as a DataFrame.

        Parameters
        ----------
        con : sqlite3.Connection
            The SQLite connection object to the RSK file.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing channel information with columns: channelID, shortName, longName,
            longNamePlainText, and units. The DataFrame is ordered by channelID.
        """
        query = "SELECT channelID, shortName, longName, longNamePlainText, units " \
            "FROM  channels " \
            "ORDER BY channelID"
        return pd.read_sql_query(query, con)

    def _read_measurement_data(self, con: sqlite3.Connection) -> pd.DataFrame:
        """ Reads measurement data from the RSK file. 
        
        This method retrieves measurement data from the database and returns it as a DataFrame.

        Parameters
        ----------
        con : sqlite3.Connection
            The SQLite connection object to the RSK file.
        
        Returns
        -------
        pd.DataFrame
            A DataFrame containing measurement data with columns: tstamp and channelXX 
            for each channel. The DataFrame contains all measurement data from the 'data' 
            table in the RSK file
        """
        query = "SELECT * FROM data"
        return pd.read_sql_query(query, con)

    def __read(self):
        """ Reads a RSK file (legacy format) and converts it to a xarray Dataset. 
        
        This method connects to the SQLite database within the RSK file, retrieves
        channel information and measurement data, processes the timestamps, and
        organizes the data into a xarray Dataset. It also assigns long names and
        units as attributes to the dataset variables.
        """

        # Connect to the SQLite database in the RSK file
        con = sqlite3.connect( self.input_file )
        if con is None:
            raise ValueError(f"Could not open RSK file: {self.input_file}. " \
                             "Ensure it is a valid RSK file.")

        # Load channel information
        channels_df = self._read_channel_data(con)
        if channels_df.empty:
            raise ValueError("No channel data found in the RSK file.")

        # Create list with channel column names
        chan_cols = [f"channel{int(cid):02d}" for cid in channels_df['channelID']]

        # Load all measurement data
        df = self._read_measurement_data(con)
        if df.empty:
            raise ValueError("No measurement data found in the RSK file.")

        # Convert timestamp to datetime and set as index
        df['time'] = pd.to_datetime(df['tstamp'], unit='ms')
        df = df.set_index('time').drop(columns=['tstamp'])

        # Replace the columns with the "channelXX" names with the short names
        chan_cols = [f"channel{int(cid):02d}" for cid in channels_df['channelID']]
        used_names = {}
        rename_map = {}
        attribute_map = {}

        # Iterate over the channel columns and rename them according to the mapping
        for chan_col, short_name, long_name, units in zip(
                chan_cols,
                channels_df['shortName'],
                channels_df['longNamePlainText'],
                channels_df['units']):
            if chan_col in df.columns:
                base_name = long_name
                count = used_names.get(base_name, 0)
                if count == 0:
                    new_name = base_name
                else:
                    new_name = f"{base_name}_{count+1}"
                while new_name in rename_map.values() or new_name in df.columns:
                    count += 1
                    new_name = f"{base_name}_{count+1}"
                rename_map[chan_col] = new_name
                used_names[base_name] = count + 1

                # Hier das attribute_map befüllen:
                attribute_map[new_name] = {
                    "shortName": short_name,
                    "longName": long_name,
                    "units": units
                }
        df = df.rename(columns=rename_map)

        # Convert to an xarray.Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Add long names and units as attributes
        for var_name, attrs in attribute_map.items():
            if var_name in ds:
                ds[var_name].attrs['long_name'] = attrs.get('longName', '')
                ds[var_name].attrs['units'] = attrs.get('units', '')
                ds[var_name].attrs['short_name'] = attrs.get('shortName', '')

        # Add instrument information as global attributes
        instrument_info = self._read_instrument_data(con)
        if instrument_info:
            ds.attrs['instrument_model'] = instrument_info.get('model', '')
            ds.attrs['instrument_serial'] = instrument_info.get('serialID', '')
            ds.attrs['instrument_firmware_version'] = instrument_info.get('firmwareVersion', '')
            ds.attrs['instrument_firmware_type'] = instrument_info.get('firmwareType', '')
            if 'partNumber' in instrument_info:
                ds.attrs['instrument_part_number'] = instrument_info.get('partNumber', '')

        # Add database information as global attributes
        db_info = self._read_database_information(con)
        if db_info:
            ds.attrs['rsk_version'] = db_info.get('version', '')
            ds.attrs['rsk_type'] = db_info.get('type', '')

        # Perform default post-processing
        ds = self._perform_default_postprocessing(ds)

        # Store processed data
        self.data = ds

        # Close the database connection
        con.close()

    @staticmethod
    def format_key() -> str:
        return 'rbr-rsk-legacy'

    @staticmethod
    def format_name() -> str:
        return 'RBR RSK Legacy'

    @staticmethod
    def file_extension() -> str | None:
        return None
