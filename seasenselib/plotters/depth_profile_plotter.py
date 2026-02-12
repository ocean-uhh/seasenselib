"""
Module for creating vertical CTD profiles from sensor data.
"""

from __future__ import annotations
from seasenselib.plotters.base import AbstractPlotter
import seasenselib.parameters as params


class DepthProfilePlotter(AbstractPlotter):
    """Creates CTD depth profiles showing temperature and salinity vs depth.
    
    This class specializes in creating depth profile plots with depth on the
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
        plt = self._get_plt()

        # Get dataset without NaN values
        ds = self._get_dataset_without_nan()

        # Auto-detect variable names based on parameters
        # For temperature: prefer exact match, then _1 suffix, then any that starts with it
        temp_var = None
        if params.TEMPERATURE in ds.data_vars:
            temp_var = params.TEMPERATURE
        elif f"{params.TEMPERATURE}_1" in ds.data_vars:
            temp_var = f"{params.TEMPERATURE}_1"
        else:
            # Find any variable that starts with temperature
            temp_candidates = [v for v in ds.data_vars if v.startswith(params.TEMPERATURE)]
            if temp_candidates:
                # Prefer temperature_1 over other variants
                temp_var = sorted(temp_candidates)[0]
        
        # For salinity: prefer exact match, then _1 suffix, then any that starts with it
        sal_var = None
        if params.SALINITY in ds.data_vars:
            sal_var = params.SALINITY
        elif f"{params.SALINITY}_1" in ds.data_vars:
            sal_var = f"{params.SALINITY}_1"
        else:
            sal_candidates = [v for v in ds.data_vars if v.startswith(params.SALINITY)]
            if sal_candidates:
                sal_var = sorted(sal_candidates)[0]
        
        # For depth: prefer exact match
        depth_var = None
        if params.DEPTH in ds.data_vars:
            depth_var = params.DEPTH
        elif f"{params.DEPTH}_1" in ds.data_vars:
            depth_var = f"{params.DEPTH}_1"
        else:
            depth_candidates = [v for v in ds.data_vars if v.startswith(params.DEPTH)]
            if depth_candidates:
                depth_var = sorted(depth_candidates)[0]
        
        # Validate that we found all required variables
        if not temp_var:
            raise ValueError(f"No temperature variable found (looking for '{params.TEMPERATURE}*')")
        if not sal_var:
            raise ValueError(f"No salinity variable found (looking for '{params.SALINITY}*')")
        if not depth_var:
            raise ValueError(f"No depth variable found (looking for '{params.DEPTH}*')")
        
        # Extract temperature, salinity, and depth variables from the dataset
        temperature = ds[temp_var]
        salinity = ds[sal_var]
        depth = ds[depth_var]

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

    @staticmethod
    def name() -> str:
        return "Depth Profile"

    @staticmethod
    def key() -> str:
        return "depth-profile"

    @classmethod
    def add_cli_arguments(cls, parser):
        """Register CLI arguments for the depth profile plotter."""
        parser.add_argument('--dot-size', type=int, default=3,
                            help='Dot size for scatter plot (1-200)')
        parser.add_argument('--no-lines-between-dots', action='store_true', default=False,
                            help='Disable the connecting lines between dots')
        parser.add_argument('--no-grid', action='store_true', default=False,
                            help='Disable the grid')
