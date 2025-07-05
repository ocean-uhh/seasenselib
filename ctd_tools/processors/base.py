"""
Module for abstract base class for processing sensor data from xarray Datasets.

This module defines the `AbstractProcessor` class, which serves as a base class for
all processor implementations in the CTD Tools package. Concrete processor classes should
inherit from this class and implement their specific processing methods.
"""

from abc import ABC, abstractmethod
from typing import Any
import xarray as xr

class AbstractProcessor(ABC):
    """Abstract base class for processing sensor data from xarray Datasets.
    
    This class provides a common interface for all processor implementations.
    All concrete processor classes should inherit from this class and implement
    their specific processing methods.
    
    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be processed.
    
    Methods:
    --------
    __init__(data: xr.Dataset):
        Initializes the processor with the provided xarray Dataset.
    """

    def __init__(self, data: xr.Dataset):
        """Initialize the processor with the provided xarray Dataset.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data to be processed.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """
        if not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray.Dataset")

        self.data = data

    @abstractmethod
    def process(self) -> Any:
        """Process the dataset.
        
        This method should be implemented by concrete processor classes
        to define their specific processing logic.
        
        Returns:
        --------
        Any:
            The result of the processing operation.
        """
        pass

    def validate_parameter(self, parameter_name: str) -> None:
        """Validate that a parameter exists in the dataset.
        
        Parameters:
        -----------
        parameter_name : str
            The name of the parameter to validate.
            
        Raises:
        -------
        ValueError:
            If the parameter is not found in the dataset.
        """
        if parameter_name not in self.data:
            raise ValueError(f"Parameter '{parameter_name}' not found in dataset")

    def validate_coordinate(self, coordinate_name: str) -> None:
        """Validate that a coordinate exists in the dataset.
        
        Parameters:
        -----------
        coordinate_name : str
            The name of the coordinate to validate.
            
        Raises:
        -------
        ValueError:
            If the coordinate is not found in the dataset.
        """
        if coordinate_name not in self.data.coords:
            raise ValueError(f"Coordinate '{coordinate_name}' not found in dataset")
