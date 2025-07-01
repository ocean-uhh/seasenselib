import xarray
import pandas as pd
import ctd_tools.ctd_parameters as ctdparams

class CtdSubsetter:
    """ Subsets sensor data based on sample number, time, and parameter values.

    This class allows for flexible slicing of sensor data stored in an xarray Dataset.
    It can filter data based on sample indices, time ranges, and specific parameter values.

    Example usage:
        subsetter = CtdSubsetter(ds)
        subsetter \
            .set_sample_min(10) \
            .set_sample_max(50) \
            .set_time_min("2023-01-01") \
            .set_time_max("2023-01-31")
        ds_subset = subsetter.get_subset()

    Attributes:
    ------------
    data : xarray.Dataset
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
    """

    def __init__(self, data: xarray.Dataset):
        """ Initializes the CtdSubsetter with the provided xarray Dataset.

        Parameters:
        -----------
        data (xarray.Dataset):
            The xarray Dataset containing the sensor data to be subsetted.

        Raises:
        -------
        TypeError:
            If the provided data is not a xarray.Dataset.
        """

        if not isinstance(data, xarray.Dataset):
            raise TypeError("Data must be a xarray.Dataset")

        # Store the dataset
        self.data = data

        # Initialize slicing parameters
        self.min_sample = None
        self.max_sample = None
        self.min_datetime = None
        self.max_datetime = None
        self.parameter_name = None
        self.parameter_value_max = None
        self.parameter_value_min = None

    def set_sample_min(self, value: int) -> "CtdSubsetter":
        """ Sets the minimum sample index for slicing the dataset.

        Parameters:
        -----------
        value (int):
            The minimum sample index to include in the subset.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated minimum sample index.

        Raises:
        -------
        TypeError:
            If the provided value is not an integer.
        """
        # Validate the sample index
        if not isinstance(value, int):
            raise TypeError("Sample index must be an integer")

        # Store the minimum sample index
        self.min_sample = value

        return self

    def set_sample_max(self, value: int) -> "CtdSubsetter":
        """ Sets the maximum sample index for slicing the dataset.

        Parameters:
        -----------
        value (int):
            The maximum sample index to include in the subset.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated maximum sample index.
        """
        self.max_sample = value

        return self

    def __handle_time_value(self, value: str | pd.Timestamp) -> pd.Timestamp:
        """ Converts a time value to a pandas Timestamp.

        Parameters:
        -----------
        value (str or pd.Timestamp):
            The time value to convert. Can be a string or a pandas Timestamp.

        Returns:
        --------
        pd.Timestamp:
            The converted time value as a pandas Timestamp.

        Raises:
        ------- 
        TypeError:
            If the provided value is not a string or a pandas Timestamp.
        """

        # Validate the time value
        if not isinstance(value, (str, pd.Timestamp)):
            raise TypeError("Time value must be a string or a pandas Timestamp")

        # Convert the time value to a pandas Timestamp
        datetime_object = None
        if isinstance(value, str):
            datetime_object =  pd.Timestamp(value)
        elif isinstance(value, pd.Timestamp):
            datetime_object = value

        return datetime_object

    def set_time_min(self, value: str | pd.Timestamp) -> "CtdSubsetter":
        """ Sets the minimum time for slicing the dataset.

        Parameters:
        -----------
        value (str or pd.Timestamp):
            The minimum time to include in the subset. Can be a string or a pandas Timestamp.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated minimum time.

        Raises:
        -------
        TypeError:
            If the provided value is not a string or a pandas Timestamp.
        """

        # Validate the time value
        if not isinstance(value, (str, pd.Timestamp)):
            raise TypeError("Time value must be a string or a pandas Timestamp")

        # Convert the time value to a pandas Timestamp and store it
        self.min_datetime = self.__handle_time_value(value)

        return self

    def set_time_max(self, value):
        """ Sets the maximum time for slicing the dataset.

        Parameters:
        -----------
        value (str or pd.Timestamp):
            The maximum time to include in the subset. Can be a string or a pandas Timestamp.
        """

        # Validate the time value
        if not isinstance(value, (str, pd.Timestamp)):
            raise TypeError("Time value must be a string or a pandas Timestamp")

        # Convert the time value to a pandas Timestamp and store it
        self.max_datetime = self.__handle_time_value(value)

        return self

    def set_parameter_name(self, value: str):
        """ Sets the name of the parameter to filter by.

        Parameters:
        -----------
        value (str):
            The name of the parameter to filter by. 
            This should be a valid variable name in the dataset.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated parameter name.

        Raises:
        -------
        TypeError:
            If the provided value is not a string.
        ValueError:
            If the provided parameter name is not found in the dataset.
        """

        # Validate the parameter name
        if not isinstance(value, str):
            raise TypeError("Parameter name must be a string")
        if value not in self.data:
            raise ValueError(f"Parameter '{value}' not found in dataset")

        # Store the parameter name
        self.parameter_name = value

        return self

    def set_parameter_value_max(self, value):
        """ Sets the maximum value of the parameter to include in the subset.

        Parameters:
        -----------
        value (float):
            The maximum value of the parameter to include in the subset.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated maximum parameter value.

        Raises:
        -------
        TypeError:
            If the provided value is not a number (int or float).
        """
        # Validate the parameter value
        if not isinstance(value, (int, float)):
            raise TypeError("Parameter value must be a number (int or float)")

        # Store the maximum parameter value
        self.parameter_value_max = value

        return self

    def set_parameter_value_min(self, value):
        """ Sets the minimum value of the parameter to include in the subset.

        Parameters:
        -----------
        value (float):
            The minimum value of the parameter to include in the subset.

        Returns:
        --------
        CtdSubsetter:
            The current instance of CtdSubsetter with the updated minimum parameter value.

        Raises:
        -------
        TypeError:
            If the provided value is not a number (int or float).
        """
        # Validate the parameter value
        if not isinstance(value, (int, float)):
            raise TypeError("Parameter value must be a number (int or float)")

        # Store the minimum parameter value
        self.parameter_value_min = value

        return self

    def __slice_by_sample_number(self, subset: xarray.Dataset) -> xarray.Dataset:
        """ Slices the dataset by sample number (index).

        This method filters the dataset based on the minimum and maximum sample 
        indices set by the user.
        
        Parameters:
        -----------
        subset (xarray.Dataset):
            The xarray Dataset to be sliced by sample number.

        Returns:
        --------
        xarray.Dataset:
            The subset of the dataset that matches the specified sample number criteria.

        Raises:
        -------
        ValueError:
            If the dataset does not contain the sample index coordinate.
        """

        # Check if the dataset has a sample index coordinate
        if ctdparams.TIME not in subset.coords:
            raise ValueError(f"Dataset does not contain '{ctdparams.TIME}' " \
                             "coordinate for slicing by sample number")

        # Get the time values from the dataset
        time_values = subset[ctdparams.TIME].values

        if self.min_sample is not None and self.max_sample is not None:
            selection_criteria = {ctdparams.TIME: slice(
                time_values[self.min_sample], time_values[self.max_sample])}
            subset = subset.sel(**selection_criteria)
        elif self.min_sample is not None:
            selection_criteria = {ctdparams.TIME: slice(time_values[self.min_sample], None)}
            subset = subset.sel(**selection_criteria)
        elif self.max_sample is not None:
            selection_criteria = {ctdparams.TIME: slice(None, time_values[self.max_sample])}
            subset = subset.sel(**selection_criteria)

        return subset

    def __slice_by_time(self, subset: xarray.Dataset) -> xarray.Dataset:
        """ Slices the dataset by time.
        
        This method filters the dataset based on the minimum and maximum time 
        values set by the user.
        
        Parameters:
        -----------
        subset (xarray.Dataset):
            The xarray Dataset to be sliced by time.

        Returns:
        --------
        xarray.Dataset:
            The subset of the dataset that matches the specified time criteria.
        """
        # Check if the dataset has a time coordinate
        if ctdparams.TIME not in subset.coords:
            raise ValueError(f"Dataset does not contain '{ctdparams.TIME}' " \
                             "coordinate for slicing by time")

        # If min or max datetime is set, slice the dataset accordingly
        if self.min_datetime or self.max_datetime:
            slice_obj = slice(self.min_datetime, self.max_datetime)
            subset = subset.sel(**{ctdparams.TIME: slice_obj})

        return subset

    def __slice_by_parameter_value(self, subset: xarray.Dataset) -> xarray.Dataset:
        """ Slices the dataset by parameter values.

        This method filters the dataset based on the specified parameter name and 
        its minimum and maximum values.
        
        Parameters:
        -----------
        subset (xarray.Dataset):
            The xarray Dataset to be sliced by parameter values.    
        
        Returns:
        --------
        xarray.Dataset:
            The subset of the dataset that matches the specified parameter value criteria.
        """

        # Check if the parameter name is set
        if self.parameter_name:

            # Check if the parameter exists in the dataset
            if self.parameter_name not in subset:
                raise ValueError(f"Parameter '{self.parameter_name}' not available")

            # If min value is set, filter the dataset for values greater than or equal to min value
            if self.parameter_value_min:
                subset = subset.where(subset[self.parameter_name] >= \
                                      self.parameter_value_min, drop=True)

            # If max value is set, filter the dataset for values less than or equal to max value
            if self.parameter_value_max:
                subset = subset.where(subset[self.parameter_name] <= \
                                      self.parameter_value_max, drop=True)

        return subset

    def get_subset(self) -> xarray.Dataset:
        """ Returns the subset of the dataset based on the specified slicing parameters.

        This method applies the slicing parameters set by the user to filter the dataset.
        It slices the dataset by sample number, time, and parameter values as specified.

        Returns:
        --------
        xarray.Dataset:
            The subset of the dataset that matches the specified slicing parameters.

        Raises:
        -------
        TypeError:
            If the provided data is not a xarray.Dataset.
        """

        # Validate the dataset
        if not isinstance(self.data, xarray.Dataset):
            raise TypeError("Data must be an xarray.Dataset")

        # Start with the full dataset
        subset = self.data

        # Slice by sample / index number
        subset = self.__slice_by_sample_number(subset)

        # Slice by time
        subset = self.__slice_by_time(subset)

        # Slice by parameter / variable values
        subset = self.__slice_by_parameter_value(subset)

        return subset
