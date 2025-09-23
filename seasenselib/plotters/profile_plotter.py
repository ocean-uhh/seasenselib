"""
Module for creating vertical CTD profiles from sensor data.
"""

from __future__ import annotations
import matplotlib.pyplot as plt
from seasenselib.plotters.base import AbstractPlotter
import seasenselib.parameters as params


class ProfilePlotter(AbstractPlotter):
    """Creates vertical CTD profiles showing temperature and salinity vs depth.
    
    This class specializes in creating vertical profile plots with depth on the
    y-axis and temperature/salinity on separate x-axes.

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    plot(output_file=None, title='Salinity and Temperature Profiles', 
         show_grid=True, dot_size=3, show_lines_between_dots=True):
        Creates and displays/saves the vertical profile plot.
    """

    def plot(self, output_file: str | None = None, 
             title: str = 'Salinity and Temperature Profiles',
             show_grid: bool = True, dot_size: int = 3,
             show_lines_between_dots: bool = True, *args, **kwargs):
        """Creates a vertical CTD profile plot.
        
        Parameters:
        -----------
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        title : str, default 'Salinity and Temperature Profiles'
            Title for the plot.
        show_grid : bool, default True
            Whether to show grid lines on the plot.
        dot_size : int, default 3
            Size of the scatter plot markers.
        show_lines_between_dots : bool, default True
            Whether to connect data points with lines.
        **kwargs : dict
            Additional keyword arguments (for compatibility).
            
        Raises:
        -------
        ValueError:
            If required variables (temperature, salinity, depth) are missing.
        """
        # Validate required variables
        required_vars = [params.TEMPERATURE, params.SALINITY, params.DEPTH]
        self._validate_required_variables(required_vars)

        # Get dataset without NaN values
        ds = self._get_dataset_without_nan()

        # Extract temperature, salinity, and depth variables from the dataset
        temperature = ds[params.TEMPERATURE]
        salinity = ds[params.SALINITY]
        depth = ds[params.DEPTH]

        # Figure out if depth contains only positive or negative values
        depth_min = depth.min()
        depth_max = depth.max()
        if depth_min <= 0 and depth_max <= 0:
            depth = depth * (-1)

        # Create a scatter plot of salinity and temperature with depth as the y-axis
        fig, ax1 = plt.subplots(figsize=(8, 6))

        # Invert y-axis for depth
        plt.gca().invert_yaxis()

        # Calculate the range for salinity with some padding for aesthetics
        salinity_padding = float((salinity.max() - salinity.min()) * 0.1)
        salinity_range = (float(salinity.min() - salinity_padding), 
                         float(salinity.max() + salinity_padding))    

        # Plot salinity on the primary y-axis
        salinity_color = 'blue'    
        ax1.set_xlim(salinity_range)
        ax1.scatter(salinity, depth, c=salinity_color, label='Salinity', s=dot_size)
        ax1.tick_params(axis='x', labelcolor=salinity_color)

        # Calculate the range for temperature with some padding for aesthetics
        temperature_color = 'red'
        temperature_padding = float((temperature.max() - temperature.min()) * 0.1)
        temperature_range = (float(temperature.min() - temperature_padding), 
                            float(temperature.max() + temperature_padding))  

        # Plot temperature on the secondary x-axis
        ax2 = ax1.twiny()  # Create a twin axis for temperature
        ax2.set_xlim(temperature_range)
        ax2.scatter(temperature, depth, c=temperature_color, label='Temperature', s=dot_size)
        ax2.tick_params(axis='x', labelcolor=temperature_color)

        # Plot lines between the dots
        if show_lines_between_dots:
            ax1.plot(salinity, depth, color=salinity_color, linestyle='-', linewidth=0.5)
            ax2.plot(temperature, depth, color=temperature_color, linestyle='-', linewidth=0.5)

        # Add grid lines to the plot for better readability
        if show_grid:
            ax1.grid(color='gray', linestyle='--', linewidth=0.5)

        # Set axis labels and title
        ax1.set_title(title)
        ax1.set_xlabel('Salinity', color=salinity_color)
        ax1.set_ylabel('Depth', color='black')
        ax2.set_xlabel('Temperature', color=temperature_color)

        # Add a legend
        ax1.legend()

        # Adjust layout
        fig.tight_layout()

        # Save or show the plot
        self._save_or_show_plot(output_file)
