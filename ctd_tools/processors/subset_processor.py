"""
Module for subsetting sensor data based on various criteria.

This module provides the SubsetProcessor class for filtering sensor data
stored in xarray Datasets based on sample number, time, and parameter values.
"""

from typing import Optional, Union
import xarray as xr
import pandas as pd
import ctd_tools.parameters as params
from .base import AbstractProcessor

class SubsetProcessor(AbstractProcessor):
    """Subset sensor data based on sample number, time, and parameter values.

    This class allows for flexible slicing of sensor data stored in an xarray Dataset.
    It can filter data based on sample indices, time ranges, and specific parameter values.

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be subsetted.
    min_sample : int, optional
        The minimum sample index to include in the subset.
    max_sample : int, optional
        The maximum sample index to include in the subset.
    min_datetime : pd.Timestamp, optional
        The minimum time to include in the subset.
    max_datetime : pd.Timestamp, optional
        The maximum time to include in the subset.
    parameter_name : str, optional
        The name of the parameter to filter by.
    parameter_value_min : float, optional
        The minimum value of the parameter to include in the subset.
    parameter_value_max : float, optional
        The maximum value of the parameter to include in the subset.

    Example Usage:
    --------------
    subset_processor = SubsetProcessor(dataset)
    subset_processor.set_sample_min(10).set_sample_max(50)
    subset_processor.set_time_min("2023-01-01").set_time_max("2023-01-31")
    subset = subset_processor.get_subset()
    """

    def __init__(self, data: xr.Dataset):
        """Initialize the Subsetter with the provided xarray Dataset.

        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data to be subsetted.

        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """
        super().__init__(data)

        # Initialize slicing parameters
        self.min_sample: Optional[int] = None
        self.max_sample: Optional[int] = None
        self.min_datetime: Optional[pd.Timestamp] = None
        self.max_datetime: Optional[pd.Timestamp] = None
        self.parameter_name: Optional[str] = None
        self.parameter_value_max: Optional[float] = None
        self.parameter_value_min: Optional[float] = None

    def process(self) -> xr.Dataset:
        """Process the dataset to create a subset.
        
        This method applies all the filtering criteria to create the final subset.
        
        Returns:
        --------
        xr.Dataset:
            The subset of the dataset based on the specified criteria.
        """
        return self.get_subset()

    def set_sample_min(self, value: int) -> "SubsetProcessor":
        """Set the minimum sample index for slicing the dataset.

        Parameters:
        -----------
        value : int
            The minimum sample index to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not an integer.
        """
        if not isinstance(value, int):
            raise TypeError("Sample index must be an integer")

        self.min_sample = value
        return self

    def set_sample_max(self, value: int) -> "SubsetProcessor":
        """Set the maximum sample index for slicing the dataset.

        Parameters:
        -----------
        value : int
            The maximum sample index to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not an integer.
        """
        if not isinstance(value, int):
            raise TypeError("Sample index must be an integer")

        self.max_sample = value
        return self

    def _handle_time_value(self, value: Union[str, pd.Timestamp]) -> pd.Timestamp:
        """Convert a time value to a pandas Timestamp.

        Parameters:
        -----------
        value : str or pd.Timestamp
            The time value to convert.

        Returns:
        --------
        pd.Timestamp:
            The converted time value as a pandas Timestamp.

        Raises:
        -------
        TypeError:
            If the provided value is not a string or a pandas Timestamp.
        """
        if not isinstance(value, (str, pd.Timestamp)):
            raise TypeError("Time value must be a string or a pandas Timestamp")

        if isinstance(value, str):
            return pd.Timestamp(value)
        return value

    def set_time_min(self, value: Union[str, pd.Timestamp]) -> "SubsetProcessor":
        """Set the minimum time for slicing the dataset.

        Parameters:
        -----------
        value : str or pd.Timestamp
            The minimum time to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not a string or a pandas Timestamp.
        """
        self.min_datetime = self._handle_time_value(value)
        return self

    def set_time_max(self, value: Union[str, pd.Timestamp]) -> "SubsetProcessor":
        """Set the maximum time for slicing the dataset.

        Parameters:
        -----------
        value : str or pd.Timestamp
            The maximum time to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not a string or a pandas Timestamp.
        """
        self.max_datetime = self._handle_time_value(value)
        return self

    def set_parameter_name(self, value: str) -> "SubsetProcessor":
        """Set the name of the parameter to filter by.

        Parameters:
        -----------
        value : str
            The name of the parameter to filter by.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not a string.
        ValueError:
            If the provided parameter name is not found in the dataset.
        """
        if not isinstance(value, str):
            raise TypeError("Parameter name must be a string")

        self.validate_parameter(value)
        self.parameter_name = value
        return self

    def set_parameter_value_max(self, value: Union[int, float]) -> "SubsetProcessor":
        """Set the maximum value of the parameter to include in the subset.

        Parameters:
        -----------
        value : int or float
            The maximum value of the parameter to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not a number.
        """
        if not isinstance(value, (int, float)):
            raise TypeError("Parameter value must be a number (int or float)")

        self.parameter_value_max = float(value)
        return self

    def set_parameter_value_min(self, value: Union[int, float]) -> "SubsetProcessor":
        """Set the minimum value of the parameter to include in the subset.

        Parameters:
        -----------
        value : int or float
            The minimum value of the parameter to include in the subset.

        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.

        Raises:
        -------
        TypeError:
            If the provided value is not a number.
        """
        if not isinstance(value, (int, float)):
            raise TypeError("Parameter value must be a number (int or float)")

        self.parameter_value_min = float(value)
        return self

    def _slice_by_sample_number(self, subset: xr.Dataset) -> xr.Dataset:
        """Slice the dataset by sample number (index).

        Parameters:
        -----------
        subset : xr.Dataset
            The xarray Dataset to be sliced by sample number.

        Returns:
        --------
        xr.Dataset:
            The subset of the dataset that matches the specified sample criteria.

        Raises:
        -------
        ValueError:
            If the dataset does not contain the time coordinate.
        """
        self.validate_coordinate(params.TIME)

        # Get the time values from the dataset
        time_values = subset[params.TIME].values

        if self.min_sample is not None and self.max_sample is not None:
            subset = subset.sel({params.TIME: slice(
                time_values[self.min_sample], time_values[self.max_sample])})
        elif self.min_sample is not None:
            subset = subset.sel({params.TIME: slice(time_values[self.min_sample], None)})
        elif self.max_sample is not None:
            subset = subset.sel({params.TIME: slice(None, time_values[self.max_sample])})

        return subset

    def _slice_by_time(self, subset: xr.Dataset) -> xr.Dataset:
        """Slice the dataset by time.
        
        Parameters:
        -----------
        subset : xr.Dataset
            The xarray Dataset to be sliced by time.

        Returns:
        --------
        xr.Dataset:
            The subset of the dataset that matches the specified time criteria.

        Raises:
        -------
        ValueError:
            If the dataset does not contain the time coordinate.
        """
        self.validate_coordinate(params.TIME)

        # If min or max datetime is set, slice the dataset accordingly
        if self.min_datetime or self.max_datetime:
            slice_obj = slice(self.min_datetime, self.max_datetime)
            subset = subset.sel({params.TIME: slice_obj})

        return subset

    def _slice_by_parameter_value(self, subset: xr.Dataset) -> xr.Dataset:
        """Slice the dataset by parameter values.

        Parameters:
        -----------
        subset : xr.Dataset
            The xarray Dataset to be sliced by parameter values.    
        
        Returns:
        --------
        xr.Dataset:
            The subset of the dataset that matches the specified parameter criteria.

        Raises:
        -------
        ValueError:
            If the parameter name is set but not available in the dataset.
        """
        if self.parameter_name:
            self.validate_parameter(self.parameter_name)

            # Filter by minimum value if set
            if self.parameter_value_min is not None:
                subset = subset.where(subset[self.parameter_name] >= 
                                      self.parameter_value_min, drop=True)

            # Filter by maximum value if set
            if self.parameter_value_max is not None:
                subset = subset.where(subset[self.parameter_name] <= 
                                      self.parameter_value_max, drop=True)

        return subset

    def get_subset(self) -> xr.Dataset:
        """Return the subset of the dataset based on the specified criteria.

        This method applies all the slicing parameters to filter the dataset.
        It slices the dataset by sample number, time, and parameter values as specified.

        Returns:
        --------
        xr.Dataset:
            The subset of the dataset that matches the specified criteria.
        """
        # Start with the full dataset
        subset = self.data

        # Apply all slicing operations
        subset = self._slice_by_sample_number(subset)
        subset = self._slice_by_time(subset)
        subset = self._slice_by_parameter_value(subset)

        return subset

    def reset(self) -> "SubsetProcessor":
        """Reset all filtering criteria to None.
        
        Returns:
        --------
        SubsetProcessor:
            The current instance for method chaining.
        """
        self.min_sample = None
        self.max_sample = None
        self.min_datetime = None
        self.max_datetime = None
        self.parameter_name = None
        self.parameter_value_max = None
        self.parameter_value_min = None

        return self
