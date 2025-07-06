"""
Module for reading CTD data from SBE CNV files.
"""

import re
from datetime import datetime
import pycnv
import pandas as pd
import numpy as np
import gsw

from ctd_tools.readers.base import AbstractReader
import ctd_tools.parameters as params


class SbeCnvReader(AbstractReader):
    """ Reads sensor data from a SeaBird CNV file into a xarray Dataset. 

    This class is used to read SeaBird CNV files, which are commonly used for storing
    sensor data. The provided data is expected to be in a CNV format, and this reader
    is designed to parse that format correctly.

    Attributes:
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be read from the CNV file.
    input_file : str
        The path to the input CNV file containing the sensor data.
    mapping : dict
        A mapping dictionary for renaming variables or attributes in the dataset.

    Methods:
    -------
    __init__(input_file, mapping = {}):
        Initializes the CnvReader with the input file and optional mapping.
    __read():
        Reads the CNV file and processes the data into an xarray Dataset.
    __get_scan_interval_in_seconds(string):
        Extracts the scan interval in seconds from the CNV file header.
    __get_bad_flag(string):
        Extracts the bad flag from the CNV file header.
    file_type: str
        The type of the file being read, which is 'SBE CNV'.
    _file_extension: str
        The file extension for this reader, which is '.cnv'.
    get_data():
        Returns the xarray Dataset containing the sensor data.
    get_file_type():
        Returns the type of the file being read, which is 'SBE CNV'.
    get_file_extension():
        Returns the file extension for this reader, which is '.cnv'.
    """

    def __init__(self, input_file, mapping = None):
        super().__init__(input_file, mapping)
        self.__read()

    def __get_scan_interval_in_seconds(self, string):
        pattern = r'^# interval = seconds: ([\d.]+)$'
        match = re.search(pattern, string, re.MULTILINE)
        if match:
            seconds = float(match.group(1))
            return seconds
        return None

    def __get_bad_flag(self, string):
        pattern = r'^# bad_flag = (.+)$'
        match = re.search(pattern, string, re.MULTILINE)
        if match:
            bad_flag = match.group(1)
            return bad_flag
        return None

    def __read(self):
        """ Reads a CNV file """

        # Read CNV file with pycnv reader
        cnv = pycnv.pycnv(self.input_file)

        # Map column names ('channel names') to standard names
        channel_names = [d['name'] for d in cnv.channels if 'name' in d]
        for key, values in params.default_mappings.items():
            if key not in self.mapping:
                for value in values:
                    if value in channel_names:
                        self.mapping[key] = value
                        break
        # Validate required parameters
        super()._validate_necessary_parameters(self.mapping, cnv.lat, cnv.lon, 'mapping data')

        # Create dictionaries with data, names, and labels
        xarray_data = dict()
        xarray_labels = dict()
        xarray_units = dict()
        for k, v in self.mapping.items():
            xarray_data[k] = cnv.data[v][:]
            xarray_labels[k] = cnv.names[v]
            xarray_units[k] = cnv.units[v]
            maxCount = len(cnv.data[v])

        # Define the offset date and time
        offset_datetime = pd.to_datetime( cnv.date.strftime("%Y-%m-%d %H:%M:%S") )

        # Define the time coordinates as an array of datetime values
        if params.TIME_J in xarray_data:
            year_startdate = datetime(year=offset_datetime.year, month=1, day=1)
            time_coords = np.array([self._julian_to_gregorian(jday, year_startdate) \
                                    for jday in xarray_data[params.TIME_J]])
        elif params.TIME_Q in xarray_data:
            time_coords = np.array([self._elapsed_seconds_since_jan_2000_to_datetime(elapsed_seconds) \
                                    for elapsed_seconds in xarray_data[params.TIME_Q]])
        elif params.TIME_N in xarray_data:
            time_coords = np.array([self._elapsed_seconds_since_jan_1970_to_datetime(elapsed_seconds) \
                                    for elapsed_seconds in xarray_data[params.TIME_N]])
        elif params.TIME_S in xarray_data:
           time_coords = np.array([self._elapsed_seconds_since_offset_to_datetime(elapsed_seconds, offset_datetime) \
                                   for elapsed_seconds in xarray_data[params.TIME_S]])
        else:
            timedelta = self.__get_scan_interval_in_seconds(cnv.header)
            if timedelta:
                time_coords = [offset_datetime + pd.Timedelta(seconds=i*timedelta) for i in range(maxCount)][:]

        # Calculate depth from pressure and latitude
        depth = None
        if params.PRESSURE in xarray_data:
            lat = cnv.lat
            lon = cnv.lon
            if lat == None and params.LATITUDE in xarray_data:
                lat = xarray_data[params.LATITUDE][0]
            if lon == None and params.LONGITUDE in xarray_data:
                lon = xarray_data[params.LONGITUDE][0]
            depth = gsw.conversions.z_from_p(xarray_data[params.PRESSURE], cnv.lat)

        # Create xarray Dataset
        ds = self._get_xarray_dataset_template(time_coords, depth, cnv.lat, cnv.lon)

        # Derive parameters if temperature, pressure, and salinity are given
        if params.TEMPERATURE in xarray_data and params.PRESSURE in \
                xarray_data and params.SALINITY in xarray_data:
            # Derive density
            ds['density'] = ([params.TIME], gsw.density.rho(
                xarray_data[params.SALINITY], xarray_data[params.TEMPERATURE], 
                    xarray_data[params.PRESSURE]))
            # Derive potential temperature
            ds['potential_temperature'] = ([params.TIME], gsw.pt0_from_t(
                xarray_data[params.SALINITY], xarray_data[params.TEMPERATURE], 
                    xarray_data[params.PRESSURE]))
        
        # Assign parameter values and meta information for each 
        # parameter to xarray Dataset
        for key in self.mapping.keys():
            super()._assign_data_for_key_to_xarray_dataset(ds, key, xarray_data[key])
            super()._assign_metadata_for_key_to_xarray_dataset(
                ds, key, xarray_labels[key], xarray_units[key]
            )
        
        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        # Check for bad flag
        bad_flag = self.__get_bad_flag(cnv.header)
        if bad_flag is not None:
            for var in ds:
                ds[var] = ds[var].where(ds[var] != bad_flag, np.nan)

        # Store processed data
        self.data = ds

    @staticmethod
    def format_key() -> str:
        return 'sbe-cnv'

    @staticmethod
    def format_name() -> str:
        return 'SeaBird CNV'

    @staticmethod
    def file_extension() -> str | None:
        return '.cnv'
