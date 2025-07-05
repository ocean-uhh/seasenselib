"""
Module for creating T-S (Temperature-Salinity) diagrams from sensor data.
"""

import matplotlib.pyplot as plt
import numpy as np
import gsw

from ctd_tools.plotters.base import AbstractPlotter
import ctd_tools.parameters as params


class TsDiagramPlotter(AbstractPlotter):
    """Creates T-S (Temperature-Salinity) diagrams from CTD sensor data.
    
    This class specializes in creating T-S diagrams, which are scatter plots
    of temperature vs salinity data points, often colored by depth and with
    optional density isolines.

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    plot(output_file=None, title='T-S Diagram', dot_size=70, use_colormap=True, 
         show_density_isolines=True, colormap='jet', show_lines_between_dots=True,
         show_grid=True):
        Creates and displays/saves the T-S diagram.
    _plot_density_isolines():
        Adds density isolines to the T-S diagram.
    """

    def plot(self, output_file: str | None = None, title: str = 'T-S Diagram',
             dot_size: int = 70, use_colormap: bool = True, 
             show_density_isolines: bool = True, colormap: str = 'jet',
             show_lines_between_dots: bool = True, show_grid: bool = True, *args, **kwargs):
        """Creates a T-S diagram plot.
        
        Parameters:
        -----------
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        title : str, default 'T-S Diagram'
            Title for the plot.
        dot_size : int, default 70
            Size of the scatter plot markers.
        use_colormap : bool, default True
            Whether to color points by depth using a colormap.
        show_density_isolines : bool, default True
            Whether to show density isolines on the plot.
        colormap : str, default 'jet'
            Matplotlib colormap name to use for depth coloring.
        show_lines_between_dots : bool, default True
            Whether to connect data points with lines.
        show_grid : bool, default True
            Whether to show grid lines on the plot.
            
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

        temperature = ds[params.TEMPERATURE]
        salinity = ds[params.SALINITY]
        depth = ds[params.DEPTH]

        # Check for potential temperature and use it if available
        if params.POTENTIAL_TEMPERATURE in ds:
            temperature = ds[params.POTENTIAL_TEMPERATURE]

        # Create figure
        fig = plt.figure(figsize=(15, 8))

        # Create a line plot of temperature vs. salinity
        if show_lines_between_dots:
            plt.plot(salinity, temperature, color='gray', linestyle='-', linewidth=0.5)

        # Create a scatter plot of temperature vs. salinity
        if use_colormap:
            plt.scatter(salinity, temperature, c=depth, cmap=colormap, marker='o', s=dot_size)
            plt.colorbar(label='Depth [m]')  # Plot legend for colormap
        else:
            plt.scatter(salinity, temperature, c='black', marker='o', s=dot_size)

        # Add grid lines to the plot for better readability
        if show_grid:
            plt.grid(color='gray', linestyle='--', linewidth=0.5)

        # Set plot labels and title
        plt.title(title)
        plt.xlabel('Salinity [PSU]')

        # Set y-label based on temperature type
        if params.POTENTIAL_TEMPERATURE in ds:
            plt.ylabel(ds[params.POTENTIAL_TEMPERATURE].attrs['long_name'] + \
                      " [" + ds[params.POTENTIAL_TEMPERATURE].attrs['units'] + "]")
        else:
            plt.ylabel(ds[params.TEMPERATURE].attrs['long_name'] + \
                      " [" + ds[params.TEMPERATURE].attrs['units'] + "]")

        # Integrate density isolines if wanted
        if show_density_isolines:
            self._plot_density_isolines(ds)

        # Enable tight layout
        plt.tight_layout()

        # Save or show the plot
        self._save_or_show_plot(output_file)

    def _plot_density_isolines(self, ds):
        """Plots density isolines into the T-S diagram.
        
        Parameters:
        -----------
        ds : xr.Dataset
            The dataset containing temperature and salinity data.
        """
        # Define the min / max values for plotting isopycnals
        t_min = ds[params.TEMPERATURE].values.min()
        t_max = ds[params.TEMPERATURE].values.max()
        s_min = ds[params.SALINITY].values.min()
        s_max = ds[params.SALINITY].values.max()

        # Calculate "padding" for temperature axis
        t_width = t_max - t_min
        t_min -= (t_width * 0.1)
        t_max += (t_width * 0.1)

        # Calculate "padding" for salinity axis
        s_width = s_max - s_min
        s_min -= (s_width * 0.1)
        s_max += (s_width * 0.1)

        # Calculate how many gridcells we need in the x and y dimensions
        factor = round(max([t_width, s_width]) / min([t_width, s_width]))
        if s_width > t_width:
            xdim = 150
            ydim = round(150 / factor)
        else:
            ydim = 150
            xdim = round(150 / factor)

        density = np.zeros((int(ydim), int(xdim)))

        # Create temp and salt vectors of appropriate dimensions
        ti = np.linspace(t_min, t_max, ydim)
        si = np.linspace(s_min, s_max, xdim)

        # Loop to fill in grid with densities
        for j in range(0, int(ydim)):
            for i in range(0, int(xdim)):
                density[j, i] = gsw.rho(si[i], ti[j], 0)

        # Subtract 1000 to convert density to sigma-t
        sigma_t = density - 1000

        # Plot isolines
        cs = plt.contour(si, ti, sigma_t, linewidths=1, linestyles='dashed', colors='gray')
        plt.clabel(cs, fontsize=8, inline=1, fmt='%1.2f')  # Label every second level

        # Add sigma_0 in gray in the left upper corner
        plt.text(0.02, 0.95, r"$\sigma_0$", color='gray', fontsize=18, 
                fontweight='bold', transform=plt.gca().transAxes)
