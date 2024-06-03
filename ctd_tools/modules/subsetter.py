import xarray
import pandas as pd
import matplotlib.pyplot as plt
import ctd_tools.ctd_parameters as ctdparams
from datetime import datetime

class CtdSubsetter:

    def __init__(self, data: xarray.Dataset):
        self.data = data
        self.min_sample = None
        self.max_sample = None
        self.min_datetime = None
        self.max_datetime = None
        self.parameter_name = None
        self.parameter_value_max = None
        self.parameter_value_min = None

    def set_sample_min(self, value: int):
        self.min_sample = value

    def set_sample_max(self, value: int):
        self.max_sample = value

    def __handle_time_value(self, value):
        datetime_object = None
        if isinstance(value, str):
            datetime_object =  pd.Timestamp(value)
        elif isinstance(value, pd.Timestamp):
            datetime_object = value
        return datetime_object

    def set_time_min(self, value):
        self.min_datetime = self.__handle_time_value(value)

    def set_time_max(self, value):
        self.max_datetime = self.__handle_time_value(value)

    def set_parameter_name(self, value: str):
        self.parameter_name = value

    def set_parameter_value_max(self, value):
        self.parameter_value_max = value

    def set_parameter_value_min(self, value):
        self.parameter_value_min = value

    def __slice_by_sample_number(self, subset: xarray.Dataset) -> xarray.Dataset:
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
        if self.min_datetime or self.max_datetime:
            slice_obj = slice(self.min_datetime, self.max_datetime)
            subset = subset.sel(**{ctdparams.TIME: slice_obj})
        return subset
    
    def __slice_by_parameter_value(self, subset: xarray.Dataset) -> xarray.Dataset:
        if self.parameter_name:
            if self.parameter_name not in subset:
                raise ValueError(f"Parameter '{self.parameter_name}' not available")
            if self.parameter_value_min:
                subset = subset.where(subset[self.parameter_name] >= self.parameter_value_min, drop=True)
            if self.parameter_value_max:
                subset = subset.where(subset[self.parameter_name] <= self.parameter_value_max, drop=True)
        return subset

    def get_subset(self) -> xarray.Dataset:
        subset = self.data

        # Slice by sample / index number
        subset = self.__slice_by_sample_number(subset)
        
        # Slice by time
        subset = self.__slice_by_time(subset)

        # Slice by parameter / variable values
        subset = self.__slice_by_parameter_value(subset)

        return subset