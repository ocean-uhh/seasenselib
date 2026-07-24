"""
Module for reading RBR data from legacy MATLAB .mat files.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime
from seasenselib.readers.base import AbstractReader
import seasenselib.parameters as params


def _parse_start_end(s: str) -> np.datetime64:
    """Parse start/end date from string, supporting multiple formats."""
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M:%S.%f %p",
    ):
        try:
            return np.datetime64(datetime.strptime(str(s), fmt))
        except (ValueError, TypeError):
            continue
    raise ValueError(f"Could not parse date string: {s}")


def _parse_time_any(s: str) -> pd.Timestamp:
    """Parse RBR sample time strings without swapping ISO day/month fields."""
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %I:%M:%S.%f %p",
        "%d/%m/%Y %I:%M:%S %p",
    ):
        try:
            return pd.to_datetime(str(s), format=fmt)
        except (ValueError, TypeError):
            continue

    result = pd.to_datetime(str(s), dayfirst=False, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"Could not parse time string: {s}")
    return result


class RbrMatlabLegacyReader(AbstractReader):
    """Reader which converts RBR data stored in MATLAB .mat files into an xarray Dataset."""

    def __init__(self, input_file: str,
                 time_dim: str = params.TIME,
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize RbrMatlabLegacyReader.
        
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
        # side-info captured during parse
        self._serial_number = None
        self._start_date = None
        self._end_date = None
        self._comment = ""
        self._latitude = None
        self._longitude = None
        self._coefficients = []
        # Channel information for multi-parameter support
        self._channel_names = []
        self._channel_units = []
        super().__init__(input_file, mapping, **kwargs)
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for MATLAB files."""
        return ('.mat',)

    @classmethod
    def reader_args(cls) -> list[dict]:
        return []

    # ---------- internals ----------
    def _parse_data(self, mat_file_path) -> pd.DataFrame:
        """
        Parse MATLAB file into a pandas.DataFrame with a datetime index and
        multiple parameter columns based on available channels. Also returns 
        side info via instance attributes.
        """

        import scipy.io

        # Load the .mat with MATLAB-like structs squeezed into simple objects
        mat = scipy.io.loadmat(mat_file_path, squeeze_me=True, struct_as_record=False)

        # Raise error if mat file is empty
        if mat is None:
            raise ValueError("Could not read .mat file.")            

        # Raise error ift RBR entry not in mat file
        if "RBR" not in mat:
            raise ValueError("Expected 'RBR' struct not found in .mat file.")

        # Get top-level struct named 'RBR'
        RBR = mat["RBR"]

        # Extract channel names and units if available
        channel_names = self._extract_channel_names(RBR)
        channel_units = self._extract_channel_units(RBR)

        # --- Serial number from the end of the 'name' field ---
        try:
            name_str = str(getattr(RBR, "name", "")).strip()
            self._serial_number = name_str.split()[-1] if name_str else None
        except Exception:
            self._serial_number = None

        self._start_date = _parse_start_end(RBR.starttime)
        self._end_date   = _parse_start_end(RBR.endtime)

        # Events → comment (string)
        events_arr = np.atleast_1d(getattr(RBR, "events", []))
        self._comment = "; ".join(map(str, events_arr)) if events_arr.size else ""

        # Lat/Lon from nested parameters struct (optional)
        params = getattr(RBR, "parameters", None)
        self._latitude = getattr(params, "latitude", None) if params is not None else None
        self._longitude = getattr(params, "longitude", None) if params is not None else None

        # Coefficients (store on the temperature variable later)
        coeff = np.atleast_1d(getattr(RBR, "coefficients", []))
        self._coefficients = coeff.astype(float).tolist() if coeff.size else []

        # ---- sample times (cell array of strings) → datetime64 ----
        # Examples like: '12/08/2018 12:00:00.000 PM' or without milliseconds
        raw_times = np.atleast_1d(RBR.sampletimes)

        times = pd.to_datetime([_parse_time_any(str(s)) for s in raw_times])
        if times.isna().any():
            n_bad = int(times.isna().sum())
            raise ValueError(f"Failed to parse {n_bad} sample time strings from 'sampletimes'.")

        # ---- data (NxM array for M channels) → DataFrame ----
        data = np.asarray(getattr(RBR, "data", []), dtype=float)
        
        # Handle different data shapes
        if data.ndim == 1:
            # Single parameter (original case)
            data = data.reshape(-1, 1)
            if not channel_names:
                channel_names = ["temperature"]  # Default fallback
        elif data.ndim == 2:
            # Multiple parameters
            if not channel_names or len(channel_names) < data.shape[1]:
                # Generate default names if not enough channel names available
                default_names = [f"parameter_{i+1}" for i in range(data.shape[1])]
                if channel_names:
                    # Use available names, fill rest with defaults
                    channel_names.extend(default_names[len(channel_names):])
                else:
                    channel_names = default_names
        else:
            raise ValueError(f"Unexpected data shape {data.shape}; expected 1D or 2D array.")

        # Ensure we have the right number of channel names
        if data.shape[1] != len(channel_names):
            channel_names = channel_names[:data.shape[1]]  # Truncate if too many
            while len(channel_names) < data.shape[1]:
                channel_names.append(f"parameter_{len(channel_names)+1}")

        if data.shape[0] != times.size:
            raise ValueError(f"Data length ({data.shape[0]}) != time length ({times.size}).")

        # Build DataFrame with multiple columns
        df_data = {}
        for i, channel_name in enumerate(channel_names):
            # Clean channel name for DataFrame column
            clean_name = self._clean_channel_name(channel_name)
            df_data[clean_name] = data[:, i]
        
        df = pd.DataFrame(df_data, index=times)
        df.index.name = self._time_dim
        
        # Store channel information for later use
        self._channel_names = channel_names
        self._channel_units = channel_units
        
        return df

    def _extract_channel_names(self, RBR) -> list:
        """Extract channel names from RBR structure."""
        try:
            channel_names = getattr(RBR, "channelnames", [])
            if hasattr(channel_names, '__iter__') and not isinstance(channel_names, str):
                # Handle array of strings
                return [str(name) for name in np.atleast_1d(channel_names)]
            elif isinstance(channel_names, str):
                return [channel_names]
            else:
                return []
        except:
            return []

    def _extract_channel_units(self, RBR) -> list:
        """Extract channel units from RBR structure."""
        try:
            channel_units = getattr(RBR, "channelunits", [])
            if hasattr(channel_units, '__iter__') and not isinstance(channel_units, str):
                # Handle array of strings
                return [str(unit) for unit in np.atleast_1d(channel_units)]
            elif isinstance(channel_units, str):
                return [channel_units]
            else:
                return []
        except:
            return []

    def _clean_channel_name(self, channel_name: str) -> str:
        """Clean channel name for use as DataFrame column name."""
        # Remove spaces, special characters, make lowercase
        import re
        clean_name = re.sub(r'[^\w]', '_', str(channel_name).strip())
        clean_name = re.sub(r'_+', '_', clean_name)  # Multiple underscores to single
        clean_name = clean_name.strip('_')  # Remove leading/trailing underscores
        return clean_name.lower() if clean_name else "unknown_parameter"

    def _create_xarray_dataset(self, df: pd.DataFrame) -> xr.Dataset:
        """Create an xarray Dataset and attach metadata for all parameters."""
        # Create data variables for each column in the DataFrame
        data_vars = {}
        coords = {self._time_dim: df.index.values.astype("datetime64[ns]")}
        
        for i, col in enumerate(df.columns):
            # Get original channel name and units
            original_name = self._channel_names[i] if i < len(self._channel_names) else col
            units = (self._channel_units[i] if i < len(self._channel_units) else '')
            
            # Create DataArray for this parameter
            data_vars[col] = xr.DataArray(
                df[col].to_numpy(),
                dims=[self._time_dim],
                attrs={
                    "units": units,
                    "long_name": original_name,
                    "original_name": original_name
                }
            )
            
            # Add coefficients to first parameter (legacy behavior)
            if i == 0 and self._coefficients:
                data_vars[col].attrs["coefficients"] = self._coefficients

        # Create Dataset
        ds = xr.Dataset(
            data_vars=data_vars,
            coords=coords,
            attrs={
                "Conventions": "CF-1.13",
                "title": "RBR oceanographic data",
                "source": "RBR instrument (legacy MATLAB export)",
                "rbr_serial_number": self._serial_number,
                "rbr_start_date": self._start_date,
                "rbr_end_date": self._end_date,
            },
        )

        # Optional global attrs
        if self._comment:
            ds.attrs["comment"] = self._comment
        if self._latitude is not None:
            ds.attrs["latitude"] = float(self._latitude)
        if self._longitude is not None:
            ds.attrs["longitude"] = float(self._longitude)

        # Let base class attach any mapped metadata
        for key in list(ds.data_vars.keys()) + list(ds.coords.keys()):
            super()._assign_metadata_for_key_to_xarray_dataset(ds, key)
        
        # Perform default post-processing
        return ds

    def _load_data(self) -> xr.Dataset:
        """Load data from the MATLAB file and return an xarray Dataset."""
        df = self._parse_data(self.input_file)
        return self._create_xarray_dataset(df)

    @classmethod
    def format_key(cls) -> str:
        return "rbr-matlab-legacy"

    @classmethod
    def format_name(cls) -> str:
        return "RBR Matlab Legacy"

    @classmethod
    def file_extension(cls) -> str | None:
        return None
    
