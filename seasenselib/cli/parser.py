"""
Command-line argument parsing with lazy loading capabilities.
"""

import argparse
from typing import List, Optional
from ..core.format_detection import INPUT_FORMATS, OUTPUT_FORMATS


class ArgumentParser:
    """
    Enhanced argument parser with lazy loading support.

    This class provides methods to quickly parse command names and create
    a full argument parser with all subcommands. It allows for lazy loading
    of dependencies, ensuring that only the necessary components are loaded
    when needed.

    Attributes:
    ----------
    base_parser : argparse.ArgumentParser
        The base argument parser used for quick command detection and full parsing.
    Methods:
    -------
    parse_command_quickly(args: List[str]) -> Optional[str]:
        Quickly parse the command name from the provided arguments.
    create_full_parser() -> argparse.ArgumentParser:
        Create the full argument parser with all subcommands and options.
    """

    def __init__(self):
        self.base_parser = None

    def parse_command_quickly(self, args: List[str]) -> Optional[str]:
        """
        Quick parse to extract just the command name without full parsing.
        
        This allows us to determine what dependencies to load before doing
        the full argument parsing.
        """
        if not args:
            return None

        # Create a minimal parser just for command detection
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('command', nargs='?', help='Command to execute')

        try:
            parsed_args, _ = parser.parse_known_args(args)
            return parsed_args.command
        except SystemExit:
            # Handle --help or invalid args
            return None

    def create_full_parser(self) -> argparse.ArgumentParser:
        """Create the full argument parser with all subcommands."""
        parser = argparse.ArgumentParser(
            description='SeaSenseLib - Oceanographic sensor data processing',
            formatter_class=argparse.RawTextHelpFormatter
        )

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Add all subcommands
        self._add_convert_parser(subparsers)
        self._add_show_parser(subparsers)
        self._add_formats_parser(subparsers)
        self._add_plot_parsers(subparsers)
        self._add_subset_parser(subparsers)
        self._add_calc_parser(subparsers)

        return parser

    def _add_convert_parser(self, subparsers):
        """Add convert command parser."""
        # We'll import parameters only when needed
        try:
            # pylint: disable=C0415
            import seasenselib.parameters as params
            mapping_help = ('Map CNV column names to standard parameter names in the '
                           'format name=value. Allowed parameter names are: ' +
                           ', \n'.join(f"{k}" for k, v in params.allowed_parameters().items()))
        except ImportError:
            mapping_help = 'Map CNV column names to standard parameter names'

        format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(OUTPUT_FORMATS)

        convert_parser = subparsers.add_parser('convert',
                    help='Convert a file to a specific format.')
        convert_parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        convert_parser.add_argument('-f', '--input-format',
                    type=str, default=None, choices=INPUT_FORMATS,
                    help='Format of input file')
        convert_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        convert_parser.add_argument('-o', '--output', type=str, required=True,
                    help='Path of output file')
        convert_parser.add_argument('-F', '--output-format', type=str, choices=OUTPUT_FORMATS, 
                    help=format_help)
        convert_parser.add_argument('-m', '--mapping', nargs='+',
                    help=mapping_help)

    def _add_show_parser(self, subparsers):
        """Add show command parser."""
        show_parser = subparsers.add_parser('show',
                    help='Show contents of a file.')
        show_parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        show_parser.add_argument('-f', '--input-format', type=str,
                    default=None, choices=INPUT_FORMATS,
                    help='Format of input file')
        show_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        show_parser.add_argument('-s', '--schema', type=str,
                    choices=['summary', 'info', 'example'], default='summary',
                    help='What to show.')

    def _add_formats_parser(self, subparsers):
        """Add formats command parser."""
        formats_parser = subparsers.add_parser('formats',
                    help='Display supported input file formats.')
        formats_parser.add_argument('--output', '-o', type=str,
                    choices=['table', 'json', 'yaml', 'csv'], default='table',
                    help='Output format (default: table)')
        formats_parser.add_argument('--filter', '-f', type=str,
                    help='Filter formats by name or extension (case-insensitive)')
        formats_parser.add_argument('--sort', '-s', type=str,
                    choices=['name', 'key', 'extension'], default='name',
                    help='Sort by field (default: name)')
        formats_parser.add_argument('--reverse', '-r', action='store_true',
                    help='Reverse sort order')
        formats_parser.add_argument('--no-header', action='store_true',
                    help='Omit header row (useful for scripts)')
        formats_parser.add_argument('--verbose', '-v', action='store_true',
                    help='Show additional information like class names')

    def _add_plot_parsers(self, subparsers):
        """Add plotting command parsers."""
        # Plot T-S diagram
        plot_ts_parser = subparsers.add_parser('plot-ts',
                    help='Plot a T-S diagram from a netCDF, CNV, CSV, or TOB file')
        plot_ts_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        plot_ts_parser.add_argument('-f', '--input-format',
                    type=str, default=None, choices=INPUT_FORMATS,
                    help='Format of input file')
        plot_ts_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        plot_ts_parser.add_argument('-o', '--output', type=str, 
                    help='Path of output file if plot shall be written')
        plot_ts_parser.add_argument('-t', '--title', default='T-S Diagram', type=str,
                    help='Title of the plot.')
        plot_ts_parser.add_argument('--dot-size', default=70, type=int, 
                    help='Dot size for scatter plot (1-200)')
        plot_ts_parser.add_argument('--colormap', default='jet', type=str,
                    help='Name of the colormap for the plot. Must be a valid Matplotlib colormap.')
        plot_ts_parser.add_argument('--no-lines-between-dots', default=False, action='store_true',
                    help='Disable the connecting lines between dots.')
        plot_ts_parser.add_argument('--no-colormap', action='store_true', default=False,
                    help='Disable the colormap in the plot')
        plot_ts_parser.add_argument('--no-isolines', default=False, action='store_true',
                    help='Disable the density isolines in the plot')
        plot_ts_parser.add_argument('--no-grid', default=False, action='store_true',
                    help='Disable the grid.')

        # Plot profile
        plot_profile_parser = subparsers.add_parser('plot-profile',
                    help='Plot a vertical CTD profile from an input file')
        plot_profile_parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        plot_profile_parser.add_argument('-f', '--input-format', type=str,
                    default=None, choices=INPUT_FORMATS,
                    help='Format of input file')
        plot_profile_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        plot_profile_parser.add_argument('-o', '--output', type=str,
                    help='Path of output file if plot shall be written')
        plot_profile_parser.add_argument('-t', '--title', 
                    default='Salinity and Temperature Profiles', type=str,
                    help='Title of the plot.')
        plot_profile_parser.add_argument('--dot-size', default=3, type=int,
                    help='Dot size for scatter plot (1-200)')
        plot_profile_parser.add_argument('--no-lines-between-dots', 
                    default=False, action='store_true',
                    help='Disable the connecting lines between dots.')
        plot_profile_parser.add_argument('--no-grid', default=False, action='store_true',
                    help='Disable the grid.')

        # Plot time series
        plot_series_parser = subparsers.add_parser('plot-series', 
                    help='Plot a time series for one or multiple parameters from an input file')
        plot_series_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        plot_series_parser.add_argument('-f', '--input-format', type=str, 
                    default=None, choices=INPUT_FORMATS, 
                    help='Format of input file')
        plot_series_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        plot_series_parser.add_argument('-o', '--output', type=str, 
                    help='Path of output file if plot shall be written')
        plot_series_parser.add_argument('-p', '--parameter', type=str, nargs='+', required=True,
                    help='Standard name(s) of parameter(s), e.g. ' \
                    '"temperature" or "temperature,salinity"')
        plot_series_parser.add_argument('--dual-axis', action='store_true', default=False,
                    help='Use dual y-axes for parameters with different units')
        plot_series_parser.add_argument('--normalize', action='store_true', default=False,
                    help='Normalize all parameters to 0-1 range for comparison')
        plot_series_parser.add_argument('--colors', type=str, nargs='*',
                    help='Custom colors for each parameter line')
        plot_series_parser.add_argument('--line-styles', type=str, nargs='*',
                    help='Custom line styles for each parameter')

    def _add_subset_parser(self, subparsers):
        """Add subset command parser."""
        format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(OUTPUT_FORMATS)

        subset_parser = subparsers.add_parser('subset', 
                    help='Extract a subset of a file and save the result in another')
        subset_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        subset_parser.add_argument('-f', '--input-format', type=str, 
                    default=None, choices=INPUT_FORMATS,
                    help='Format of input file')
        subset_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        subset_parser.add_argument('-o', '--output', type=str,
                    help='Path of output file')
        subset_parser.add_argument('-F', '--output-format', type=str, choices=OUTPUT_FORMATS, 
                    help=format_help)
        subset_parser.add_argument('--time-min', type=str, 
                    help='Minimum datetime value. Formats are: YYYY-MM-DD HH:ii:mm.ss')
        subset_parser.add_argument('--time-max', type=str, 
                    help='Maximum datetime value. Formats are: YYYY-MM-DD HH:ii:mm.ss')
        subset_parser.add_argument('--sample-min', type=int, 
                    help='Minimum sample/index value (integer)')
        subset_parser.add_argument('--sample-max', type=int, 
                    help='Maximum sample/index value (integer)')
        subset_parser.add_argument('--parameter', type=str, 
                    help='Standard name of a parameter, e.g. "temperature" or "salinity".')
        subset_parser.add_argument('--value-min', type=float, 
                    help='Minimum value for the specified parameter')
        subset_parser.add_argument('--value-max', type=float, 
                    help='Maximum value for the specified parameter')

    def _add_calc_parser(self, subparsers):
        """Add calc command parser."""
        format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(OUTPUT_FORMATS)
        method_choices = [
            'min', 'max', 'mean', 'arithmetic_mean', 'median', 'std',
            'standard_deviation', 'var', 'variance', 'sum'
        ]

        calc_parser = subparsers.add_parser('calc',
                    help='Run an aggregate function on a parameter of the whole dataset')
        calc_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        calc_parser.add_argument('-f', '--input-format', type=str, default=None,
                    choices=INPUT_FORMATS, help='Format of input file')
        calc_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header input file (for Nortek ASCII files)')
        calc_parser.add_argument('-o', '--output', type=str, 
                    help='Path of output file')
        calc_parser.add_argument('-F', '--output-format', type=str, choices=OUTPUT_FORMATS,
                    help=format_help)
        calc_parser.add_argument('-M', '--method', type=str, choices=method_choices,
                    help='Mathematical method operated on the values.')
        calc_parser.add_argument('-p', '--parameter', type=str, required=True,
                    help='Standard name of a parameter, e.g. "temperature" or "salinity".')
        calc_parser.add_argument('-r', '--resample', default=False, action='store_true',
                    help='Resample the time series.')
        calc_parser.add_argument('-T', '--time-interval', type=str,
                    help='Time interval for resampling. Examples: 1M (one month)')
