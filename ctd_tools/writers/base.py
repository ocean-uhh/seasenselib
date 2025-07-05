"""
Module for abstract base class for writing sensor data from xarray Datasets.

This module defines the `AbstractWriter` class, which serves as a base class for
all writer implementations in the CTD Tools package. Concrete writer classes should
inherit from this class and implement the `write` method to handle the specifics of
writing data to various formats (e.g., NetCDF, CSV, Excel).
"""

from abc import ABC, abstractmethod
import xarray as xr

class AbstractWriter(ABC):
    """Abstract base class for writing sensor data from xarray Datasets.
    
    This class provides a common interface for all writer implementations.
    All concrete writer classes should inherit from this class and implement
    the write method.
    
    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be written.
    
    Methods:
    --------
    __init__(data: xr.Dataset):
        Initializes the writer with the provided xarray Dataset.
    file_extension: str
        The default file extension for this writer (to be implemented by subclasses).
    data: xr.Dataset
        The xarray Dataset containing the sensor data.
    data.setter(value: xr.Dataset):
        Sets the xarray Dataset with validation.
    write(file_name: str, **kwargs):
        Writes the xarray Dataset to a file (to be implemented by subclasses).

    Raises:
    -------
    NotImplementedError:
        If the subclass does not implement the `write` method or the `file_extension` property.
    TypeError:
        If the provided data is not an xarray Dataset.
    """

    def __init__(self, data: xr.Dataset):
        """Initialize the writer with the provided xarray Dataset.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data to be written.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """

        if not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        self.data = data  # This will use the setter

    @staticmethod
    @abstractmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.
        
        This property must be implemented by all subclasses.
        
        Returns:
        --------
        str
            The file extension (e.g., '.nc', '.csv', '.xlsx').

        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Writer classes must define a file extension")

    @property
    def data(self) -> xr.Dataset:
        """Get the xarray Dataset.
        
        Returns:
        --------
        xr.Dataset
            The xarray Dataset containing the sensor data.
        """
        return self._data

    @data.setter
    def data(self, value: xr.Dataset) -> None:
        """Set the xarray Dataset with validation.
        
        Parameters:
        -----------
        value : xr.Dataset
            The xarray Dataset containing the sensor data.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """
        if not isinstance(value, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")
        self._data = value

    @abstractmethod
    def write(self, file_name: str, **kwargs):
        """Write the xarray Dataset to a file.
        
        Parameters:
        -----------
        file_name : str
            The name of the output file where the data will be saved.
        **kwargs
            Additional keyword arguments specific to the writer implementation.
        """
        raise NotImplementedError("Subclasses must implement the write method")
