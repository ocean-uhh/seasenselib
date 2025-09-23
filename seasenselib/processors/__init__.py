"""
SeaSenseLib Processing Module

This module provides various processing classes for analyzing and manipulating
sensor data stored in xarray Datasets.

Available Processors:
--------------------
- StatisticsProcessor: Calculate statistical metrics on sensor data
- SubsetProcessor: Subset sensor data by time, sample indices, or parameter values
- ResampleProcessor: Resample sensor data to different time intervals

Example Usage:
--------------
from seasenselib.processing import StatisticsProcessor, SubsetProcessor, ResampleProcessor

# Calculate statistics
stats_processor = StatisticsProcessor(dataset, "temperature")
mean_temp = stats_processor.mean()
max_temp = stats_processor.max()

# Subset data
subset_processor = SubsetProcessor(dataset)
subset = subset_processor.set_time_min("2023-01-01").set_time_max("2023-01-31").get_subset()

# Resample data
resample_processor = ResampleProcessor(dataset)
daily_data = resample_processor.resample("1D")
"""

# Import the base class
from .base import AbstractProcessor

# Import all individual processor classes
from .statistics_processor import StatisticsProcessor
from .subset_processor import SubsetProcessor
from .resample_processor import ResampleProcessor

__all__ = [
    'AbstractProcessor',
    'StatisticsProcessor',
    'SubsetProcessor',
    'ResampleProcessor'
]
