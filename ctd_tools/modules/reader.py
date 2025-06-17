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

    def _elapsed_seconds_since_offset_to_datetime(self, elapsed_seconds, offset_datetime):
            base_date = offset_datetime
            time_delta = timedelta(seconds=elapsed_seconds)
            return base_date + time_delta

    def _validate_necessary_parameters(self, data, longitude, latitude, entity: str):
        if not ctdparams.TIME and not ctdparams.TIME_J and not ctdparams.TIME_Q  and not ctdparams.TIME_N in data:
            raise ValueError(f"Parameter '{ctdparams.TIME}' is missing in {entity}.")
        if not ctdparams.PRESSURE in data and not ctdparams.DEPTH:
            raise ValueError(f"Parameter '{ctdparams.PRESSURE}' is missing in {entity}.")
        #if not ctdparams.DEPTH in data and not ctdparams.PRESSURE in data:
        #    raise ValueError(f"Parameter '{ctdparams.DEPTH}' is missing in {entity}.")
        #if not ctdparams.LATITUDE in data and not latitude:
        #    raise ValueError(f"Parameter '{ctdparams.LATITUDE}' is missing in {entity}.")
        #if not ctdparams.LONGITUDE in data and not longitude:
        #    raise ValueError(f"Parameter '{ctdparams.LONGITUDE}' is missing in {entity}.")

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
        elif ctdparams.TIME_S in xarray_data:
           time_coords = np.array([self._elapsed_seconds_since_offset_to_datetime(elapsed_seconds, offset_datetime) for elapsed_seconds in xarray_data[ctdparams.TIME_S]])
        else:
            timedelta = self.__get_scan_interval_in_seconds(cnv.header)
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

        # Check for bad flag
        bad_flag = self.__get_bad_flag(cnv.header)
        if bad_flag is not None:
            for var in ds:
                ds[var] = ds[var].where(ds[var] != bad_flag, np.nan)

        # Store processed data
        self.data = ds

class TobReader(AbstractReader):
    """ Reads CTD data from a TOB ASCII file (Sea & Sun) into a xarray Dataset. """

    def __init__(self, input_file, mapping = {}, encoding = 'latin-1'):
        super().__init__(input_file, mapping)
        self.encoding = encoding
        self.__read()

    def __read(self):
        ''' Reads a TOB file from Sea & Sun CTD into a xarray dataset. '''

        # Read the file
        with open(self.input_file, 'r', encoding=self.encoding) as file:
            lines = file.readlines()

        # Find the line with column names
        header_line_index = next((i for i, line in enumerate(lines) if line.startswith('; Datasets')), None)

        if header_line_index is None:
            raise ValueError("Line with column names not found in the file.")

        # Extract column names
        column_names = lines[header_line_index].strip().split()[1:]

        # Extract column units
        units = [None] + lines[header_line_index + 1].replace('[','').replace(']','').strip().split()[1:]

        # Load data into pandas DataFrame
        data_start_index = header_line_index + 3
        data = pd.read_csv(
            self.input_file,
            skiprows=data_start_index,
            delim_whitespace=True,
            names=column_names,
            parse_dates={ctdparams.TIME: ['IntD', 'IntT']},
            encoding=self.encoding,
        )

        # Convert DataFrame to xarray dataset
        ds = xr.Dataset.from_dataframe(data.set_index(ctdparams.TIME))

        # Assign units to data fields
        for index, name in enumerate(column_names):
            if name in ds and units[index]:
                ds[name].attrs['units'] = units[index]

        # Rename fields
        ds = ds.rename({
            'SALIN': ctdparams.SALINITY,
            'Temp': ctdparams.TEMPERATURE,
            'Cond': ctdparams.CONDUCTIVITY,
            'Press': ctdparams.PRESSURE,
            'SOUND': ctdparams.SPEED_OF_SOUND,
            'Vbatt': ctdparams.POWER_SUPPLY_INPUT_VOLTAGE,
            'SIGMA': 'sigma',
            'Datasets': 'sample',
        })

        # Convert pressure to depth
        pressure_in_dbar = ds['pressure'].values  # Extract pressure values from the dataset
        depth_in_meters = gsw.z_from_p(pressure_in_dbar, lat=53.8187)  # latitude is for Cuxhaven
        ds['depth'] = (('time',), depth_in_meters)  # Assuming the pressure varies with time
        ds['depth'].attrs['units'] = "m"

        # Ensure 'time' coordinate is datetime type
        ds[ctdparams.TIME] = pd.to_datetime(ds[ctdparams.TIME], errors='coerce')

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

class RbrAsciiReader(AbstractReader):

    def __init__(self, dat_file_path):
        self.dat_file_path = dat_file_path
        self.__read()

    def __create_xarray_dataset(self, df):
        """
        Converts a pandas DataFrame to an xarray Dataset.
        Assumes 'Datetime' as the index of the DataFrame, 
        which will be used as the time dimension.
        """

        # Ensure 'Datetime' is the index; if not, set it
        if 'time' not in df.index.names:
            df = df.set_index('time')

        # Rename columns as specified
        df.rename(columns=ctdparams.rename_list, inplace=True)

        # Convert DataFrame to xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)
            
        return ds

    def __parse_data(self, file_path):
        """
        Reads RBR data from a .dat file. Assumes that the actual data 
        starts after an empty line, with the first column being datetime 
        and the subsequent columns being the data entries.
        """
        # Open the file and read through it line by line until the data headers are found.
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        # Find the first non-empty line after metadata, which should be the header line for data columns.
        start_data_index = 0
        for i, line in enumerate(lines):
            if line.strip() == '':
                start_data_index = i + 1
                break
        
        # The line right after an empty line contains column headers. We need to handle it accordingly.
        header_line = lines[start_data_index].strip().split()
        header = header_line  # Assuming now 'Datetime' is handled in the next step
        
        # Now read the actual data, skipping rows up to and including the header line
        data = pd.read_csv(file_path, delimiter="\s+", names=['Date', 'Time'] + header, skiprows=start_data_index + 1)

        # Concatenate 'Date' and 'Time' columns to create a 'Datetime' column and convert it to datetime type
        data['time'] = pd.to_datetime(data['Date'] + ' ' + data['Time'], format='%Y/%m/%d %H:%M:%S')
        data.drop(['Date', 'Time'], axis=1, inplace=True)  # Remove the original 'Date' and 'Time' columns
        data.set_index('time', inplace=True)

        return data
    
    def __read(self):
        data = self.__parse_data(self.dat_file_path)
        ds = self.__create_xarray_dataset(data)
        self.data = ds

    def get_data(self):
        return self.data
    
class NortekAsciiReader(AbstractReader):
    """ Reads Nortek ASCII data from a .dat file into a xarray Dataset. """

    def __init__(self, dat_file_path, header_file_path):
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
                        import re
                        parts = re.split(r'\s{2,}', line.strip())  # Split based on two or more spaces

                        if len(parts) >= 2:
                            col_number = parts[0]
                            if parts[-1].startswith('(') and parts[-1].endswith(')'):
                                unit = parts[-1].strip('()')
                                col_name = ' '.join(parts[1:-1])
                            else:
                                unit = 'unknown'
                                col_name = ' '.join(parts[1:])
                        else:
                            # Fallback in case no unit is provided and the line is not correctly parsed
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
        df.rename(columns=ctdparams.rename_list, inplace=True)

        # Convert the DataFrame to an xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Renaming and CF meta data enrichment
        for header in headers:
            _, variable, unit = header

            # Rename
            if variable in ctdparams.rename_list.keys():
                variable = ctdparams.rename_list[variable]

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

class ADCPmatReader:
    def __init__(self, mat_file_path):
        self.mat_file_path = mat_file_path
        self.reader = self.__select_reader()
        if not self.reader:
            raise ValueError("Unsupported file format.")
        self.data = self.reader.get_data()

    def __select_reader(self):
        mat_data = scipy.io.loadmat(self.mat_file_path)
        
        # Distinguishing logic based on unique keys in mat_data
        if "dat_u" in mat_data and "dat_timesteps" in mat_data:
            return ADCPmatReader_17(self.mat_file_path)
        elif "SerYear" in mat_data and "RDIBin1Mid" in mat_data:
            return ADCPmatReader_13(self.mat_file_path)
        elif "DS_19_12_ndaysens" in mat_data and "DS_19_12_v" in mat_data:
            return ADCPmatReader_12_2(self.mat_file_path)#
        elif "sens" in mat_data and "wt" in mat_data:
            return ADCPmatReader_11(self.mat_file_path)
        # Add logic for a third or more formats
        else:
            return None  # Return None if no match is found

    def get_data(self):
        return self.data


class ADCPmatReader_17:
    def __init__(self, mat_file_path):
        self.mat_file_path = mat_file_path
        self.data = self.__read()

    def __parse_data(self, mat_file_path):
        # Load the MATLAB file
        mat_data = scipy.io.loadmat(mat_file_path)
        
        # Extract relevant data and prepare for xarray Dataset
        time = pd.to_datetime(mat_data['dat_timesteps'].flatten() - 719529, unit='D')
        depth_bins = mat_data['dat_binrange'].flatten()
        
        data_vars = {
            "east_velocity": (["time", "bin"], mat_data['dat_u']),
            "north_velocity": (["time", "bin"], mat_data['dat_v']),
            "up_velocity": (["time", "bin"], mat_data['dat_w']),
            "temperature": (["time"], mat_data['dat_t'].flatten()),
            "echo_intensity": (["time", "bin"], mat_data['dat_echoa']),  # Example variable
            "correlation": (["time", "bin"], mat_data['dat_corra']),  # Example variable
            "pitch": (["time"], mat_data['dat_pitch'].flatten()),
            "roll": (["time"], mat_data['dat_roll'].flatten()),
            "heading": (["time"], mat_data['dat_head'].flatten()),
            "battery_voltage": (["time"], mat_data['dat_batt'].flatten()),
        }
        
        coords = {
            "time": time,
            "bin": depth_bins,
        }
        
        return data_vars, coords

    def __create_xarray_dataset(self, data_vars, coords):
        # Create an xarray Dataset
        ds = xr.Dataset(data_vars, coords=coords)
        
        # Add metadata for CF compliance
        ds["east_velocity"].attrs = {"units": "m/s", "long_name": "Eastward velocity", "standard_name": "eastward_sea_water_velocity"}
        ds["north_velocity"].attrs = {"units": "m/s", "long_name": "Northward velocity", "standard_name": "northward_sea_water_velocity"}
        ds["up_velocity"].attrs = {"units": "m/s", "long_name": "Upward velocity", "standard_name": "upward_sea_water_velocity"}
        ds["temperature"].attrs = {"units": "°C", "long_name": "Temperature", "standard_name": "sea_water_temperature"}
        ds["echo_intensity"].attrs = {"units": "dB", "long_name": "Echo intensity"}
        ds["pitch"].attrs = {"units": "degrees", "long_name": "Pitch angle"}
        ds["roll"].attrs = {"units": "degrees", "long_name": "Roll angle"}
        ds["heading"].attrs = {"units": "degrees", "long_name": "Compass heading"}
        ds["battery_voltage"].attrs = {"units": "volts", "long_name": "Battery voltage"}
        
        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["title"] = "ADCP Data"
        ds.attrs["institution"] = "University of Hamburg"
        ds.attrs["source"] = "Acoustic Doppler Current Profiler"
        
        return ds

    def __read(self):
        data_vars, coords = self.__parse_data(self.mat_file_path)
        return self.__create_xarray_dataset(data_vars, coords)

    def get_data(self):
        return self.data


class ADCPmatReader_13:
    def __init__(self, mat_file_path):
        self.mat_file_path = mat_file_path
        self.data = self.__read()

    def __parse_data(self, mat_file_path):
        # Load the MATLAB file
        mat_data = scipy.io.loadmat(mat_file_path)

        # Extract time information
        time = pd.to_datetime({
            'year': mat_data['SerYear'].flatten() + 2000,
            'month': mat_data['SerMon'].flatten(),
            'day': mat_data['SerDay'].flatten(),
            'hour': mat_data['SerHour'].flatten(),
            'minute': mat_data['SerMin'].flatten(),
            'second': mat_data['SerSec'].flatten() + mat_data['SerHund'].flatten() / 100
        })

        # Calculate depth bins
        bin1_mid = mat_data['RDIBin1Mid'].item()
        bin_size = mat_data['RDIBinSize'].item()
        num_bins = mat_data['SerBins'].shape[1]
        depth_bins = bin1_mid + bin_size * (np.arange(num_bins))

        # Prepare data variables
        data_vars = {
            "east_velocity": (("time", "bin"), mat_data['SerEmmpersec'] / 1000),  # mm/s to m/s
            "north_velocity": (("time", "bin"), mat_data['SerNmmpersec'] / 1000),
            "up_velocity": (("time", "bin"), mat_data['SerVmmpersec'] / 1000),
            "echo_intensity": (("time", "bin"), mat_data['SerEA1cnt']),
            "correlation": (("time", "bin"), mat_data['SerC1cnt']),
            "direction": (("time", "bin"), mat_data['SerDir10thDeg'] / 10),  # 10th degrees to degrees
            "magnitude": (("time", "bin"), mat_data['SerMagmmpersec'] / 1000),
            "heading": (("time"), mat_data['AnH100thDeg'].flatten() / 100),
            "pitch": (("time"), mat_data['AnP100thDeg'].flatten() / 100),
            "roll": (("time"), mat_data['AnR100thDeg'].flatten() / 100),
            "temperature": (("time"), mat_data['AnT100thDeg'].flatten() / 100),
            "battery_voltage": (("time"), mat_data['AnBatt'].flatten() / 10),  # Tenths of volts
        }

        coords = {
            "time": time,
            "bin": depth_bins,
        }

        return data_vars, coords

    def __create_xarray_dataset(self, data_vars, coords):
        # Create an xarray Dataset
        ds = xr.Dataset(data_vars, coords=coords)

        # Add metadata for CF compliance
        ds["east_velocity"].attrs = {"units": "m/s", "long_name": "Eastward velocity", "standard_name": "eastward_sea_water_velocity"}
        ds["north_velocity"].attrs = {"units": "m/s", "long_name": "Northward velocity", "standard_name": "northward_sea_water_velocity"}
        ds["up_velocity"].attrs = {"units": "m/s", "long_name": "Upward velocity", "standard_name": "upward_sea_water_velocity"}
        ds["echo_intensity"].attrs = {"units": "dB", "long_name": "Echo intensity"}
        ds["correlation"].attrs = {"units": "", "long_name": "Correlation"}
        ds["direction"].attrs = {"units": "degrees", "long_name": "Current direction"}
        ds["magnitude"].attrs = {"units": "m/s", "long_name": "Current magnitude"}
        ds["heading"].attrs = {"units": "degrees", "long_name": "Heading"}
        ds["pitch"].attrs = {"units": "degrees", "long_name": "Pitch angle"}
        ds["roll"].attrs = {"units": "degrees", "long_name": "Roll angle"}
        ds["temperature"].attrs = {"units": "°C", "long_name": "Temperature", "standard_name": "sea_water_temperature"}
        ds["battery_voltage"].attrs = {"units": "volts", "long_name": "Battery voltage"}

        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["title"] = "ADCP Data"
        ds.attrs["institution"] = "University of Hamburg"
        ds.attrs["source"] = "Acoustic Doppler Current Profiler"

        return ds

    def __read(self):
        data_vars, coords = self.__parse_data(self.mat_file_path)
        return self.__create_xarray_dataset(data_vars, coords)

    def get_data(self):
        return self.data

class ADCPmatReader_12_2:
    def __init__(self, mat_file_path):
        self.mat_file_path = mat_file_path
        self.data = self.__read()

    def __parse_data(self, mat_file_path):
        # Load the MATLAB file
        mat_data = scipy.io.loadmat(mat_file_path)
        
        # Extract relevant data and prepare for xarray Dataset
        time = pd.to_datetime(mat_data['DS_19_12_ndaysens'].flatten() - 719529, unit='D')
        depth_bins = mat_data['DS_19_12_binrange'].flatten()
        
        data_vars = {
            "east_velocity": (["time", "bin"], mat_data['DS_19_12_u']),
            "north_velocity": (["time", "bin"], mat_data['DS_19_12_v']),
            "up_velocity": (["time", "bin"], mat_data['DS_19_12_w']),
            "temperature": (["time"], mat_data['DS_19_12_t'].flatten()),
            "echo_intensity": (["time", "bin"], mat_data['DS_19_12_echoa']),  # Example variable
            "correlation": (["time", "bin"], mat_data['DS_19_12_corra']),  # Example variable
            "pitch": (["time"], mat_data['DS_19_12_pitch'].flatten()),
            "roll": (["time"], mat_data['DS_19_12_roll'].flatten()),
            "heading": (["time"], mat_data['DS_19_12_head'].flatten()),
            "battery_voltage": (["time"], mat_data['DS_19_12_batt'].flatten()),
        }
        
        coords = {
            "time": time,
            "bin": depth_bins,
        }
        
        return data_vars, coords

    def __create_xarray_dataset(self, data_vars, coords):
        # Create an xarray Dataset
        ds = xr.Dataset(data_vars, coords=coords)
        
        # Add metadata for CF compliance
        ds["east_velocity"].attrs = {"units": "m/s", "long_name": "Eastward velocity", "standard_name": "eastward_sea_water_velocity"}
        ds["north_velocity"].attrs = {"units": "m/s", "long_name": "Northward velocity", "standard_name": "northward_sea_water_velocity"}
        ds["up_velocity"].attrs = {"units": "m/s", "long_name": "Upward velocity", "standard_name": "upward_sea_water_velocity"}
        ds["temperature"].attrs = {"units": "°C", "long_name": "Temperature", "standard_name": "sea_water_temperature"}
        ds["echo_intensity"].attrs = {"units": "dB", "long_name": "Echo intensity"}
        ds["pitch"].attrs = {"units": "degrees", "long_name": "Pitch angle"}
        ds["roll"].attrs = {"units": "degrees", "long_name": "Roll angle"}
        ds["heading"].attrs = {"units": "degrees", "long_name": "Compass heading"}
        ds["battery_voltage"].attrs = {"units": "volts", "long_name": "Battery voltage"}
        
        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["title"] = "ADCP Data"
        ds.attrs["institution"] = "University of Hamburg"
        ds.attrs["source"] = "Acoustic Doppler Current Profiler"
        
        return ds

    def __read(self):
        data_vars, coords = self.__parse_data(self.mat_file_path)
        return self.__create_xarray_dataset(data_vars, coords)

    def get_data(self):
        return self.data   

class ADCPmatReader_11:
    def __init__(self, mat_file_path):
        self.mat_file_path = mat_file_path
        self.data = self.__read()

    def __parse_data(self, mat_file_path):
        # Load the MATLAB file
        mat_data = scipy.io.loadmat(mat_file_path)
        
        # Extract data from 'sens' (sensor data)
        time_raw = mat_data['sens']['time'][0, 0].flatten()  # Convert to 1D array
        salinity = mat_data['sens']['s'][0, 0].flatten()  # Salinity data
        temperature = mat_data['sens']['t'][0, 0].flatten()  # Temperature data
        pitch = mat_data['sens']['p'][0, 0].flatten()  # Pitch angle
        roll = mat_data['sens']['r'][0, 0].flatten()  # Roll angle
        heading = mat_data['sens']['h'][0, 0].flatten()  # Heading
        battery_voltage = mat_data['sens']['v'][0, 0].flatten()  # Battery voltage

        # Extract depth-related data from 'wt' (water profile)
        depth_bins = mat_data['wt']['r'][0, 0].flatten()  # Depth bins (same as 'r')
        
        # Extract velocity data from 'wt'
        east_velocity_raw = mat_data['wt']['vel'][0, 0]  # Raw velocity data (shape: (n_time, n_depth, n_velocity_components))
        
        # Dynamically calculate the shape for reshaping based on the data
        n_time, n_depth, n_velocity_components = east_velocity_raw.shape
        total_depth = n_depth * n_velocity_components  # Total number of depth bins * velocity components

        # Reshape the data to (n_time, total_depth)
        east_velocity = east_velocity_raw.reshape(-1, total_depth)
        
        # Convert Unix time format (seconds since epoch) to pandas datetime
        time = pd.to_datetime(time_raw, unit='s', errors='coerce')
        
        # Create coordinate mappings
        coords = {
            "time": time,  # Flatten time to 1D
            "depth_bin": depth_bins[:east_velocity.shape[1]],  # Adjust depth_bins to match east_velocity depth
        }

        # Organize data variables to return
        data_vars = {
            "east_velocity": (["time", "depth_bin"], east_velocity),
            "temperature": (["time"], temperature),
            "salinity": (["time"], salinity),
            "pitch": (["time"], pitch),
            "roll": (["time"], roll),
            "heading": (["time"], heading),
            "battery_voltage": (["time"], battery_voltage),
        }

        return data_vars, coords

    def __create_xarray_dataset(self, data_vars, coords):
        # Create an xarray Dataset
        ds = xr.Dataset(data_vars, coords=coords)
        
        # Add metadata for CF compliance
        ds["east_velocity"].attrs = {"units": "m/s", "long_name": "Eastward velocity", "standard_name": "eastward_sea_water_velocity"}
        ds["temperature"].attrs = {"units": "°C", "long_name": "Temperature", "standard_name": "sea_water_temperature"}
        ds["salinity"].attrs = {"units": "psu", "long_name": "Salinity", "standard_name": "sea_water_salinity"}
        ds["pitch"].attrs = {"units": "degrees", "long_name": "Pitch angle"}
        ds["roll"].attrs = {"units": "degrees", "long_name": "Roll angle"}
        ds["heading"].attrs = {"units": "degrees", "long_name": "Compass heading"}
        ds["battery_voltage"].attrs = {"units": "volts", "long_name": "Battery voltage"}
        
        ds.attrs["Conventions"] = "CF-1.8"
        ds.attrs["title"] = "Modified ADCP Data"
        ds.attrs["institution"] = "University of Hamburg"
        ds.attrs["source"] = "Acoustic Doppler Current Profiler"
        
        return ds

    def __read(self):
        # Parse the data and create the dataset
        data_vars, coords = self.__parse_data(self.mat_file_path)
        return self.__create_xarray_dataset(data_vars, coords)

    def get_data(self):
        # Return the dataset created from the parsed data
        return self.data

