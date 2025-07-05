"""
Module for resampling sensor data to different time intervals.

This module provides the ResampleProcessor class for resampling sensor data
stored in xarray Datasets to different time intervals.
"""

from typing import Optional, Any
import xarray as xr
import ctd_tools.parameters as params
from .base import AbstractProcessor

class ResampleProcessor(AbstractProcessor):
    """Resample sensor data to different time intervals.

    This class provides methods to resample sensor data along the time dimension
    to different frequencies (e.g., hourly, daily, monthly).
    
    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    
    Example Usage:
    --------------
    resample_processor = ResampleProcessor(dataset)
    daily_data = resample_processor.resample("1D").mean()
    hourly_data = resample_processor.resample("1H").median()
    """

    def __init__(self, data: xr.Dataset):
        """Initialize the resample processor with dataset.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        ValueError:
            If the dataset does not contain a time coordinate.
        """
        super().__init__(data)

        # Validate that the dataset has a time coordinate
        self.validate_coordinate(params.TIME)

    def process(self) -> xr.Dataset:
        """Process the dataset (returns the original dataset).
        
        This method is required by the AbstractProcessor interface.
        For resampling, use the resample() method instead.
        
        Returns:
        --------
        xr.Dataset:
            The original dataset.
        """
        return self.data

    def resample(self, time_interval: str, dim: Optional[str] = None) -> Any:
        """Resample the dataset to a specified time interval.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling (e.g., "1H", "1D", "1M").
            Uses pandas frequency strings.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.core.resample.DatasetResample:
            A resample object that can be used to apply aggregation functions.
            
        Example:
        --------
        # Resample to daily averages
        daily_mean = resample_processor.resample("1D").mean()
        
        # Resample to hourly maximum values
        hourly_max = resample_processor.resample("1H").max()
        """
        if dim is None:
            dim = params.TIME

        # Validate that the dimension exists
        self.validate_coordinate(dim)

        return self.data.resample({dim: time_interval})

    def resample_mean(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute mean values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with mean values.
        """
        return self.resample(time_interval, dim).mean()

    def resample_median(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute median values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with median values.
        """
        return self.resample(time_interval, dim).median()

    def resample_max(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute maximum values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with maximum values.
        """
        return self.resample(time_interval, dim).max()

    def resample_min(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute minimum values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with minimum values.
        """
        return self.resample(time_interval, dim).min()

    def resample_std(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute standard deviation.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with standard deviation values.
        """
        return self.resample(time_interval, dim).std()

    def resample_sum(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and compute sum values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with sum values.
        """
        return self.resample(time_interval, dim).sum()

    def resample_count(self, time_interval: str, dim: Optional[str] = None) -> xr.Dataset:
        """Resample and count valid values.
        
        Parameters:
        -----------
        time_interval : str
            The time interval for resampling.
        dim : str, optional
            The dimension to resample along. If None, uses the TIME parameter.
        
        Returns:
        --------
        xr.Dataset:
            The resampled dataset with count values.
        """
        return self.resample(time_interval, dim).count()
