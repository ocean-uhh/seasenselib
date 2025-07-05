"""
Module for calculating statistics and performing calculations on sensor data.

This module provides the StatisticsProcessor class for computing various statistical
metrics on CTD sensor data stored in xarray Datasets.
"""

from typing import Union, Optional, Any
import xarray as xr
import ctd_tools.parameters as params
from .base import AbstractProcessor

class StatisticsProcessor(AbstractProcessor):
    """Calculate statistical metrics on sensor data.
    
    This class provides methods to calculate various statistical measures
    like mean, median, standard deviation, etc. on specific parameters
    within a sensor dataset.

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    parameter : str
        The name of the parameter to calculate statistics for.
    
    Example Usage:
    --------------
    stats_processor = StatisticsProcessor(dataset, "temperature")
    mean_temp = stats_processor.mean()
    max_temp = stats_processor.max()
    stats = stats_processor.get_all_statistics()
    """

    def __init__(self, data: xr.Dataset, parameter: str):
        """Initialize the statistics processor with dataset and parameter.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data.
        parameter : str
            The name of the parameter to calculate statistics for.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        ValueError:
            If the parameter is not found in the dataset.
        """
        super().__init__(data)

        if not isinstance(parameter, str):
            raise TypeError("Parameter name must be a string")

        self.validate_parameter(parameter)
        self.parameter = parameter

    def process(self) -> dict:
        """Process the dataset to calculate all statistics.
        
        Returns:
        --------
        dict:
            A dictionary containing all calculated statistics.
        """
        return self.get_all_statistics()

    def max(self, dim: Optional[str] = None) -> Any:
        """Calculate the maximum value.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the maximum.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        Any:
            The maximum value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].max(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def min(self, dim: Optional[str] = None) -> Any:
        """Calculate the minimum value.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the minimum.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The minimum value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].min(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def mean(self, dim: Optional[str] = None) -> Any:
        """Calculate the arithmetic mean.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the mean.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The mean value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].mean(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def median(self, dim: Optional[str] = None) -> Any:
        """Calculate the median value.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the median.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The median value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].median(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def std(self, dim: Optional[str] = None) -> Any:
        """Calculate the standard deviation.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the standard deviation.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The standard deviation value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].std(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def var(self, dim: Optional[str] = None) -> Any:
        """Calculate the variance.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate the variance.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The variance value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].var(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def quantile(self, q: Union[float, list], dim: Optional[str] = None) -> Any:
        """Calculate quantiles.
        
        Parameters:
        -----------
        q : float or list
            Quantile(s) to compute (0 <= q <= 1).
        dim : str, optional
            The dimension along which to calculate the quantiles.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        float or xr.DataArray:
            The quantile value(s).
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].quantile(q, dim=dim)
        return result.values if hasattr(result, 'values') else result

    def count_valid(self, dim: Optional[str] = None) -> Any:
        """Count valid (non-NaN) values.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to count valid values.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        int or xr.DataArray:
            The count of valid values.
        """
        if dim is None:
            dim = params.TIME

        result = self.data[self.parameter].count(dim=dim)
        return result.values if hasattr(result, 'values') else result

    def get_all_statistics(self, dim: Optional[str] = None) -> dict:
        """Calculate all available statistics.
        
        Parameters:
        -----------
        dim : str, optional
            The dimension along which to calculate statistics.
            If None, uses the TIME parameter.
        
        Returns:
        --------
        dict:
            A dictionary containing all calculated statistics.
        """
        return {
            'min': self.min(dim),
            'max': self.max(dim),
            'mean': self.mean(dim),
            'median': self.median(dim),
            'std': self.std(dim),
            'var': self.var(dim),
            'count_valid': self.count_valid(dim),
            'q25': self.quantile(0.25, dim),
            'q75': self.quantile(0.75, dim)
        }
