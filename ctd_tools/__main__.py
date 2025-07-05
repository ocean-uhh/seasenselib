"""
This module is the main entry point for the CTD Tools command line interface (CLI).

It provides a command controller that routes commands to the appropriate handlers
and manages the execution of various CTD data processing tasks such as conversion, 
plotting, calculation, and subsetting of CTD sensor data.
"""

import argparse
import os
import re
from io import StringIO
import csv
import json
import yaml
import pandas as pd
import xarray as xr
import ctd_tools.parameters as params
from . import readers
from .writers import NetCdfWriter, CsvWriter, ExcelWriter
from .plotters import TsDiagramPlotter, ProfilePlotter, TimeSeriesPlotter, \
    TimeSeriesPlotterMulti
from .processors import SubsetProcessor, StatisticsProcessor, ResampleProcessor

# module name
__module_name__ = 'ctd_tools'

# Input format keys for the CLI commands
INPUTFORMAT_KEY_CSV = 'csv'
INPUTFORMAT_KEY_NETCDF = 'netcdf'
INPUTFORMAT_KEY_NORTEK_ASCII = 'nortek-ascii'
INPUTFORMAT_KEY_RBR_ASCII = 'rbr-ascii'
INPUTFORMAT_KEY_RBR_RSK_AUTO = 'rbr-rsk'
INPUTFORMAT_KEY_RBR_RSK_DEFAULT = 'rbr-rsk-default'
INPUTFORMAT_KEY_RBR_RSK_LEGACY = 'rbr-rsk-legacy'
INPUTFORMAT_KEY_SBE_CNV = 'sbe-cnv'
INPUTFORMAT_KEY_SEASUN_TOB = 'seasun-tob'

# Input formats for the CLI commands
input_formats = [
    INPUTFORMAT_KEY_SBE_CNV,      # Seabird CNV
    INPUTFORMAT_KEY_SEASUN_TOB,   # Sea & Sun TOB
    INPUTFORMAT_KEY_CSV,          # Comma separated file
    INPUTFORMAT_KEY_NETCDF,       # netCDF
    INPUTFORMAT_KEY_RBR_ASCII,    # RBR ASCII
    INPUTFORMAT_KEY_NORTEK_ASCII, # Nortek ASCII
    INPUTFORMAT_KEY_RBR_RSK_LEGACY, # RBR RSK Legacy
    INPUTFORMAT_KEY_RBR_RSK_DEFAULT, # RBR RSK Default (modern format)
    INPUTFORMAT_KEY_RBR_RSK_AUTO  # RBR RSK Auto (auto-detect format)
]

# Output formats for the CLI commands
output_formats = [
    'netcdf',       # netCDF
    'csv',          # Comma separated file
    'excel'         # Excel
]

class CommandController:
    """ Controller logic for CLI commands """

    def __init__(self, argsparser, args):
        self.argsparser = argsparser
        self.args = args

    def execute(self):
        """ Manages the routing according to the given command in the args. """

        if self.args.command == 'convert':
            self.handle_convert_command()
        elif self.args.command == 'plot-ts':
            self.handle_plot_ts_command()
        elif self.args.command == 'plot-profile':
            self.handle_plot_profile_command()
        elif self.args.command == 'plot-series':
            self.handle_plot_series_command()
        elif self.args.command == 'show':
            self.handle_show_command()
        elif self.args.command == 'formats':
            self.handle_formats_command()
        elif self.args.command == 'calc':
            self.handle_calc_command()
        elif self.args.command == 'subset':
            self.handle_subset_command()
        else:
            self.argsparser.print_help()

    def __read_data(self, input_file, header_input_file=None) -> xr.Dataset | None:
        """ Helper for reading data from input file of different types.
        Returns the data. """

        input_format = self.args.input_format

        if input_file.lower().endswith('.nc') or input_format == INPUTFORMAT_KEY_NETCDF:
            reader = readers.NetCdfReader(input_file)
        elif input_file.lower().endswith('.csv') or input_format == INPUTFORMAT_KEY_CSV:
            reader = readers.CsvReader(input_file)
        elif input_file.lower().endswith('.cnv') or input_format == INPUTFORMAT_KEY_SBE_CNV:
            reader = readers.SbeCnvReader(input_file)
        elif input_file.lower().endswith('.tob') or input_format == INPUTFORMAT_KEY_SEASUN_TOB:
            reader = readers.SeasunTobReader(input_file)
        elif input_format == INPUTFORMAT_KEY_RBR_ASCII:
            reader = readers.RbrAsciiReader(input_file)
        elif input_format == INPUTFORMAT_KEY_NORTEK_ASCII:
            if not header_input_file:
                raise argparse.ArgumentTypeError(
                    "Header input file is required for Nortek ASCII files."
                )
            reader = readers.NortekAsciiReader(input_file, header_input_file)
        elif input_format == INPUTFORMAT_KEY_RBR_RSK_LEGACY:
            reader = readers.RbrRskLegacyReader(input_file)
        elif input_format == INPUTFORMAT_KEY_RBR_RSK_DEFAULT:
            reader = readers.RbrRskReader(input_file)
        elif input_file.lower().endswith('.rsk') or input_format == INPUTFORMAT_KEY_RBR_RSK_AUTO:
            reader = readers.RbrRskAutoReader(input_file)
        else:
            raise argparse.ArgumentTypeError("Input file must be a netCDF (.nc) " \
                    "CSV (.csv), CNV (.cnv), or TOB (.tob), or RBR ASCII file.")
        return reader.get_data()

    def __handle_output_directory(self, output_file):
        """ Helper to create the output directory if it doesn't exist. """
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

    def __validate_output_format(self, output_file: str, output_format: str | None = None) -> str:
        """Validate and determine the output format early before processing.
        
        Parameters:
        -----------
        output_file : str
            Path to the output file
        output_format : str, optional
            Explicit output format. If None, will be detected from file extension.
            
        Returns:
        --------
        str
            The validated output format
            
        Raises:
        -------
        argparse.ArgumentTypeError
            If the output format is invalid or cannot be determined
        """
        # Determine output format
        if output_format is None:
            if output_file.lower().endswith('.nc'):
                output_format = 'netcdf'
            elif output_file.lower().endswith('.csv'):
                output_format = 'csv'
            elif output_file.lower().endswith('.xlsx'):
                output_format = 'excel'
            else:
                raise argparse.ArgumentTypeError(
                    "Output file must be a netCDF (.nc), " \
                    "CSV (.csv), or Excel (.xlsx) file.")

        # Validate the format is supported
        if output_format not in ['netcdf', 'csv', 'excel']:
            raise argparse.ArgumentTypeError(f'Unknown output format: {output_format}')

        return output_format

    def __write_output_file(self, data: xr.Dataset, output_file: str, output_format: str):
        """Write data to output file using the specified format.
        
        Parameters:
        -----------
        data : xr.Dataset
            The dataset to write
        output_file : str
            Path to the output file
        output_format : str
            The output format (must be pre-validated)
        """
        # Create output directory if it doesn't exist
        self.__handle_output_directory(output_file)

        # Write data to file
        if output_format == 'netcdf':
            writer = NetCdfWriter(data)
            writer.write(output_file)
        elif output_format == 'csv':
            writer = CsvWriter(data)
            writer.write(output_file)
        elif output_format == 'excel':
            writer = ExcelWriter(data)
            writer.write(output_file)
        else:
            raise argparse.ArgumentTypeError(f'Unknown output format: {output_format}')

    def handle_plot_series_command(self):
        """ Handles the CLI 'plot-series' command. """

        # Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Parse parameters (support both comma-separated and space-separated)
        parameters = self._parse_parameters(self.args.parameter)

        # Determine which plotter to use based on number of parameters
        if len(parameters) == 1:
            # Single parameter - use original TimeSeriesPlotter
            plotter = TimeSeriesPlotter(data)
            plotter.plot(parameter_name=parameters[0], output_file=self.args.output)
        else:
            # Multiple parameters - use TimeSeriesPlotterMulti
            plotter = TimeSeriesPlotterMulti(data)

            # Extract optional styling arguments
            dual_axis = getattr(self.args, 'dual_axis', False)
            normalize = getattr(self.args, 'normalize', False)
            colors = getattr(self.args, 'colors', None)
            line_styles = getattr(self.args, 'line_styles', None)

            # Plot multiple parameters
            plotter.plot(
                parameter_names=parameters,
                output_file=self.args.output,
                dual_axis=dual_axis,
                normalize=normalize,
                colors=colors,
                line_styles=line_styles
            )

    def _parse_parameters(self, parameter_args):
        """Parse parameter arguments supporting both comma-separated and space-separated formats.
        
        Parameters:
        -----------
        parameter_args : list[str]
            List of parameter arguments from argparse
            
        Returns:
        --------
        list[str]
            Parsed list of parameter names
            
        Examples:
        ---------
        Input: ["temperature,salinity,pressure"]
        Output: ["temperature", "salinity", "pressure"]
        
        Input: ["temperature", "salinity", "pressure"] 
        Output: ["temperature", "salinity", "pressure"]
        
        Input: ["temperature,salinity", "pressure"]
        Output: ["temperature", "salinity", "pressure"]
        """
        parameters = []

        for arg in parameter_args:
            # Split by comma and strip whitespace
            comma_split = [param.strip() for param in arg.split(',')]
            parameters.extend(comma_split)

        # Remove empty strings and duplicates while preserving order
        seen = set()
        result = []
        for param in parameters:
            if param and param not in seen:
                seen.add(param)
                result.append(param)

        return result

    def handle_plot_profile_command(self):
        """ Handles the CLI 'plot-profile' command. """

        # Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Create plotter
        plotter = ProfilePlotter(data)
        plotter.plot(
            output_file=self.args.output,
            title=self.args.title,
            dot_size=self.args.dot_size,
            show_lines_between_dots=(not self.args.no_lines_between_dots),
            show_grid=(not self.args.no_grid)
        )

    def handle_plot_ts_command(self):
        """ Handles the CLI 'plot-ts' command. """

        if self.args.dot_size:
            if self.args.dot_size < 1 or self.args.dot_size > 200:
                raise argparse.ArgumentTypeError("--dot-size must be between 1 and 200")

        # Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Create plotter
        plotter = TsDiagramPlotter(data)
        plotter.plot(
            output_file=self.args.output, 
            title=self.args.title, 
            dot_size=self.args.dot_size, 
            use_colormap=(not self.args.no_colormap), 
            show_density_isolines=(not self.args.no_isolines),
            colormap=self.args.colormap, 
            show_lines_between_dots=(not self.args.no_lines_between_dots),
            show_grid=(not self.args.no_grid)
        )

    def handle_convert_command(self):
        """ Handles the CLI 'convert' command. """

        # 1. Validate output format early before processing
        output_format = self.__validate_output_format(self.args.output, self.args.output_format)

        # 2. Validate parameter mapping
        parameter_mapping = {}
        allowed_parameters = params.allowed_parameters()
        if self.args.mapping:
            for mapping in self.args.mapping:
                key, value = mapping.split('=')
                if key in allowed_parameters:
                    parameter_mapping[key] = value
                else:
                    raise ValueError(f"Unallowed parameter name: {key}. " \
                            "Allowed parameters are: {', '.join(allowed_parameters)}")

        # 3. Read and process data
        data = self.__read_data(self.args.input)

        # If data is empty, raise an error
        if not data:
            raise ValueError('No data found in file.')

        # 4. Write data using the validated format
        self.__write_output_file(data, self.args.output, output_format)

    def handle_show_command(self):
        """ Handles the CLI 'show' command. """

        # Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        if data:
            schema = self.args.schema
            if schema == 'summary':
                print(data)
            elif schema == 'info':
                data.info()
            elif schema == 'example':
                df = data.to_dataframe()
                print(df.head())
        else:
            raise ValueError('No data found in file.')

    def handle_subset_command(self):
        """ Handles the CLI 'subset' command. """

        # 1. Validate output format early if output is specified
        output_format = None
        if self.args.output:
            output_format = self.__validate_output_format(self.args.output, self.args.output_format)

        # 2. Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        if not data:
            raise ValueError('No data found in file.')

        # 3. Process data (subsetting)
        subsetter = SubsetProcessor(data)
        if self.args.sample_min:
            subsetter.set_sample_min(self.args.sample_min)
        if self.args.sample_max:
            subsetter.set_sample_max(self.args.sample_max)
        if self.args.time_min:
            subsetter.set_time_min(self.args.time_min)
        if self.args.time_max:
            subsetter.set_time_max(self.args.time_max)
        if self.args.parameter:
            subsetter.set_parameter_name(self.args.parameter)
        if self.args.value_min:
            subsetter.set_parameter_value_min(self.args.value_min)
        if self.args.value_max:
            subsetter.set_parameter_value_max(self.args.value_max)
        subset = subsetter.get_subset()

        # 4. Write output or print to console
        if self.args.output:
            assert output_format is not None  # This should never be None here
            self.__write_output_file(subset, self.args.output, output_format)
        else:
            # If no output file specified, print to console
            print(subset)

    def __run_calculation(self, data):
        """ Runs the specified calculation on the provided data. """

        calc = StatisticsProcessor(data, self.args.parameter)
        if self.args.method == 'max':
            return calc.max()
        if self.args.method == 'min':
            return calc.min()
        if self.args.method == 'mean':
            return calc.mean()
        if self.args.method == 'median':
            return calc.median()
        if self.args.method == 'std' or self.args.method == 'standard_deviation':
            return calc.std()
        if self.args.method == 'var' or self.args.method == 'variance':
            return calc.var()
        raise ValueError(f"Unknown calculation method: {self.args.method}")

    def handle_calc_command(self):
        """ Handles the CLI 'calc' command. """

        # Read data from input file
        data = self.__read_data(self.args.input, self.args.header_input)

        if not data:
            raise ValueError('No data found in file.')

        if self.args.resample:
            resampler = ResampleProcessor(data)
            data = resampler.resample(self.args.time_interval)

            # Format the datetime output based on the time interval
            datetime_format_pattern = "%Y-%m-%d %H:%M:%S"
            if re.match(r"^[0-9\.]*M$", self.args.time_interval):
                datetime_format_pattern = '%Y-%m'
            elif re.match(r"^[0-9\.]*Y$", self.args.time_interval):
                datetime_format_pattern = '%Y'
            elif re.match(r"^[0-9\.]*D$", self.args.time_interval):
                datetime_format_pattern = '%Y-%m-%d'
            elif re.match(r"^[0-9\.]*H$", self.args.time_interval):
                datetime_format_pattern = '%Y-%m-%d %H:%M'
            elif re.match(r"^[0-9\.]*min$", self.args.time_interval):
                datetime_format_pattern = '%Y-%m-%d %H:%M'

            # Group by time period and run the calculation
            for time_period, group in data:
                result = self.__run_calculation(group)
                dt_datetime = pd.to_datetime(time_period)
                datetime_string = dt_datetime.strftime(datetime_format_pattern)
                print(f"{datetime_string}: {result}")
        else:
            print(self.__run_calculation(data))

    def handle_formats_command(self):
        """ Handles the CLI 'formats' command to display supported input formats. """

        # Dynamically get all reader classes from the readers module
        reader_classes = []
        for class_name in readers.__all__:
            # Skip the abstract base class
            if class_name == 'AbstractReader':
                continue
            # Get the actual class object
            reader_class = getattr(readers, class_name)
            reader_classes.append(reader_class)

        # Collect format information from each reader
        formats_data = []
        for reader_class in reader_classes:
            try:
                format_name = reader_class.format_name()
                format_key = reader_class.format_key()
                file_extension = reader_class.file_extension()
                class_name = reader_class.__name__

                format_info = {
                    'name': format_name,
                    'key': format_key,
                    'extension': file_extension or '',
                    'class': class_name
                }
                formats_data.append(format_info)
            except (AttributeError, NotImplementedError):
                # Skip readers that don't implement the static methods
                continue

        # Apply filtering if specified
        if self.args.filter:
            filter_term = self.args.filter.lower()
            formats_data = [
                fmt for fmt in formats_data
                if filter_term in fmt['name'].lower() or 
                   filter_term in fmt['extension'].lower() or
                   filter_term in fmt['key'].lower()
            ]

        # Sort data
        sort_key = self.args.sort
        if sort_key == 'name':
            formats_data.sort(key=lambda x: x['name'].lower(), reverse=self.args.reverse)
        elif sort_key == 'key':
            formats_data.sort(key=lambda x: x['key'].lower(), reverse=self.args.reverse)
        elif sort_key == 'extension':
            formats_data.sort(key=lambda x: x['extension'].lower(), reverse=self.args.reverse)

        # Output based on selected format
        output_format = self.args.output

        if output_format == 'json':
            print(json.dumps(formats_data, indent=2))
        elif output_format == 'yaml':
            try:
                print(yaml.dump(formats_data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(formats_data, indent=2))
        elif output_format == 'csv':
            output = StringIO()
            fieldnames = ['name', 'key', 'extension']
            if self.args.verbose:
                fieldnames.append('class')

            writer = csv.DictWriter(output, fieldnames=fieldnames)
            if not self.args.no_header:
                writer.writeheader()

            for fmt in formats_data:
                row = {k: fmt[k] for k in fieldnames}
                writer.writerow(row)

            print(output.getvalue().rstrip())
        else:  # table format (default)
            self._print_formats_table(formats_data)

    def _print_formats_table(self, formats_data):
        """ Print formats data in a nicely formatted table. """
        if not formats_data:
            print("No formats found matching the criteria.")
            return

        # Determine columns to show
        columns = [
            ('Format', 'name'),
            ('Key', 'key'), 
            ('Extension', 'extension')
        ]

        if self.args.verbose:
            columns.append(('Class', 'class'))

        # Calculate column widths
        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for fmt in formats_data:
                max_width = max(max_width, len(str(fmt[field])))
            col_widths.append(max_width + 2)  # Add padding

        # Create table border
        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        # Print table
        if not self.args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for fmt in formats_data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(fmt[field])
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not self.args.no_header:
            print(border)

        # Show summary
        if not self.args.no_header:
            print(f"\nTotal: {len(formats_data)} format(s)")
            if self.args.filter:
                print(f"Filtered by: '{self.args.filter}'")

class CliInterface:
    """ Definition of the CLI interface """

    @staticmethod
    def parse(argparser: argparse.ArgumentParser) -> argparse.Namespace:
        """ Parses the command line arguments and sets up the CLI interface. """

        subparsers = argparser.add_subparsers(dest='command', help='Verfügbare Befehle')

        # Sub parser for "convert" command
        # -------------------------------------------------------------------------------
        mapping_help = 'Map CNV column names to standard parameter names in the ' \
            'format name=value. Allowed parameter names are: ' + \
            ', \n'.join(f"{k}" for k, v in params.allowed_parameters().items())
        format_help = 'Choose the output format. Allowed formats are: ' + \
            ', '.join(['netcdf','csv','excel'])
        convert_parser = subparsers.add_parser('convert', help='Convert a file to a specific format.')
        convert_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        convert_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        convert_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        convert_parser.add_argument('-o', '--output', type=str, required=True, help='Path of output file')
        convert_parser.add_argument('-F', '--output-format', type=str, choices=output_formats, help=format_help)
        convert_parser.add_argument('-m', '--mapping', nargs='+', help=mapping_help)

        # Sub parser for "show" command
        # -------------------------------------------------------------------------------
        show_parser = subparsers.add_parser('show', help='Show contents of a file.')
        show_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        show_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        show_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        show_parser.add_argument('-s', '--schema', type=str, choices=['summary', 'info', 'example'], default='summary', help='What to show.')

        # Sub parser for "formats" command
        # -------------------------------------------------------------------------------
        formats_parser = subparsers.add_parser('formats', help='Display supported input file formats.')
        formats_parser.add_argument('--output', '-o', type=str, choices=['table', 'json', 'yaml', 'csv'], 
                                   default='table', help='Output format (default: table)')
        formats_parser.add_argument('--filter', '-f', type=str, 
                                   help='Filter formats by name or extension (case-insensitive)')
        formats_parser.add_argument('--sort', '-s', type=str, choices=['name', 'key', 'extension'], 
                                   default='name', help='Sort by field (default: name)')
        formats_parser.add_argument('--reverse', '-r', action='store_true', 
                                   help='Reverse sort order')
        formats_parser.add_argument('--no-header', action='store_true', 
                                   help='Omit header row (useful for scripts)')
        formats_parser.add_argument('--verbose', '-v', action='store_true', 
                                   help='Show additional information like class names')

        # Sub parser for "plot-ts" command
        # -------------------------------------------------------------------------------
        plot_ts_parser = subparsers.add_parser('plot-ts', help='Plot a T-S diagram from a netCDF, CNV, CSV, or TOB file')
        plot_ts_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        plot_ts_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        plot_ts_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        plot_ts_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_ts_parser.add_argument('-t', '--title', default='T-S Diagram', type=str, help='Title of the plot.')
        plot_ts_parser.add_argument('--dot-size', default=70, type=int, help='Dot size for scatter plot (1-200)')
        plot_ts_parser.add_argument('--colormap', default='jet', type=str, help='Name of the colormap for the plot. Must be a valid Matplotlib colormap.')
        plot_ts_parser.add_argument('--no-lines-between-dots', default=False, action='store_true', help='Disable the connecting lines between dots.')
        plot_ts_parser.add_argument('--no-colormap', action='store_true', default=False, help='Disable the colormap in the plot')
        plot_ts_parser.add_argument('--no-isolines', default=False, action='store_true', help='Disable the density isolines in the plot')
        plot_ts_parser.add_argument('--no-grid', default=False, action='store_true', help='Disable the grid.')

        # Sub parser for "plot-profile" command
        # -------------------------------------------------------------------------------
        plot_profile_parser = subparsers.add_parser('plot-profile', help='Plot a vertical CTD profile from an input file')
        plot_profile_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        plot_profile_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        plot_profile_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        plot_profile_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_profile_parser.add_argument('-t', '--title', default='Salinity and Temperature Profiles', type=str, help='Title of the plot.')
        plot_profile_parser.add_argument('--dot-size', default=3, type=int, help='Dot size for scatter plot (1-200)')
        plot_profile_parser.add_argument('--no-lines-between-dots', default=False, action='store_true', help='Disable the connecting lines between dots.')
        plot_profile_parser.add_argument('--no-grid', default=False, action='store_true', help='Disable the grid.')

        # Sub parser for "plot-series" command
        # -------------------------------------------------------------------------------
        plot_series_parser = subparsers.add_parser('plot-series', help='Plot a time series for one or multiple parameters from an input file')
        plot_series_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        plot_series_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        plot_series_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        plot_series_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_series_parser.add_argument('-p', '--parameter', type=str, nargs='+', required=True, 
                                       help='Standard name(s) of parameter(s), e.g. "temperature" or "temperature,salinity" or "temperature salinity pressure". ' +
                                            'Multiple parameters can be specified either comma-separated in quotes or as separate arguments.')
        plot_series_parser.add_argument('--dual-axis', action='store_true', default=False,
                                       help='Use dual y-axes for parameters with different units (only for multiple parameters)')
        plot_series_parser.add_argument('--normalize', action='store_true', default=False,
                                       help='Normalize all parameters to 0-1 range for comparison (only for multiple parameters)')
        plot_series_parser.add_argument('--colors', type=str, nargs='*',
                                       help='Custom colors for each parameter line (e.g., --colors red blue green)')
        plot_series_parser.add_argument('--line-styles', type=str, nargs='*',
                                       help='Custom line styles for each parameter (e.g., --line-styles - -- -. :)')

        # Sub parser for "subset" command
        # -------------------------------------------------------------------------------
        calc_parser = subparsers.add_parser('subset', help='Extract a subset of a file and save the result in another')
        calc_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        calc_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        calc_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        calc_parser.add_argument('-o', '--output', type=str, help='Path of output file')
        calc_parser.add_argument('-F', '--output-format', type=str, choices=output_formats, help=format_help)
        calc_parser.add_argument('--time-min', type=str, help='Minimum datetime value. Formats are: YYYY-MM-DD HH:ii:mm.ss')
        calc_parser.add_argument('--time-max', type=str, help='Maximum datetime value. Formats are: YYYY-MM-DD HH:ii:mm.ss')
        calc_parser.add_argument('--sample-min', type=int, help='Minimum sample/index value (integer)')
        calc_parser.add_argument('--sample-max', type=int, help='Maximum sample/index value (integer)')
        calc_parser.add_argument('--parameter', type=str, help='Standard name of a parameter, e.g. "temperature" or "salinity".')
        calc_parser.add_argument('--value-min', type=float, help='Minimum value for the specified parameter (float, integer)')
        calc_parser.add_argument('--value-max', type=float, help='Maximum value for the specified parameter (float, integer)')

        # Sub parser for "calc" command
        # -------------------------------------------------------------------------------
        method_choices = ['min', 'max', 'mean', 'arithmetic_mean', 'median', 'std', 'standard_deviation', 'var', 'variance', 'sum']
        calc_parser = subparsers.add_parser('calc', help='Run an aggregate function on a parameter of the whole dataset')
        calc_parser.add_argument('-i', '--input', type=str, required=True, help='Path of input file')
        calc_parser.add_argument('-f', '--input-format', type=str, default=None, choices=input_formats, help='Format of input file')
        calc_parser.add_argument('-H', '--header-input', type=str, default=None, help='Path of header input file (for Nortek ASCII files)')
        calc_parser.add_argument('-o', '--output', type=str, help='Path of output file')
        calc_parser.add_argument('-F', '--output-format', type=str, choices=output_formats, help=format_help)
        calc_parser.add_argument('-M', '--method', type=str, choices=method_choices, help='Mathematical method operated on the values.')
        calc_parser.add_argument('-p', '--parameter', type=str, required=True, help='Standard name of a parameter, e.g. "temperature" or "salinity".')
        calc_parser.add_argument('-r', '--resample', default=False, action='store_true', help='Resample the time series.')
        calc_parser.add_argument('-T', '--time-interval', type=str, help='Time interval for resampling. Examples: 1M (one month)')

        return argparser.parse_args()

def main():
    """ Main entry point for the CTD Tools CLI. """

    argparser = argparse.ArgumentParser(description='CTD Tools', \
                                        formatter_class=argparse.RawTextHelpFormatter)
    args = CliInterface.parse(argparser)
    controller = CommandController(argparser, args)
    controller.execute()

# if the script is run directly, execute the main function
if __name__ == "__main__":
    main()
