"""
CTD Tools Writers Module

This module provides various writer classes for exporting CTD sensor data
from xarray Datasets to different file formats.

Available Writers:
-----------------
- NetCdfWriter: Export to NetCDF format
- CsvWriter: Export to CSV format  
- ExcelWriter: Export to Excel format

Example Usage:
--------------
from ctd_tools.writers import NetCdfWriter, CsvWriter, ExcelWriter

# Write to NetCDF
writer = NetCdfWriter(data)
writer.write("output.nc")

# Write to CSV
csv_writer = CsvWriter(data)
csv_writer.write("output.csv")

# Write to Excel
excel_writer = ExcelWriter(data) 
excel_writer.write("output.xlsx")
"""

from .base import AbstractWriter
from .netcdf_writer import NetCdfWriter
from .csv_writer import CsvWriter
from .excel_writer import ExcelWriter

__all__ = [
    'AbstractWriter',
    'CsvWriter',
    'ExcelWriter',
    'NetCdfWriter'
]
