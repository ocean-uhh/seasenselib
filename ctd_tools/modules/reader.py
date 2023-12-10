import pycnv
import xarray as xr
import pandas as pd
import numpy as np
import gsw
import re
import csv

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
import ctd_tools.ctd_parameters as ctdparams


class AbstractReader(ABC):
    """ Abstract super class for reading CTD data. """

    def __init__(self, input_file: str, mapping = None):
        self.input_file = input_file
        self.data = None
        self.mapping = mapping

    def _julian_to_gregorian(self, julian_days, start_date):
        full_days = int(julian_days)
        seconds = (julian_days - full_days) * 24 * 60 * 60
        return start_date + timedelta(days=full_days, seconds=seconds)

    def _elapsed_seconds_since_jan_1970_to_datetime(self, elapsed_seconds):
            base_date = datetime(1970, 1, 1)
            time_delta = timedelta(seconds=elapsed_seconds)
            return base_date + time_delta

    def _elapsed_seconds_since_jan_2000_to_datetime(self, elapsed_seconds):
        base_date = datetime(2000, 1, 1)
        time_delta = timedelta(seconds=elapsed_seconds)
        return base_date + time_delta

    def _validate_necessary_parameters(self, data, longitude, latitude, entity: str):
        if not ctdparams.TIME and not ctdparams.TIME_J and not ctdparams.TIME_Q  and not ctdparams.TIME_N in data:
            raise ValueError(f"Parameter '{ctdparams.TIME}' is missing in {entity}.")
        if not ctdparams.PRESSURE in data and not ctdparams.DEPTH:
            raise ValueError(f"Parameter '{ctdparams.PRESSURE}' is missing in {entity}.")
        #if not ctdparams.DEPTH in data and not ctdparams.PRESSURE in data:
        #    raise ValueError(f"Parameter '{ctdparams.DEPTH}' is missing in {entity}.")
        if not ctdparams.LATITUDE in data and not latitude:
            raise ValueError(f"Parameter '{ctdparams.LATITUDE}' is missing in {entity}.")
        if not ctdparams.LONGITUDE in data and not longitude:
            raise ValueError(f"Parameter '{ctdparams.LONGITUDE}' is missing in {entity}.")

    def _get_xarray_dataset_template(self, time_array, depth_array, 
                latitude, longitude):
        return xr.Dataset(
            data_vars = dict(), 
            coords = dict(
                time = time_array,
                depth = ([ctdparams.TIME], depth_array),
                latitude = latitude,
                longitude = longitude,
            ), attrs = dict(
                latitude = latitude,
                longitude = longitude,
                CreateTime = datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                DataType = 'TimeSeries',
            )
        )
    
    def _assign_data_for_key_to_xarray_dataset(self, ds: xr.Dataset, key:str, data):
        ds[key] = xr.DataArray(data, dims=ctdparams.TIME)
        ds[key].attrs = {}

    def _assign_metadata_for_key_to_xarray_dataset(self, ds: xr.Dataset, key: str, 
                label = None, unit = None):
        if not ds[key].attrs:
            ds[key].attrs = {}
        if key in ctdparams.metadata:
            for attribute, value in ctdparams.metadata[key].items():
                if attribute not in ds[key].attrs:
                    ds[key].attrs[attribute] = value
        if unit:
            ds[key].attrs['units'] = unit
        if label:
            if unit:
                label = label.replace(f"[{unit}]", '').strip() # Remove unit from label
            ds[key].attrs['long_name'] = label
    
    def get_data(self) -> xr.Dataset:
        return self.data


class CnvReader(AbstractReader):
    """ Reads CTD data from a CNV file into a xarray Dataset. """

    def __init__(self, input_file, mapping = {}):
        super().__init__(input_file, mapping)
        self.__read()

    def __get_scan_interval_in_seconds(self, string):
        pattern = r'^# interval = seconds: ([\d.]+)$'
        match = re.search(pattern, string, re.MULTILINE)
        if match:
            seconds = float(match.group(1))
            return seconds
        return None

    def __read(self):
        """ Reads a CNV file """

        # Read CNV file with pycnv reader
        cnv = pycnv.pycnv(self.input_file)

        # Map column names ('channel names') to standard names
        channel_names = [d['name'] for d in cnv.channels if 'name' in d]
        for key, values in ctdparams.default_mappings.items():
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
        if ctdparams.TIME_J in xarray_data:
            year_startdate = datetime(year=offset_datetime.year, month=1, day=1)
            time_coords = np.array([self._julian_to_gregorian(jday, year_startdate) for jday in xarray_data[ctdparams.TIME_J]])
        elif ctdparams.TIME_Q in xarray_data:
            time_coords = np.array([self._elapsed_seconds_since_jan_2000_to_datetime(elapsed_seconds) for elapsed_seconds in xarray_data[ctdparams.TIME_Q]])
        elif ctdparams.TIME_N in xarray_data:
            time_coords = np.array([self._elapsed_seconds_since_jan_1970_to_datetime(elapsed_seconds) for elapsed_seconds in xarray_data[ctdparams.TIME_Q]])
        else:
            timedelta = self.__get_scan_interval_in_seconds(cnv.raw_header())
            if timedelta:
                time_coords = [offset_datetime + pd.Timedelta(seconds=i*timedelta) for i in range(maxCount)][:]

        # Calculate depth from pressure and latitude
        depth = None
        if ctdparams.PRESSURE in xarray_data:
            lat = cnv.lat
            lon = cnv.lon
            if lat == None and ctdparams.LATITUDE in xarray_data:
                lat = xarray_data[ctdparams.LATITUDE][0]
            if lon == None and ctdparams.LONGITUDE in xarray_data:
                lon = xarray_data[ctdparams.LONGITUDE][0]
            depth = gsw.conversions.z_from_p(xarray_data[ctdparams.PRESSURE], cnv.lat)

        # Create xarray Dataset
        ds = self._get_xarray_dataset_template(time_coords, depth, cnv.lat, cnv.lon)

        # Derive parameters if temperature, pressure, and salinity are given
        if ctdparams.TEMPERATURE in xarray_data and ctdparams.PRESSURE in \
                xarray_data and ctdparams.SALINITY in xarray_data:
            # Derive density
            ds['density'] = ([ctdparams.TIME], gsw.density.rho(
                xarray_data[ctdparams.SALINITY], xarray_data[ctdparams.TEMPERATURE], 
                    xarray_data[ctdparams.PRESSURE]))
            # Derive potential temperature
            ds['potential_temperature'] = ([ctdparams.TIME], gsw.pt0_from_t(
                xarray_data[ctdparams.SALINITY], xarray_data[ctdparams.TEMPERATURE], 
                    xarray_data[ctdparams.PRESSURE]))
        
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

        # Store processed data
        self.data = ds


class NetCdfReader(AbstractReader):
    """ Reads CTD data from a netCDF file into a xarray Dataset. """

    def __init__(self, input_file):
        super().__init__(input_file)
        self.__read()

    def __read(self):
        # Read from netCDF file
        self.data = xr.open_dataset(self.input_file)

        # Validation
        super()._validate_necessary_parameters(self.data, None, None, 'netCDF file')


class CsvReader(AbstractReader):
    """ Reads CTD data from a CSV file into a xarray Datset. """

    def __init__(self, input_file):
        super().__init__(input_file)
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
            data[ctdparams.TIME] = [
                datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f') for timestamp in data[ctdparams.TIME]
            ]
            
            # Convert all other columns to floats
            for key in data.keys():
                if key != ctdparams.TIME and key in ctdparams.default_mappings: 
                    data[key] = [float(value) for value in data[key]]

            # Create xarray Dataset
            ds = self._get_xarray_dataset_template( 
                data[ctdparams.TIME],data[ctdparams.DEPTH],
                data[ctdparams.LATITUDE][0], data[ctdparams.LONGITUDE][0]
            )

            # Assign parameter values and meta information for each parameter to xarray Dataset
            for key in data.keys():
                super()._assign_data_for_key_to_xarray_dataset(ds, key, data[key])
                super()._assign_metadata_for_key_to_xarray_dataset( ds, key )
    
            # Store processed data
            self.data = ds
