"""
Module for creating time series plots from CTD sensor data.
"""

import matplotlib.pyplot as plt
import numpy as np

from ctd_tools.plotters.base import AbstractPlotter
import ctd_tools.parameters as params


class TimeSeriesPlotter(AbstractPlotter):
    """Creates time series plots for any parameter in the CTD dataset.
    
    This class specializes in creating time series plots showing how a specific
    parameter varies over time.

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    plot(parameter_name, output_file=None, ylim_min=None, ylim_max=10, 
         xlim_min=None, xlim_max=None):
        Creates and displays/saves the time series plot.
    """

    def plot(self, *args, **kwargs):
        """Creates a time series plot for a given parameter.
        
        Parameters:
        -----------
        *args : tuple
            First argument should be parameter_name (str).
        **kwargs : dict
            Keyword arguments:
            - output_file : str, optional - Path to save the plot
            - ylim_min : float, optional - Minimum y-axis value  
            - ylim_max : float, optional - Maximum y-axis value
            
        Raises:
        -------
        ValueError:
            If the parameter_name is not found in the dataset or time data is missing.
        """

        # Check if data is set
        if not self.data:
            raise ValueError("No data available to plot. Please set the data attribute first.")

        # Extract parameters from args and kwargs
        parameter_name = kwargs.get('parameter_name', None)
        output_file = kwargs.get('output_file', None)
        ylim_min = kwargs.get('ylim_min', None)
        ylim_max = kwargs.get('ylim_max', None)

        # Validate required variables
        if parameter_name is None:
            raise ValueError("parameter_name must be provided as argument")

        required_vars = [params.TIME, parameter_name]
        self._validate_required_variables(required_vars)

        # Create a plot
        _fig, ax = plt.subplots(figsize=(10, 5))

        # Plot the parameter data variable
        self.data[parameter_name].plot.line('b-', ax=ax)

        # Creating string date range
        first_date = np.min(self.data[params.TIME].values).astype('datetime64[D]')
        last_date = np.max(self.data[params.TIME].values).astype('datetime64[D]')
        if first_date == last_date:
            dateline = f"on {first_date}"
        else:
            dateline = f"{first_date} to {last_date}"

        # Customize the plot with titles and labels
        long_name = parameter_name
        if 'long_name' in self.data[parameter_name].attrs:
            long_name = self.data[parameter_name].attrs['long_name']

        ax.set_title(f"{long_name} over time ({dateline})")
        ax.set_xlabel('Time')

        # Set y-label with units if available
        y_label = long_name
        if 'units' in self.data[parameter_name].attrs:
            y_label += " [" + self.data[parameter_name].attrs['units'] + "]"
        ax.set_ylabel(y_label)

        # Set y-axis limits if specified
        if ylim_min and ylim_max:
            ax.set_ylim(ylim_min, ylim_max)

        # Set x-axis limits if specified (removed since xlim handling for time series is complex)
        # if xlim_min is not None and xlim_max is not None:
        #     ax.set_xlim(xlim_min, xlim_max)

        # Optionally, you can format the x-axis to better display dates
        plt.gcf().autofmt_xdate()  # Auto-format date on x-axis

        # Save or show the plot
        self._save_or_show_plot(output_file)

    def plot_parameter(self, parameter_name: str, output_file: str | None = None, 
                      ylim_min: float | None = None, ylim_max: float | None = None):
        """Convenience method with explicit parameters for better IDE support.
        
        Parameters:
        -----------
        parameter_name : str
            Name of the parameter to plot (must exist in the dataset).
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        ylim_min : float, optional
            Minimum value for the y-axis. If None, auto-scaled.
        ylim_max : float, optional
            Maximum value for the y-axis. If None, auto-scaled.
        """
        self.plot(parameter_name, output_file=output_file, 
                 ylim_min=ylim_min, ylim_max=ylim_max)
