import xarray
import pandas as pd
import matplotlib.pyplot as plt
import ctd_tools.ctd_parameters as ctdparams
import numpy as np

class CtdResampler:

    def __init__(self, data: xarray.Dataset):
        self.data = data

    def resample(self, time_interval: str) -> xarray.Dataset:
        return self.data.resample(time=time_interval)

class CtdCalculator:

    def __init__(self, data: xarray.Dataset, parameter: str):
        self.data = data
        self.parameter = parameter

    def max(self) -> float:
        """ Maximum """
        return self.data[self.parameter].max(dim=ctdparams.TIME).values
    
    def min(self) -> float:
        """ Minimum """
        return self.data[self.parameter].min(dim=ctdparams.TIME).values

    def mean(self) -> float:
        """ Arithmetic mean """    
        return self.data[self.parameter].mean(dim=ctdparams.TIME).values
    
    def median(self) -> float:
        """ Median """
        return self.data[self.parameter].median(dim=ctdparams.TIME).values

    def std(self) -> float:
        """ Standard deviation """
        return self.data[self.parameter].std(dim=ctdparams.TIME).values
    
    def var(self) -> float:
        """ Variance """
        return self.data[self.parameter].var(dim=ctdparams.TIME).values
