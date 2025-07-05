"""
CTD Tools Plotters Module

This module provides various plotter classes for visualizing CTD sensor data
from xarray Datasets using matplotlib.

Available Plotters:
------------------
- TsDiagramPlotter: Create T-S (Temperature-Salinity) diagrams with density isolines
- ProfilePlotter: Create vertical CTD profiles for temperature and salinity
- TimeSeriesPlotter: Create time series plots for any parameter

Example Usage:
--------------
from ctd_tools.plotters import TsDiagramPlotter, ProfilePlotter, TimeSeriesPlotter

# Create a T-S diagram
ts_plotter = TsDiagramPlotter(data)
ts_plotter.plot(title="Station 001 T-S Diagram", output_file="ts_diagram.png")

# Create a vertical profile  
profile_plotter = ProfilePlotter(data)
profile_plotter.plot(title="CTD Profile", output_file="profile.png")

# Create a time series plot
time_plotter = TimeSeriesPlotter(data)
time_plotter.plot("temperature", title="Temperature Time Series", output_file="temp_series.png")

"""

# Import the base class
from .base import AbstractPlotter

# Import all individual plotter classes
from .ts_diagram_plotter import TsDiagramPlotter
from .profile_plotter import ProfilePlotter
from .time_series_plotter import TimeSeriesPlotter
from .time_series_plotter_multi import TimeSeriesPlotterMulti

__all__ = [
    'AbstractPlotter',
    'TsDiagramPlotter',
    'ProfilePlotter',
    'TimeSeriesPlotter',
    'TimeSeriesPlotterMulti'
]
