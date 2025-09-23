"""
SeaSenseLib - Oceanographic Sensor Data Processing Library

This package provides tools for reading, processing, and writing 
sensor data in various formats.

Main Components:
---------------
- readers: Classes for reading different sensor file formats
- writers: Classes for writing sensor data to different formats
- plotters: Tools for visualizing sensor data
- processors: Classes for processing sensor data
"""

# Import modules lazily to improve startup performance
# The actual imports happen when these modules are first accessed

import sys
from importlib import import_module

# Cache for loaded modules to avoid re-importing
_loaded_modules = {}

def __getattr__(name):
    """Lazy loading of package modules."""
    if name in ['readers', 'writers', 'plotters', 'processors']:
        if name not in _loaded_modules:
            # Use absolute import to avoid recursion
            module_name = f'seasenselib.{name}'
            _loaded_modules[name] = import_module(module_name)
        return _loaded_modules[name]
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'readers',
    'writers',
    'plotters',
    'processors'
]
