"""
Module for reading RCM data from MATLAB .mat files.
"""

from __future__ import annotations
import pandas as pd
import xarray as xr
import scipy
from ctd_tools.readers.base import AbstractReader

class RcmMatlabReader(AbstractReader):
    """Reader which converts RCM data stored in MATLAB .mat files into xarray dataset."""

    def __init__(self, input_file, mapping=None):
        super().__init__(input_file, mapping)
        self.__read()

    def __parse_data(self, mat_file_path):

        # read adcp file 
        data = scipy.io.loadmat(mat_file_path)

        #prepare for alteration
        def mat_to_dict(data):
            return {key: data[key].flatten()
                    if hasattr(data[key], 'flatten')
                    else data[key]
                    for key in data.keys()
            }
        data = mat_to_dict(data)

        # convert julian time to datetime
        data['time'] = pd.to_datetime(data['t'] - 719529, unit='D')
        
        # remove original julian time 
        data.pop('t')

        #create pandas dataframe 
        df = pd.DataFrame(dict([(key, pd.Series(value)) for key, value in data.items()]))

        # set time as index
        df.set_index('time', inplace=True)

        return df

    def __create_xarray_dataset(self, df):
        """create xarray dataset from pandas dataframe"""

        ds = xr.Dataset.from_dataframe(df)

        # rename variables after cf convention
        ds = ds.rename_vars({
            'u': 'east_velocity', 
            'v': 'north_velocity', 
            'temp': 'temperature', 
            'cond': 'conductivity', 
            'pres': 'pressure', 
            'vdir': 'vdir', 
            'vmag': 'vmag'
        })

        #add metadata for cf compliance
        ds["east_velocity"].attrs = {
            "units": "m/s", 
            "long_name": "Eastward velocity", 
            "standard_name": "eastward_sea_water_velocity"
        }
        ds["north_velocity"].attrs = {
            "units": "m/s", 
            "long_name": "Northward velocity", 
            "standard_name": "northward_sea_water_velocity"
        }
        ds["temperature"].attrs = {
            "units": "°C", 
            "long_name": "Temperature", 
            "standard_name": "sea_water_temperature"
        }
        ds['conductivity'].attrs = {
            "units": "S/m", 
            "long_name": "Conductivity", 
            "standard_name": "sea_water_conductivity"
        }
        ds['pressure'].attrs = {
            "units": "dbar", 
            "long_name": "Pressure", 
            "standard_name": "sea_water_pressure"
        }

        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["title"] = "RCM Data"
        ds.attrs["source"] = "Recording Current Meter - Aanderaa"

        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)
        return ds

    def __read(self):
        data = self.__parse_data(self.input_file)
        ds = self.__create_xarray_dataset(data)
        self.data = ds

    def get_data(self) -> xr.Dataset:
        return self.data

    @staticmethod
    def format_key() -> str:
        return 'rcm-matlab'

    @staticmethod
    def format_name() -> str:
        return 'RCM Matlab'

    @staticmethod
    def file_extension() -> str | None:
        return None
