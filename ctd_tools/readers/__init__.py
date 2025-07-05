"""
CTD Tools Readers Module

This module provides various reader classes for importing CTD sensor data
from different file formats into xarray Datasets.

Available Readers:
-----------------
- NetCdfReader: Read NetCDF files
- CsvReader: Read CSV files
- RbrAsciiReader: Read RBR ASCII files
- NortekAsciiReader: Read Nortek ASCII files
- RbrRskLegacyReader: Read legacy RSK files
- RbrRskReader: Read RSK files
- RbrRskAutoReader: Auto-detect RSK format
- SbeCnvReader: Read SeaBird CNV files
- SeasunTobReader: Read Sea & Sun TOB files

Example Usage:
--------------
from ctd_tools.readers import SbeCnvReader, NetCdfReader

# Read a CNV file
reader = SbeCnvReader("data.cnv")
data = reader.get_data()

# Read a NetCDF file  
nc_reader = NetCdfReader("data.nc")
nc_data = nc_reader.get_data()
"""

# Import the base class
from .base import AbstractReader

# Import all individual reader classes
from .csv_reader import CsvReader
from .netcdf_reader import NetCdfReader
from .nortek_ascii_reader import NortekAsciiReader
from .rbr_ascii_reader import RbrAsciiReader
from .rbr_rsk_legacy_reader import RbrRskLegacyReader
from .rbr_rsk_reader import RbrRskReader
from .rbr_rsk_auto_reader import RbrRskAutoReader
from .sbe_cnv_reader import SbeCnvReader
from .seasun_tob_reader import SeasunTobReader

__all__ = [
    'AbstractReader',
    'CsvReader',
    'NetCdfReader',
    'NortekAsciiReader', 
    'RbrAsciiReader',
    'RbrRskAutoReader',
    'RbrRskLegacyReader',
    'RbrRskReader',
    'SbeCnvReader',
    'SeasunTobReader'
]
