"""
Module for reading RBR RSK data from MATLAB files.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import xarray as xr
from seasenselib.readers.base import AbstractReader
import seasenselib.parameters as params


class RbrMatlabRsktoolsReader(AbstractReader):
    """
    Reader for Matlab files created with RBR RSKtools.

    This class converts RSK structures (created with RSK2MAT.m from RBR RSKtools) 
    into xarray Datasets with separate variables for each sensor channel.
    """

    def __init__(self, input_file: str,
                 time_dim: str = params.TIME,
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize RbrMatlabRsktoolsReader.
        
        Parameters
        ----------
        input_file : str
            Path to the MAT file.
        time_dim : str, default=params.TIME
            Name of the time dimension in the output dataset.
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
        self._time_dim = time_dim
        # Instrument information (private - used only during parsing)
        self._instrument_info = {}
        self._channels_info = {}
        self._epochs_info = {}
        super().__init__(input_file, mapping, **kwargs)
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for MATLAB files."""
        return ('.mat',)

    @classmethod
    def reader_args(cls) -> list[dict]:
        return []

    def _parse_rsk_data(self, mat_file_path : str) -> xr.Dataset:
        """
        Parse RSK MATLAB file into xarray Dataset.
        
        Parameters
        ----------
        mat_file_path : str
            Path to the .mat file containing RSK structure.

        Returns
        -------
        xr.Dataset
            Converted Dataset.
        """

        import scipy.io

        # Load MATLAB file
        try:
            mat = scipy.io.loadmat(
                mat_file_path, 
                squeeze_me=True, 
                struct_as_record=False
            )
        except Exception as e:
            raise ValueError(f"Could not read .mat file: {e}")

        # RSK structure extraction
        if "rsk" not in mat:
            raise ValueError("Expected 'rsk' struct not found in .mat file.")
        
        rsk = mat["rsk"]

        # Metadata extraction
        self._extract_metadata_from_rsk(rsk)

        # Timestamp extraction
        timestamps = self._extract_timestamps(rsk)

        # Channel data extraction
        data_vars, coords = self._extract_channels_data(rsk, timestamps)

        # Dataset creation
        ds = xr.Dataset(
            data_vars=data_vars,
            coords=coords,
            attrs=self._create_global_attributes()
        )
        
        return ds
    
    def _extract_metadata_from_rsk(self, rsk):
        """Extract metadata from RSK structure."""

        # Instrument information
        instruments = getattr(rsk, 'instruments', None)
        if instruments is not None:
            self._instrument_info = {
                'model': self._safe_getattr(instruments, 'model', 'Unknown'),
                'serial_id': self._safe_getattr(instruments, 'serialID', 'Unknown'),
                'firmware_version': self._safe_getattr(instruments, 'firmwareVersion', 'Unknown'),
                'firmware_type': self._safe_getattr(instruments, 'firmwareType', 'Unknown'),
            }

        # Channel information
        channels = getattr(rsk, 'channels', [])
        if hasattr(channels, '__len__') and len(channels) > 0:
            for i, channel in enumerate(np.atleast_1d(channels)):
                try:
                    channel_name = self._safe_getattr(channel, 'longName', f'Channel_{i}')
                    self._channels_info[channel_name] = {
                        'index': i,
                        'longName': channel_name,
                        'shortName': self._safe_getattr(channel, 'shortName', channel_name),
                        'units': self._safe_getattr(channel, 'units', ''),
                        'channelID': self._safe_getattr(channel, 'channelID', i+1)
                    }
                except Exception:
                    continue

        # Epoch information
        epochs = getattr(rsk, 'epochs', None)
        if epochs is not None:
            self._epochs_info = {
                'startTime': self._safe_getattr(epochs, 'startTime', None),
                'endTime': self._safe_getattr(epochs, 'endTime', None),
                'deploymentID': self._safe_getattr(epochs, 'deploymentID', None)
            }
    
    def _extract_timestamps(self, rsk):
        """Extract and convert timestamps."""
        data_struct = getattr(rsk, 'data', None)
        if data_struct is None:
            raise ValueError("'data' structure not found in RSK")
        
        tstamp = getattr(data_struct, 'tstamp', None)
        if tstamp is None:
            raise ValueError("'tstamp' array not found in data structure")
        
        tstamp = np.asarray(tstamp)

        # Convert MATLAB datenum to datetime64
        try:
            timestamps = pd.to_datetime(tstamp, unit='D', origin='0000-01-01').values
        except:
            # Fallback: manual conversion
            unix_timestamps = (tstamp - 719529) * 86400
            timestamps = pd.to_datetime(unix_timestamps, unit='s').values
        
        return timestamps
    
    def _extract_channels_data(self, rsk, timestamps):
        """Extract data for all channels."""
        data_struct = getattr(rsk, 'data', None)
        if data_struct is None:
            raise ValueError("'data' structure not found")
        
        values = getattr(data_struct, 'values', None)
        if values is None:
            raise ValueError("'values' array not found")
        
        values = np.asarray(values)

        # Coordinates
        coords = {self._time_dim: timestamps}

        # Data variables for each channel
        data_vars = {}
        
        for channel_name, channel_info in self._channels_info.items():
            channel_index = channel_info['index']
            
            if channel_index < values.shape[1]:
                channel_data = values[:, channel_index]
                
                data_vars[channel_name] = xr.DataArray(
                    channel_data,
                    dims=[self._time_dim],
                    attrs={
                        'long_name': channel_info['longName'],
                        'units': channel_info['units'],
                        'short_name': channel_info['shortName'],
                        'rbr_channel_id': channel_info['channelID'],
                        'rbr_original_units': channel_info['units'],
                        'rbr_original_name': channel_name,
                    }
                )
        
        return data_vars, coords
    
    def _safe_getattr(self, obj, attr, default=None):
        """Safely access MATLAB structure attributes."""
        try:
            value = getattr(obj, attr, default)
            if isinstance(value, np.ndarray) and value.size == 1:
                return value.item()
            elif isinstance(value, np.ndarray) and value.dtype.kind in ['U', 'S']:
                return str(value)
            return value
        except:
            return default
    
    def _create_global_attributes(self) -> dict:
        """Extract global dataset attributes."""
        attrs = {
            'Conventions': 'CF-1.13',
            'source': f"RBR {self._instrument_info.get('model', 'Unknown')}",
        }

        # Instrument information
        for key, value in self._instrument_info.items():
            attrs[f'rbr_instrument_{key}'] = value

        # Epoch information
        if self._epochs_info.get('startTime') is not None:
            try:
                start_dt = pd.to_datetime(
                    self._epochs_info['startTime'], 
                    unit='D', 
                    origin='0000-01-01'
                )
                attrs['rbr_time_coverage_start'] = start_dt.isoformat()
            except:
                pass
        
        if self._epochs_info.get('endTime') is not None:
            try:
                end_dt = pd.to_datetime(
                    self._epochs_info['endTime'], 
                    unit='D', 
                    origin='0000-01-01'
                )
                attrs['rbr_time_coverage_end'] = end_dt.isoformat()
            except:
                pass
        
        return attrs

    def _load_data(self) -> xr.Dataset:
        """Load data from the MATLAB file and return an xarray Dataset."""
        return self._parse_rsk_data(self.input_file)

    @classmethod
    def format_key(cls) -> str:
        return 'rbr-matlab-rsktools'

    @classmethod
    def format_name(cls) -> str:
        return "RBR Matlab RSKtools"

    @classmethod
    def file_extension(cls) -> str | None:
        return None
