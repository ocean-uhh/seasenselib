"""
CTD Tools - Oceanographic Sensor Data Processing Library

This package provides tools for reading, processing, and writing 
sensor data in various formats.

Main Components:
---------------
- readers: Classes for reading different sensor file formats
- writers: Classes for writing sensor data to different formats
- plotters: Tools for visualizing sensor data
- processors: Classes for processing sensor data
"""

try:
    from . import readers
    from . import writers
    from . import plotters
    from . import processors
except ImportError:
    pass

__all__ = [
    'readers',
    'writers',
    'plotters',
    'processors'
]
