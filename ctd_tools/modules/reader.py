import pycnv
import xarray as xr
import pandas as pd
import numpy as np
import gsw
import re
import csv
import sqlite3
import platform

from abc import ABC
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pyrsktools import RSK
from packaging.version import Version
from importlib.metadata import version

import ctd_tools.ctd_parameters as ctdparams

MODULE_NAME = 'ctd_tools'

class AbstractReader(ABC):
    """ Abstract super class for reading sensor data. 

    Must be subclassed to implement specific file format readers.
    
    Attributes
    ---------- 
    input_file : str
        The path to the input file containing sensor data.
    data : xr.Dataset | None
        The processed sensor data as a xarray Dataset, or None if not yet processed.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    perform_default_postprocessing : bool
        Whether to perform default post-processing on the data.
    rename_variables : bool
        Whether to rename xarray variables to standard names.
    assign_metadata : bool
        Whether to assign metadata to xarray variables.
    sort_variables : bool
        Whether to sort xarray variables by name.
    
    Methods
    -------
    __init__(input_file: str, mapping: dict | None = None, perform_default_postprocessing: bool = True,
                    rename_variables: bool = True, assign_metadata: bool = True, sort_variables: bool = True)
            Initializes the reader with the input file and optional mapping.
    _perform_default_postprocessing(ds: xr.Dataset) -> xr.Dataset
            Performs default post-processing on the xarray Dataset.
    get_data() -> xr.Dataset | None
            Returns the processed data as an xarray Dataset.
    """

    # The file type of the input data, to be specified by subclasses
    file_type = 'raw'

    # Attribute which indicates whether to perform default post-processing
    perform_default_postprocessing = True

    # Attribute to indicate whether to rename xarray variables to standard names
    rename_variables = True

    # Attribute to indicate whether to assign CF metadata to xarray variables
    assign_metadata = True

    # Attribute to indicate whether to sort xarray variables by name
    sort_variables = True

    def __init__(self, input_file: str, mapping: dict | None = None, perform_default_postprocessing: bool = True, 
                 rename_variables: bool = True, assign_metadata: bool = True, sort_variables: bool = True):
        """Initializes the AbstractReader with the input file and optional mapping.

        This constructor sets the input file, initializes the data attribute to None,
        and sets the mapping for variable names. It also allows for configuration of
        default post-processing, renaming of variables, assignment of metadata, and sorting of variables.

        Parameters
        ---------- 
        input_file : str
            The path to the input file containing sensor data.
        mapping : dict, optional
            A dictionary mapping names used in the input file to standard names.
        perform_default_postprocessing : bool, optional
            Whether to perform default post-processing on the data. Default is True.
        rename_variables : bool, optional
            Whether to rename xarray variables to standard names. Default is True.
        assign_metadata : bool, optional
            Whether to assign CF metadata to xarray variables. Default is True.
        sort_variables : bool, optional
            Whether to sort xarray variables by name. Default is True.
        """

        self.input_file = input_file
        self.data = None
        self.mapping = mapping
        self.perform_default_postprocessing = perform_default_postprocessing
        self.rename_variables = rename_variables
        self.assign_metadata = assign_metadata
        self.sort_variables = sort_variables

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
        # Check for numbered standard names (e.g., temperature_1, temperature_2)
        base_key = key
        m = re.match(r"^([a-zA-Z0-9_]+?)(?:_\d{1,2})?$", key)
        if m:
            base_key = m.group(1)
        # Use metadata for base_key if available
        if base_key in ctdparams.metadata:
            for attribute, value in ctdparams.metadata[base_key].items():
                if attribute not in ds[key].attrs:
                    ds[key].attrs[attribute] = value
        if unit:
            ds[key].attrs['units'] = unit
        if label:
            if unit:
                label = label.replace(f"[{unit}]", '').strip() # Remove unit from label
            ds[key].attrs['long_name'] = label

    def _sort_xarray_variables(self, ds: xr.Dataset) -> xr.Dataset:
        """Sorts the variables in an xarray Dataset based on their standard names.

        The sorting is done in a way that ensures that variables with the same base name
        (e.g., temperature_1, temperature_2) are grouped together.

        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to be sorted.

        Returns
        -------
        xr.Dataset
            The xarray Dataset with variables sorted by their names.
        """
        # Sort all variables and coordinates by name
        all_names = sorted(list(ds.data_vars) + list(ds.coords))

        # Create a new Dataset with sorted variables and coordinates
        ds_sorted = ds[all_names]

        # Ensure that the attributes are preserved
        ds_sorted.attrs = ds.attrs.copy()

        return ds_sorted

    def _rename_xarray_parameters(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Rename variables in an xarray.Dataset according to ctdparams.default_mappings.
        Handles aliases with or without trailing numbering and ensures unique standard names with numbering.
        If a standard name only occurs once, it will not have a numbering suffix.
        """
        import re
        ds_vars = list(ds.variables)
        rename_dict = {}

        # Build a reverse mapping: alias_lower -> standard_name
        alias_to_standard = {}
        for standard_name, aliases in ctdparams.default_mappings.items():
            for alias in aliases:
                alias_to_standard[alias.lower()] = standard_name

        # First, collect all matches: (standard_name, original_var, suffix)
        matches = []
        for var in ds_vars:
            var_lower = var.lower()
            matched = False
            for alias_lower, standard_name in alias_to_standard.items():
                # Match alias with optional _<number> at the end
                m = re.match(rf"^{re.escape(alias_lower)}(_?\d{{1,2}})?$", var_lower)
                if m:
                    suffix = m.group(1) or ""
                    matches.append((standard_name, var, suffix))
                    matched = True
                    break
            if not matched:
                continue

        # Group by standard_name
        from collections import defaultdict
        grouped = defaultdict(list)
        for standard_name, var, suffix in matches:
            grouped[standard_name].append((var, suffix))

        # Assign new names: only add numbering if there are multiple
        for standard_name, vars_with_suffixes in grouped.items():
            if len(vars_with_suffixes) == 1:
                # Only one variable: use plain standard name
                rename_dict[vars_with_suffixes[0][0]] = standard_name
            else:
                # Multiple variables: always add numbering (_1, _2, ...)
                for idx, (var, suffix) in enumerate(vars_with_suffixes, 1):
                    rename_dict[var] = f"{standard_name}_{idx}"

        return ds.rename(rename_dict)

    def _assign_default_global_attributes(self, ds: xr.Dataset) -> xr.Dataset:
        """Assigns default global attributes to the xarray Dataset.

        This method sets the global attributes for the xarray Dataset, including
        the title, institution, source, and other relevant metadata.

        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to which the global attributes will be assigned.
        """

        module_name = MODULE_NAME
        module_version = version(MODULE_NAME)
        module_reader_class = self.__class__.__name__
        python_version = platform.python_version()
        input_file = self.input_file
        input_file_type = self.file_type
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # assemble history entry
        history_entry = (
            f"{timestamp}: created from {input_file_type} file ({input_file}) "
            f"using {module_name} v{module_version} ({module_reader_class} class) "
            f"under Python {python_version}"
        )

        ds.attrs['history'] = history_entry
        ds.attrs['Conventions'] = 'CF-1.8'

        # Information about the processor of the xarray dataset
        ds.attrs['processor_name'] = module_name
        ds.attrs['processor_version'] = module_version
        ds.attrs['processor_reader_class'] = module_reader_class
        ds.attrs['processor_python_version'] = python_version
        ds.attrs['processor_input_filename'] = input_file
        ds.attrs['processor_input_file_type'] = input_file_type

        return ds

    def _perform_default_postprocessing(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Perform default post-processing on the xarray Dataset.
        This includes renaming variables and assigning metadata.

        Parameters
        ----------
        ds : xr.Dataset
            The xarray Dataset to be processed.

        Returns
        -------
        xr.Dataset
            The processed xarray Dataset.
        """

        # Apply custom mapping of variable names if provided
        if self.mapping is not None:
            for key, value in self.mapping.items():
                if value in ds.variables:
                    ds = ds.rename({value: key})

        # Rename variables according to default mappings
        if self.rename_variables:
            ds = self._rename_xarray_parameters(ds)

        # Assign metadata for all attributes of the xarray Dataset
        if self.assign_metadata:
            for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
                self._assign_metadata_for_key_to_xarray_dataset(ds, key)

        # Assign default global attributes
        ds = self._assign_default_global_attributes(ds)

        # Sort variables and coordinates by name
        if self.sort_variables:
            ds = self._sort_xarray_variables(ds)

        return ds   

    def get_data(self) -> xr.Dataset | None:
        """ Returns the processed data as an xarray Dataset. """
        return self.data


class CnvReader(AbstractReader):
    """ Reads CTD data from a CNV file into a xarray Dataset. """

    file_type = 'SBE CNV'

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

    file_type = 'Sea & Sun TOB'

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

    file_type = 'netCDF'

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

    file_type = 'CSV'

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

    file_type = 'RBR ASCII'

    def __init__(self, input_file : str, mapping : dict | None = None):
        super().__init__(input_file, mapping)
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
        #df.rename(columns=ctdparams.rename_list, inplace=True)

        # Convert DataFrame to xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        # Perform default post-processing
        ds = self._perform_default_postprocessing(ds)
            
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
        data = self.__parse_data(self.input_file)
        ds = self.__create_xarray_dataset(data)
        self.data = ds

    def get_data(self):
        return self.data
    
class NortekAsciiReader(AbstractReader):
    """ Reads Nortek ASCII data from a .dat file into a xarray Dataset. """

    file_type = 'Nortek ASCII'

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

    file_type = 'RBR RSK'

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
        
        This method retrieves the instrument information from the database and returns it as a dictionary.

        Parameters
        ----------
        con : sqlite3.Connection
            The SQLite connection object to the RSK file.

        Returns
        -------
        dict
            A dictionary containing instrument information such as instrumentID, serialID, model, firmwareVersion,
            firmwareType, and partNumber. If no instrument data is found, an empty dictionary is returned.
        """
        query = "SELECT * FROM instruments"
        df = pd.read_sql_query(query, con)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}

    def _read_database_information(self, con: sqlite3.Connection) -> dict:
        """ Reads database information from the RSK file. 
        
        This method retrieves the database information from the database and returns it as a dictionary.

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
            A DataFrame containing measurement data with columns: tstamp and channelXX for each channel.
            The DataFrame contains all measurement data from the 'data' table in the RSK file
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
            raise ValueError(f"Could not open RSK file: {self.input_file}. Ensure it is a valid RSK file.")

        # Load channel information
        channels_df = self._read_channel_data(con)
        if channels_df.empty:
            raise ValueError("No channel data found in the RSK file.")
        print(channels_df)

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

class RbrRskReader(AbstractReader):
    """
    Reads sensor data from a RBR .rsk file into a xarray Dataset.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    input_file : str
        The path to the input file containing the RBR legacy data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    """

    file_type = 'RBR RSK'

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

    def __read(self):
        """ Reads a RSK file and converts it to a xarray Dataset. 

        This method uses the pyrsktools library to read the RSK file, extracts
        channel information and measurement data, processes the timestamps, and
        organizes the data into a xarray Dataset. It also assigns metadata 
        according to the CF conventions to the dataset variables.
        """

        # Open the RSK file and read the data
        rsk = RSK(self.input_file)
        rsk.open()
        rsk.readdata()
        rsk.close()

        # Convert array to xarray Dataset
        ds = xr.Dataset(
            data_vars={name: (['time'], rsk.data[name]) for name in rsk.channelNames},
            coords={ctdparams.TIME: pd.to_datetime(rsk.data['timestamp'], unit='s')}
        )

        # Assign metadata to the dataset variables
        # For this, iterate over rsk.channels and look for channel name = longName.
        # Then assign _dbName, shortName, channelID, feModuleType, feModuleVersion,
        # units, label, shortName as attributes to the dataset variables.
        for channel in rsk.channels:
            if channel.longName in ds:
                attrs = {
                    'rsk_channel_id': channel.channelID,
                    'rsk_long_name': channel.longName,
                    'rsk_short_name': channel.shortName,
                    'rsk_label': channel.label,
                    'rsk_dbName': channel._dbName,
                    'rsk_units': channel.units,
                    'rsk_units_plain_text': channel.unitsPlainText,
                    'rsk_fe_module_type': channel.feModuleType,
                    'rsk_fe_module_version': channel.feModuleVersion,
                    'rsk_is_measured': channel.isMeasured,
                    'rsk_is_derived': channel.isDerived,
                }
                ds[channel.longName].attrs.update(attrs)

        # Add instrument information as global attributes
        instrument_info = rsk.instrument
        if instrument_info:
            attrs = {
                'instrument_model': instrument_info.model,
                'instrument_serial': instrument_info.serialID,
                'instrument_firmware_version': instrument_info.firmwareVersion,
                'instrument_firmware_type': instrument_info.firmwareType,
            }
            ds.attrs.update(attrs)
            if getattr(instrument_info, "partNumber", None):
                ds.attrs['instrument_part_number'] = instrument_info.partNumber

        # Add database information as global attributes
        db_info = rsk.dbInfo
        if db_info:
            ds.attrs['rsk_version'] = db_info.version
            ds.attrs['rsk_type'] = db_info.type

        # Perform default post-processing
        ds = self._perform_default_postprocessing(ds)

        # Store processed data
        self.data = ds

class RbrRskAutoReader(AbstractReader):
    """
    Facade for reading RBR .rsk files, automatically selecting the correct reader
    based on the file's type and version.

    This class checks the type and version of the RSK file and initializes either
    the RbrRskReader for modern files or the RbrRskLegacyReader for legacy files.
    It reads the data and returns it as an xarray Dataset.      

    Attributes
    ----------
    input_file : str
        The path to the input file containing the RBR data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    data : xr.Dataset | None
        The processed sensor data as an xarray Dataset, or None if not yet processed.

    Methods
    -------
    get_data() -> xr.Dataset | None
        Returns the processed data as an xarray Dataset.
    _select_and_read()
        Selects the appropriate reader based on the RSK file type and version,
        and reads the data into an xarray Dataset.
    """

    def __init__(self, input_file: str, mapping: dict | None = None):
        super().__init__(input_file, mapping)
        self._select_and_read()

    def _select_and_read(self):
        """ Selects the appropriate reader based on the RSK file type and version.

        This method connects to the SQLite database within the RSK file, checks the
        type and version of the database, and initializes either the RbrRskReader
        or the RbrRskLegacyReader accordingly. 
        """

        # Connect to the SQLite database of the RSK file to check type and version
        con = sqlite3.connect(self.input_file)
        try:
            dbinfo = con.execute("SELECT type, version FROM dbInfo").fetchone()
            if dbinfo is None:
                raise ValueError("dbInfo table not found in RSK file.")
            db_type, db_version = dbinfo
        finally:
            con.close()

        # Check if version is >= minimum supported
        is_modern = (
            (db_type.lower() == "full" and Version(db_version) >= Version("2.0.0")) or
            (db_type.lower() == "epdesktop" and Version(db_version) >= Version("1.13.4"))
        )

        # Select the appropriate reader based on the type and version
        if is_modern:
            reader = RbrRskReader(self.input_file, self.mapping)
        else:
            reader = RbrRskLegacyReader(self.input_file, self.mapping)

        # Read the data using the selected reader
        self.data = reader.get_data()
        self.file_type = reader.file_type
