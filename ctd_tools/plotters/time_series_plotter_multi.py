"""
Module for creating multi-parameter time series plots from CTD sensor data.

This module extends the basic time series plotting capabilities to support
plotting multiple parameters in a single time series plot with advanced
features like dual y-axes, normalization, and custom styling.
"""

from typing import List, Tuple
import matplotlib.pyplot as plt
import numpy as np
from ctd_tools.plotters.base import AbstractPlotter
import ctd_tools.parameters as params


class TimeSeriesPlotterMulti(AbstractPlotter):
    """Creates time series plots for multiple parameters in the CTD dataset.
    
    This class specializes in creating time series plots showing how multiple
    parameters vary over time. It supports:
    - Multiple parameters on the same y-axis
    - Multiple parameters on dual y-axes (left/right)
    - Automatic unit-based grouping
    - Custom styling for each parameter
    - Data normalization for comparison
    - Single parameter plotting (for consistency)

    Attributes:
    -----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    plot(parameter_names, output_file=None, dual_axis=False, 
         left_params=None, right_params=None, normalize=False, **kwargs):
        Creates and displays/saves the time series plot for multiple parameters.
    plot_single_parameter(parameter_name, ...):
        Convenience method for single parameter plotting.
    plot_multiple_parameters(parameter_names, ...):
        Convenience method for multi-parameter plotting with explicit parameters.
    """

    def plot(self, *args, **kwargs):
        """Creates a time series plot for multiple parameters.
        
        Parameters:
        -----------
        *args : tuple
            First argument can be parameter_names (str or List[str]).
        **kwargs : dict
            Keyword arguments:
            - parameter_names : str or List[str] - Parameter name(s) to plot
            - output_file : str, optional - Path to save the plot
            - dual_axis : bool, default False - Use dual y-axes for different units
            - left_params : List[str], optional - Parameters for left y-axis
            - right_params : List[str], optional - Parameters for right y-axis
            - normalize : bool, default False - Normalize all parameters to 0-1 range
            - colors : List[str], optional - Custom colors for each parameter
            - line_styles : List[str], optional - Custom line styles
            - ylim_left : Tuple[float, float], optional - (min, max) for left y-axis
            - ylim_right : Tuple[float, float], optional - (min, max) for right y-axis
            
        Raises:
        -------
        ValueError:
            If parameters are not found in the dataset or time data is missing.
        """

        # Check if data is set
        if not self.data:
            raise ValueError("No data available to plot. Please set the data attribute first.")

        # Extract parameter names from args or kwargs
        parameter_names = self._extract_parameter_names(*args, **kwargs)

        # Extract other parameters
        output_file = kwargs.get('output_file', None)
        dual_axis = kwargs.get('dual_axis', False)
        left_params = kwargs.get('left_params', None)
        right_params = kwargs.get('right_params', None)
        normalize = kwargs.get('normalize', False)
        colors = kwargs.get('colors', None)
        line_styles = kwargs.get('line_styles', None)

        # Validate required variables
        required_vars = [params.TIME] + parameter_names
        self._validate_required_variables(required_vars)

        # Determine axis assignment
        if dual_axis:
            left_params, right_params = self._determine_axis_assignment(
                parameter_names, left_params, right_params
            )
        else:
            left_params = parameter_names
            right_params = []

        # Create the plot
        self._create_multi_parameter_plot(
            left_params, right_params, normalize, colors, line_styles, kwargs
        )

        # Save or show the plot
        self._save_or_show_plot(output_file)

    def _extract_parameter_names(self, *args, **kwargs):
        """Extract parameter names from args and kwargs."""
        # Check for parameter_names in kwargs
        if 'parameter_names' in kwargs:
            parameter_names = kwargs['parameter_names']
        # Check first positional argument
        elif args:
            parameter_names = args[0]
        else:
            raise ValueError("parameter_names must be provided")

        # Normalize to list
        if isinstance(parameter_names, str):
            return [parameter_names]
        elif isinstance(parameter_names, list):
            return parameter_names
        else:
            raise ValueError("parameter_names must be a string or list of strings")

    def _determine_axis_assignment(self, parameter_names, left_params, right_params):
        """Determine which parameters go on which axis."""
        if left_params is not None and right_params is not None:
            # Manual assignment
            return left_params, right_params

        # Automatic assignment based on units
        if self.data is None:
            return parameter_names, []

        units_groups = {}
        for param in parameter_names:
            units = self.data[param].attrs.get('units', 'unknown')
            if units not in units_groups:
                units_groups[units] = []
            units_groups[units].append(param)

        # Assign first group to left, second to right (if exists)
        groups = list(units_groups.values())
        left_params = groups[0] if groups else []
        right_params = groups[1] if len(groups) > 1 else []

        # If more than 2 unit groups, combine extras with left
        for i in range(2, len(groups)):
            left_params.extend(groups[i])

        return left_params, right_params

    def _create_multi_parameter_plot(self, left_params, right_params, normalize, 
                                     colors, line_styles, kwargs):
        """Create the actual multi-parameter plot."""
        if self.data is None:
            raise ValueError("No data available to plot.")

        _fig, ax1 = plt.subplots(figsize=(12, 6))

        # Set up colors and line styles
        all_params = left_params + right_params
        if colors is None:
            # Use a predefined color cycle
            color_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                          '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            colors = [color_cycle[i % len(color_cycle)] for i in range(len(all_params))]
        line_styles = line_styles or ['-'] * len(all_params)

        # Plot left axis parameters
        lines_legends = []
        if left_params:
            self._plot_parameters_on_axis(ax1, left_params, colors[:len(left_params)], 
                                        line_styles[:len(left_params)], normalize, 
                                        lines_legends)

        # Plot right axis parameters
        ax2 = None
        if right_params:
            ax2 = ax1.twinx()
            right_colors = colors[len(left_params):]
            right_styles = line_styles[len(left_params):]
            self._plot_parameters_on_axis(ax2, right_params, right_colors, 
                                        right_styles, normalize, lines_legends)

        # Set up the plot appearance
        self._setup_plot_appearance(ax1, ax2, left_params, right_params, 
                                    normalize, lines_legends, kwargs)

    def _plot_parameters_on_axis(self, ax, parameters, colors, line_styles, 
                                 normalize, lines_legends):
        """Plot parameters on a specific axis."""
        if self.data is None:
            raise ValueError("No data available to plot.")

        for i, param in enumerate(parameters):
            data = self.data[param]

            if normalize:
                # Normalize to 0-1 range
                data_min, data_max = data.min().values, data.max().values
                if data_max != data_min:
                    data = (data - data_min) / (data_max - data_min)

            line = ax.plot(self.data[params.TIME], data, 
                          color=colors[i], linestyle=line_styles[i], 
                          linewidth=1.5, label=self._get_parameter_label(param, normalize))
            lines_legends.append(line[0])

    def _get_parameter_label(self, param, normalize):
        """Get the label for a parameter including units."""
        if self.data is None:
            return param

        label = param
        if 'long_name' in self.data[param].attrs:
            label = self.data[param].attrs['long_name']

        if not normalize and 'units' in self.data[param].attrs:
            label += f" [{self.data[param].attrs['units']}]"
        elif normalize:
            label += " (normalized)"

        return label

    def _setup_plot_appearance(self, ax1, ax2, left_params, right_params, 
                               normalize, lines_legends, kwargs):
        """Set up titles, labels, legend, and axis limits."""
        if self.data is None:
            raise ValueError("No data available to plot.")

        # Create date range string
        first_date = np.min(self.data[params.TIME].values).astype('datetime64[D]')
        last_date = np.max(self.data[params.TIME].values).astype('datetime64[D]')
        dateline = f"on {first_date}" if first_date == last_date else f"{first_date} to {last_date}"

        # Set title
        param_count = len(left_params) + len(right_params)
        if param_count == 1:
            param_name = (left_params + right_params)[0]
            long_name = self.data[param_name].attrs.get('long_name', param_name)
            title = f"{long_name} over time ({dateline})"
        else:
            title = f"Multi-parameter time series ({dateline})"
        ax1.set_title(title)

        # Set axis labels
        ax1.set_xlabel('Time')

        if left_params:
            if normalize:
                ax1.set_ylabel('Normalized values')
            elif len(left_params) == 1:
                ax1.set_ylabel(self._get_parameter_label(left_params[0], False))
            else:
                # Group by units for y-label
                units = [self.data[p].attrs.get('units', '') for p in left_params]
                unique_units = list(set(u for u in units if u))
                if len(unique_units) == 1:
                    ax1.set_ylabel(f"Value [{unique_units[0]}]")
                else:
                    ax1.set_ylabel("Values (mixed units)")

        if ax2 and right_params:
            if normalize:
                ax2.set_ylabel('Normalized values')
            elif len(right_params) == 1:
                ax2.set_ylabel(self._get_parameter_label(right_params[0], False))
            else:
                units = [self.data[p].attrs.get('units', '') for p in right_params]
                unique_units = list(set(u for u in units if u))
                if len(unique_units) == 1:
                    ax2.set_ylabel(f"Value [{unique_units[0]}]")
                else:
                    ax2.set_ylabel("Values (mixed units)")

        # Set axis limits
        if 'ylim_left' in kwargs and kwargs['ylim_left']:
            ax1.set_ylim(kwargs['ylim_left'])
        if ax2 and 'ylim_right' in kwargs and kwargs['ylim_right']:
            ax2.set_ylim(kwargs['ylim_right'])

        # Add legend
        if len(lines_legends) > 1:
            ax1.legend(lines_legends, [line.get_label() for line in lines_legends], 
                      loc='best', framealpha=0.9)

        # Format x-axis dates
        plt.gcf().autofmt_xdate()
        plt.tight_layout()

    def plot_single_parameter(self, parameter_name: str, output_file: str | None = None, 
                             ylim_min: float | None = None, ylim_max: float | None = None,
                             color: str | None = None, line_style: str = '-'):
        """Convenience method for single parameter plotting.
        
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
        color : str, optional
            Color for the line. If None, uses default color cycle.
        line_style : str, default '-'
            Line style for the plot ('-', '--', '-.', ':').
        """
        ylim_left = (ylim_min, ylim_max) if ylim_min is not None and ylim_max is not None else None
        colors = [color] if color else None
        self.plot(parameter_name, output_file=output_file, ylim_left=ylim_left,
                 colors=colors, line_styles=[line_style])

    def plot_multiple_parameters(self, parameter_names: List[str], output_file: str | None = None,
                                dual_axis: bool = False, left_params: List[str] | None = None,
                                right_params: List[str] | None = None, normalize: bool = False,
                                colors: List[str] | None = None,
                                line_styles: List[str] | None = None,
                                ylim_left: Tuple[float, float] | None = None,
                                ylim_right: Tuple[float, float] | None = None):
        """Convenience method for multi-parameter plotting with explicit parameters.
        
        Parameters:
        -----------
        parameter_names : List[str]
            List of parameter names to plot (must exist in the dataset).
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        dual_axis : bool, default False
            Use dual y-axes for different units or manual assignment.
        left_params : List[str], optional
            Parameters to plot on the left y-axis (if dual_axis=True).
        right_params : List[str], optional
            Parameters to plot on the right y-axis (if dual_axis=True).
        normalize : bool, default False
            Normalize all parameters to 0-1 range for comparison.
        colors : List[str], optional
            Custom colors for each parameter line.
        line_styles : List[str], optional
            Custom line styles for each parameter ('-', '--', '-.', ':').
        ylim_left : Tuple[float, float], optional
            Y-axis limits for left axis as (min, max).
        ylim_right : Tuple[float, float], optional
            Y-axis limits for right axis as (min, max).
        """
        self.plot(parameter_names=parameter_names, output_file=output_file,
                 dual_axis=dual_axis, left_params=left_params, right_params=right_params,
                 normalize=normalize, colors=colors, line_styles=line_styles,
                 ylim_left=ylim_left, ylim_right=ylim_right)

    def plot_with_auto_dual_axis(self, parameter_names: List[str], output_file: str | None = None,
                                normalize: bool = False, **kwargs):
        """Convenience method that automatically uses dual axis based on parameter units.
        
        Parameters:
        -----------
        parameter_names : List[str]
            List of parameter names to plot (must exist in the dataset).
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        normalize : bool, default False
            Normalize all parameters to 0-1 range for comparison.
        **kwargs : dict
            Additional styling options (colors, line_styles, ylim_left, ylim_right).
        """
        self.plot(parameter_names=parameter_names, output_file=output_file,
                 dual_axis=True, normalize=normalize, **kwargs)

    def plot_normalized_comparison(self, parameter_names: List[str], output_file: str | None = None,
                                  colors: List[str] | None = None, **kwargs):
        """Convenience method for normalized parameter comparison.
        
        All parameters are normalized to 0-1 range for easy comparison of trends
        regardless of their original units or scales.
        
        Parameters:
        -----------
        parameter_names : List[str]
            List of parameter names to plot (must exist in the dataset).
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        colors : List[str], optional
            Custom colors for each parameter line.
        **kwargs : dict
            Additional styling options.
        """
        self.plot(parameter_names=parameter_names, output_file=output_file,
                 normalize=True, colors=colors, **kwargs)
