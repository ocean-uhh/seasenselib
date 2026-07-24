"""Module for reading ADCP data from MATLAB .mat files converted from binaries recorded from UHH during DS cruises."""

from __future__ import annotations
import numpy as np
import xarray as xr
import pandas as pd
from datetime import datetime, timedelta
import re
import seasenselib.parameters as ctdparams
from seasenselib.readers.base import AbstractReader

class AdcpMatlabUhhdsReader(AbstractReader):
    """ Reads ADCP data from a matlab (.mat) file into a xarray Dataset. 

        This class is used to read ADCP files, which are stored in .mat files.
        The provided data is expected to be in a matlab format, and this reader
        is designed to detect the format, rename the variables under CF standards and create an xarra Dataset.
        As there are various versions of variable names and file structures,
        the reader will detect the version and parse accordingly.

        Attributes:
        ---------- 
        data : xr.Dataset
            The xarray Dataset containing the ADCP data previously stored in a .mat file.
        input_file : str
            The path to the input ADCP file containing the sensor data stored in MATLAB .mat file.

        Methods:
        -------
        __init__(input_file):
            Initializes the AdcpMatlabReader with the input file.
        __read():
            Reads the ADCP file and processes the data into an xarray Dataset.
        
        Properties
        ----------
        data : xr.Dataset (read-only)
            Returns the xarray Dataset containing the sensor data.
            For backward compatibility, get_data() method is also available but deprecated.
        
        _detect_format():
            Detects the format of the ADCP -mat input file and redirects accordingly.
        _parse_time():
            Handles different time formats in the ADCP .mat files.
        _add_time():
            Adds time coordinates to the dataset based on the detected format.
        _add_data_and_coords():
            Adds data variables and coordinates to the dataset based on the detected format.
        _add_metadata():
            Adds common metadata attributes to the dataset.
        """

    def __init__(self, input_file: str,
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize AdcpMatlabUhhDsReader.
        
        Parameters
        ----------
        input_file : str
            Path to the MAT file.
        mapping : dict, optional
            Variable name mapping dictionary.
        **kwargs
            Additional base class parameters:
            
            - input_header_file : str | None
                Path to separate header file (if applicable).
            - perform_default_postprocessing : bool, default=True
                Whether to perform default post-processing.
            - rename_variables : bool, default=True
                Whether to rename variables to standard names.
            - assign_metadata : bool, default=True
                Whether to assign CF-compliant metadata.
            - sort_variables : bool, default=True
                Whether to sort variables alphabetically.
        """
        super().__init__(input_file, mapping, **kwargs)
        self._format = None
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for MATLAB files."""
        return ('.mat',)

    def _load_data(self) -> xr.Dataset:
        """Load data from the MATLAB file and return an xarray Dataset."""
        import scipy.io

        # Load raw MATLAB data into temporary variable
        self._raw_matlab_data = scipy.io.loadmat(self.input_file, struct_as_record=False)
        self._format = self._detect_format()
        if not self._format:
            raise ValueError(f"Could not detect ADCP format in {self.input_file}.")
        data_vars, coords = self._add_data_and_coords()
        dataset = xr.Dataset(data_vars=data_vars, coords=coords)
        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(dataset.data_vars.keys()) + list(dataset.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset(dataset, key)
        
        return dataset

    def _detect_format(self):
        keys = self._raw_matlab_data.keys()
        if "dat_u" in keys and "dat_timesteps" in keys:
            return "v17"
        elif "SerYear" in keys and "RDIBin1Mid" in keys:
            return "v13"
        elif "DS_19_12_ndaysens" in keys and "DS_19_12_v" in keys:
            return "v12"
        elif "sens" in keys and "wt" in keys:
            return "v11"
        return None
    
    def _parse_time(self, arr, fmt):
        if fmt in ("v12", "v17"):
            time_raw = arr
            return pd.to_datetime(time_raw - 719529, unit="D")
        
        elif fmt == "v11":
            sens_struct = self._raw_matlab_data['sens']
            if isinstance(sens_struct, np.ndarray):
                sens_struct = sens_struct[0, 0]

            time_raw = sens_struct.time
            if hasattr(time_raw, 'flatten'):
                time_raw = time_raw.flatten()
    
            return pd.to_datetime(time_raw, unit='s', errors='coerce')
        elif fmt == "v13":
            year = self._raw_matlab_data['SerYear'].astype(np.int32).flatten()
            year = np.where(year > 50, year + 1900, year + 2000)
            month = self._raw_matlab_data['SerMon'].flatten()
            day = self._raw_matlab_data['SerDay'].flatten()
            hour = self._raw_matlab_data['SerHour'].flatten()
            minute = self._raw_matlab_data['SerMin'].flatten()
            second =  self._raw_matlab_data['SerSec'].flatten() + self._raw_matlab_data['SerHund'].flatten() / 100
            return pd.to_datetime({
                'year': year,
                'month': month,
                'day': day,
                'hour': hour,
                'minute': minute,
                'second': second
            })
    def _add_time(self):
        fmt = self._format
        if fmt == "v17":
            time = self._parse_time(self._raw_matlab_data["dat_timesteps"].flatten(), fmt)

        elif fmt == "v12":
            time = self._parse_time(self._raw_matlab_data["DS_19_12_ndaysens"].flatten(), fmt)
        
        elif fmt == "v13":
            time = self._parse_time(None, fmt)

        elif fmt == "v11":
            time = self._parse_time(self._raw_matlab_data['sens'], fmt)

        else:
            raise ValueError(f"Unsupported format {fmt} for time parsing.")
        return time
    
    def _add_data_and_coords(self):
        fmt = self._format
        data_vars = {}
        coords = {}
        time = self._add_time()

        if fmt == "v17":
            depth_bins = self._raw_matlab_data['dat_binrange'].flatten()
            coords = {
            ctdparams.TIME: time,
            "bin": depth_bins,
        }
            data_vars = {
                ctdparams.EAST_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data["dat_u"]),
                ctdparams.NORTH_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data["dat_v"]),
                ctdparams.UP_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data["dat_w"]),
                ctdparams.TEMPERATURE: (ctdparams.TIME, self._raw_matlab_data['dat_t'].flatten()),
                ctdparams.ECHO_INTENSITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['dat_echoa']),
                ctdparams.CORRELATION: ((ctdparams.TIME, "bin"), self._raw_matlab_data['dat_corra']),
                ctdparams.PITCH: (ctdparams.TIME, self._raw_matlab_data['dat_pitch'].flatten()),
                ctdparams.ROLL: (ctdparams.TIME, self._raw_matlab_data['dat_roll'].flatten()),
                ctdparams.HEADING: (ctdparams.TIME, self._raw_matlab_data['dat_head'].flatten()),
                ctdparams.BATTERY_VOLTAGE: (ctdparams.TIME, self._raw_matlab_data['dat_batt'].flatten()),
            }
        
        elif fmt == "v13":
            
            bin1_mid = np.squeeze(self._raw_matlab_data.get("RDIBin1Mid", [np.nan]))
            bin_size = np.squeeze(self._raw_matlab_data.get("RDIBinSize", [np.nan]))
            num_bins = self._raw_matlab_data['SerBins'].shape[1]
            depth = bin1_mid + bin_size * np.arange(num_bins)
            
            coords = {
            ctdparams.TIME: time,
            "bin": depth,
        }
            
            data_vars = {
                ctdparams.EAST_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerEmmpersec'] / 1000),  # mm/s to m/s
                ctdparams.NORTH_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerNmmpersec'] / 1000),
                ctdparams.UP_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerVmmpersec'] / 1000),
                ctdparams.TEMPERATURE: (ctdparams.TIME, self._raw_matlab_data['AnT100thDeg'].flatten() / 100),
                ctdparams.ECHO_INTENSITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerEA1cnt']),
                ctdparams.CORRELATION: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerC1cnt']),
                ctdparams.DIRECTION: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerDir10thDeg'] / 10),  # 10th degrees to degrees
                ctdparams.MAGNITUDE: ((ctdparams.TIME, "bin"), self._raw_matlab_data['SerMagmmpersec'] / 1000),
                ctdparams.PITCH: (ctdparams.TIME, self._raw_matlab_data['AnP100thDeg'].flatten() / 100),
                ctdparams.ROLL: (ctdparams.TIME, self._raw_matlab_data['AnR100thDeg'].flatten() / 100),
                ctdparams.HEADING: (ctdparams.TIME, self._raw_matlab_data['AnH100thDeg'].flatten() / 100),
                ctdparams.BATTERY_VOLTAGE: (ctdparams.TIME, self._raw_matlab_data['AnBatt'].flatten() / 10),  # Tenths of volts
        }
            
    
        elif fmt == "v12":

            depth_bins = self._raw_matlab_data['DS_19_12_binrange'].flatten()
            coords = {
            ctdparams.TIME: time,
            "bin": depth_bins,
        }
            
            data_vars = {
                ctdparams.EAST_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['DS_19_12_u']),
                ctdparams.NORTH_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['DS_19_12_v']),
                ctdparams.UP_VELOCITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['DS_19_12_w']),
                ctdparams.TEMPERATURE: (ctdparams.TIME, self._raw_matlab_data['DS_19_12_t'].flatten()),
                ctdparams.ECHO_INTENSITY: ((ctdparams.TIME, "bin"), self._raw_matlab_data['DS_19_12_echoa']),
                ctdparams.CORRELATION: ((ctdparams.TIME, "bin"), self._raw_matlab_data['DS_19_12_corra']),
                ctdparams.PITCH: (ctdparams.TIME, self._raw_matlab_data['DS_19_12_pitch'].flatten()),
                ctdparams.ROLL: (ctdparams.TIME, self._raw_matlab_data['DS_19_12_roll'].flatten()),
                ctdparams.HEADING: (ctdparams.TIME, self._raw_matlab_data['DS_19_12_head'].flatten()),
                ctdparams.BATTERY_VOLTAGE: (ctdparams.TIME, self._raw_matlab_data['DS_19_12_batt'].flatten()),
        }

        elif fmt == "v11":
            
            sens_struct = self._raw_matlab_data['sens']
            if isinstance(sens_struct, np.ndarray):
                sens_struct = sens_struct[0, 0]  # unwrap from ndarray container
            wt_struct = self._raw_matlab_data['wt']
            if isinstance(wt_struct, np.ndarray):
                wt_struct = wt_struct[0, 0]

            # Extract data from 'sens' and 'wt'
            salinity = sens_struct.s.flatten()
            temperature = sens_struct.t.flatten()
            pitch = sens_struct.p.flatten()
            roll = sens_struct.r.flatten()
            heading = sens_struct.h.flatten()
            battery_voltage = sens_struct.v.flatten()
            east_velocity_raw = wt_struct.vel
            
            # Reshape the data to (n_time, total_depth)
            n_time, n_depth, n_velocity_components = east_velocity_raw.shape
            total_depth = n_depth * n_velocity_components 
            east_velocity = east_velocity_raw.reshape(-1, total_depth)

            depth_bins = wt_struct.r.flatten()
            coords = {
                ctdparams.TIME: time,
                "depth_bin": depth_bins[:east_velocity.shape[1]],
            }

            # Organize data variables to return
            data_vars = {
                ctdparams.EAST_VELOCITY: ((ctdparams.TIME, "depth_bin"), east_velocity),
                ctdparams.TEMPERATURE: (ctdparams.TIME, temperature),
                ctdparams.SALINITY: (ctdparams.TIME, salinity),
                ctdparams.PITCH: (ctdparams.TIME, pitch),
                ctdparams.ROLL: (ctdparams.TIME, roll),
                ctdparams.HEADING: (ctdparams.TIME, heading),
                ctdparams.BATTERY_VOLTAGE: (ctdparams.TIME, battery_voltage),
            }

        return data_vars, coords
    
    def _add_metadata(self):
        # Add minimal source metadata (CF compliance handled by stages)
        self.dataset.attrs.update({
            "source": "Acoustic Doppler Current Profiler",
            "instrument": "ADCP",
        })

    @classmethod
    def format_key(cls) -> str:
        return 'adcp-matlab-uhhds'

    @classmethod
    def format_name(cls) -> str:
        return 'ADCP Matlab UHH DS'

    @classmethod
    def file_extension(cls) -> str | None:
        return None
