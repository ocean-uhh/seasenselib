"""
Module for reading CTD data from SBE ASCII files.
"""

from __future__ import annotations
import re
import logging
from datetime import datetime
import pandas as pd
import xarray as xr

from seasenselib.readers.base import AbstractReader
from seasenselib.readers.utils.conductivity_units import infer_conductivity_unit
import seasenselib.parameters as params

logger = logging.getLogger(__name__)

def _extract_date(date_string: str) -> datetime:
    """Parse a combined date/time string, supporting multiple SeaBird ASCII formats."""
    date_formats = [
        "%d %b %Y %H:%M:%S",  # "30 Mar 2026 03:00:01"
        "%m-%d-%Y %H:%M:%S",  # "03-30-2026 03:00:01"
        "%d-%m-%Y %H:%M:%S",  # "30-03-2026 03:00:01"
        "%Y-%m-%d %H:%M:%S",  # "2026-03-30 03:00:01"
    ]

    date_string = date_string.strip()
    for fmt in date_formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            pass
    raise ValueError(f"Could not parse datetime string: {date_string!r}")


class SbeAsciiReader(AbstractReader):
    """Reads CTD data from a SeaBird ASCII file into an xarray Dataset."""

    def __init__(self, input_file: str,
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize SbeAsciiReader.
        
        Parameters
        ----------
        input_file : str
            Path to the ASCII file.
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
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for SeaBird ASCII files."""
        return ('.asc', '.txt', '.dat', '.csv')

    @classmethod
    def _is_extension_validation_strict(cls) -> bool:
        """ASCII formats can have various extensions, so warn only."""
        return False

    def _extract_sample_interval(self, file_path):
        import codecs

        with codecs.open(file_path, 'r', 'ascii') as fo:
            content = fo.read()
        lines = content.splitlines()

        sample_interval = None
        for line in lines:
            if "sample interval" in line.lower():
                parts = line.split('=')
                if len(parts) == 2:
                    sample_interval = parts[1].strip().split()[0]
                    break
        return sample_interval

    def _extract_instrument_type(self, file_path):
        import codecs

        with codecs.open(file_path, 'r', 'ascii') as fo:
            first_line = fo.readline()
        match = re.search(r'\*+\s*(Sea-Bird\s+[A-Z0-9\-]+)', first_line)
        if match:
            return match.group(1)
        return "Unknown Instrument"

    def _parse_data(self, file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()

        metadata = {}
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith('*END*'):
                data_start = i + 1
                break
            if '=' in line:
                key, value = line.split('=', 1)
                metadata[re.sub(r'^\* ', '', key.strip())] = value.strip()

        #  Inject default reference pressure if missing
        if "reference pressure" not in (k.lower() for k in metadata):
            logger.debug("Injecting default reference pressure: 0.0 db")
            metadata["reference pressure"] = "0.0 db"

        # Prepare data list
        data = []
        pressure_data = []  # Store pressure if available

        for line in lines[data_start:]:
            parts = [p.strip() for p in line.split(",")]

            if len(parts) == 4:  # Case without pressure
                temp, cond, date, time = parts
                timestamp = _extract_date(f"{date} {time}")
                data.append([float(temp), float(cond), timestamp])
            elif len(parts) == 5:  # Case with pressure
                temp, cond, pres, date, time = parts
                timestamp = _extract_date(f"{date} {time}")
                pressure_data.append(float(pres))  # Store pressure data
                data.append([float(temp), float(cond), timestamp])

        # If pressure data is available, append it to the DataFrame
        df = pd.DataFrame(data, columns=['temperature', 'conductivity', 'time'])
        if pressure_data:
            df['pressure'] = pressure_data  # Add pressure column

        df.set_index('time', inplace=True)

        return df, metadata

    def _create_xarray_dataset(self, df, metadata, sample_interval, instrument_type):
        """Create xarray dataset from pandas dataframe.
        
        Returns raw dataset with format-specific variable names.
        Variable mapping and metadata enrichment handled by stages.
        """
        ds = xr.Dataset.from_dataframe(df)

        # SBE37 ASCII output is S/m for conductivity. Verify magnitude matches
        # declared unit; the pipeline unit_handling stage normalises to mS cm-1.
        cond_values = ds['conductivity'].values
        declared_unit = "S/m"
        try:
            infer_conductivity_unit(cond_values, declared=declared_unit)
        except ValueError as exc:
            logger.warning(
                "Could not verify conductivity units against magnitude: %s",
                exc,
            )
        ds['conductivity'].attrs = {
            'units': declared_unit,
            'conductivity_unit_source': "SBE37 ASC format outputs S/m",
        }

        # Add minimal units from raw data (stages will enrich with CF metadata)
        ds['temperature'].attrs = {'units': 'degree_C'}
        if 'pressure' in ds.data_vars:
            ds['pressure'].attrs = {'units': 'dbar'}

        # Add source information and metadata
        ds.attrs.update(metadata)
        ds.attrs['source'] = instrument_type

        if sample_interval:
            ds.attrs['information'] = f"sample interval {sample_interval} seconds"
        
        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        return ds

    def _load_data(self) -> xr.Dataset:
        """Load the SeaBird ASCII data and return an xarray Dataset.
        
        Returns
        -------
        xr.Dataset
            The loaded dataset.
        """
        df, metadata = self._parse_data(self.input_file)
        sample_interval = self._extract_sample_interval(self.input_file)
        instrument_type = self._extract_instrument_type(self.input_file)
        ds = self._create_xarray_dataset(df, metadata, sample_interval, instrument_type)
        return ds

    @classmethod
    def format_mappings(cls) -> dict[str, list]:
        """Return SeaBird ASCII format-specific variable name mappings.
        
        Returns
        -------
        dict[str, list]
            Dictionary mapping standard names to SBE ASCII format-specific aliases.
        """
        return {
            params.TEMPERATURE: ['temperature'],
            params.CONDUCTIVITY: ['conductivity'],
            params.PRESSURE: ['pressure'],
        }

    @classmethod
    def format_key(cls) -> str:
        return 'sbe-ascii'

    @classmethod
    def format_name(cls) -> str:
        return 'SeaBird ASCII'

    @classmethod
    def file_extension(cls) -> str | None:
        return None
