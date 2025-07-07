"""
Module for abstract base class for plotting sensor data from xarray Datasets.

This module defines the `AbstractPlotter` class, which serves as a base class for
all plotter implementations in the CTD Tools package. Concrete plotter classes should
inherit from this class and implement the `plot` method to handle the specifics of
creating different types of visualizations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import xarray as xr
import matplotlib.pyplot as plt
import ctd_tools.parameters as params


class AbstractPlotter(ABC):
    """Abstract base class for plotting sensor data from xarray Datasets.
    
    This class provides a common interface for all plotter implementations.
    All concrete plotter classes should inherit from this class and implement
    the plot method.
    
    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    __init__(data: xr.Dataset):
        Initializes the plotter with the provided xarray Dataset.
    data: xr.Dataset
        The xarray Dataset containing the sensor data.
    data.setter(value: xr.Dataset):
        Sets the xarray Dataset with validation.
    plot(**kwargs):
        Creates the plot (to be implemented by subclasses).
    _get_dataset_without_nan() -> xr.Dataset:
        Returns dataset with NaN values removed from time dimension.
    _validate_required_variables(required_vars: list):
        Validates that required variables exist in the dataset.

    Raises:
    -------
    NotImplementedError:
        If the subclass does not implement the `plot` method.
    TypeError:
        If the provided data is not an xarray Dataset.
    ValueError:
        If required variables are missing from the dataset.
    """

    def __init__(self, data: xr.Dataset | None = None):
        """Initialize the plotter with the provided xarray Dataset.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data to be plotted.
        """

        # Validate that data is an xarray Dataset or None
        if data is not None and not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Set the data attribute
        self._data = data

    @property
    def data(self) -> xr.Dataset | None:
        """Get the xarray Dataset containing the sensor data.

        Returns:
        --------
        xr.Dataset | None
            The xarray Dataset containing the sensor data.
        """
        return self._data

    @data.setter
    def data(self, value: xr.Dataset):
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
    def plot(self, *args, **kwargs):
        """Create the plot.
        
        This method must be implemented by all subclasses to define
        how the specific type of plot should be created.
        
        Parameters:
        -----------
        *args : tuple
            Positional arguments specific to the plot type.
        **kwargs : dict
            Keyword arguments specific to the plot type.
            
        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this method.
        """
        pass

    def _get_dataset_without_nan(self) -> xr.Dataset:
        """Returns dataset with NaN values removed from time dimension.
        
        Returns:
        --------
        xr.Dataset
            The dataset with NaN values dropped along the time dimension.
        """
        return self.data.dropna(dim=params.TIME)

    def _validate_required_variables(self, required_vars: list):
        """Validates that required variables exist in the dataset.
        
        Parameters:
        -----------
        required_vars : list
            List of variable names that must exist in the dataset.
            
        Raises:
        -------
        ValueError:
            If any required variable is missing from the dataset.
        """

        missing_vars = []
        for var in required_vars:
            if var not in self.data:
                missing_vars.append(var)

        if missing_vars:
            missing_str = ', '.join(missing_vars)
            raise ValueError(f"Required variable(s) missing from dataset: {missing_str}")

    def _save_or_show_plot(self, output_file: str | None = None):
        """Helper method to either save plot to file or display it.
        
        Parameters:
        -----------
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        """
        if output_file:
            plt.savefig(output_file)
        else:
            plt.show()
