import argparse
import os
import ctd_tools.ctd_parameters as ctdparams

from .modules.reader import NetCdfReader, CsvReader, CnvReader
from .modules.writer import NetCdfWriter, CsvWriter
from .modules.plotter import CtdPlotter

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
        else:
            self.argsparser.print_help()

    def __read_data(self, input_file):
        """ Helper for readling CTD data from input file of different types. 
        Returns the data. """

        if input_file.endswith('.nc'):
            reader = NetCdfReader(input_file)
        elif input_file.endswith('.csv'):
            reader = CsvReader(input_file)
        elif input_file.endswith('.cnv'):
            reader = CnvReader(input_file)
        else:
            raise argparse.ArgumentTypeError("Input file must be a netCDF (.nc) " \
                    "CSV (.csv), or CNV (.cnv) file.")
        return reader.get_data()
    
    def __handle_output_directory(self, output_file):
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

    def handle_plot_series_command(self):
        """ Handles the CLI 'plot-series' command. """

        # Read data from input file
        data = self.__read_data(self.args.input)
        
        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Create plotter
        plotter = CtdPlotter(data)
        plotter.plot_time_series(parameter_name=self.args.parameter, output_file=self.args.output)

    def handle_plot_profile_command(self):
        """ Handles the CLI 'plot-profile' command. """

        # Read data from input file
        data = self.__read_data(self.args.input)
        
        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Create plotter
        plotter = CtdPlotter(data)
        plotter.plot_profile(
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
        data = self.__read_data(self.args.input)

        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Create plotter
        plotter = CtdPlotter(data)
        plotter.plot_ts_diagram(
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

        # Determine output format
        format = None
        if self.args.format:
            format = self.args.format
        else:
            if self.args.output.endswith('.nc'):
                format = 'netcdf'
            elif self.args.output.endswith('.csv'):
                format = 'csv'
            else:
                raise argparse.ArgumentTypeError(
                    "Output file must be a netCDF (.nc) " \
                    "or CSV (.csv) file.")

        # Map column names to standard parameter names
        parameter_mapping = {}
        allowed_parameters = ctdparams.allowed_parameters()
        if self.args.mapping:
            for mapping in self.args.mapping:
                key, value = mapping.split('=')
                if key in allowed_parameters:
                    parameter_mapping[key] = value
                else:
                    raise ValueError(f"Unallowed parameter name: {key}. " \
                            "Allowed parameters are: {', '.join(allowed_parameters)}")

        # Create output directory if it doesn't exist
        self.__handle_output_directory(self.args.output)

        # Read data from CNV file
        reader = CnvReader(self.args.input, parameter_mapping)

        # Write data to netCDF or CSV
        if format == 'netcdf':
            writer = NetCdfWriter(reader.get_data())
            writer.write(self.args.output)
        elif format == 'csv':
            writer = CsvWriter(reader.get_data())
            writer.write(self.args.output)
        else:
            raise argparse.ArgumentTypeError('Unknown output format')

    def handle_show_command(self):
        """ Handles the CLI 'show' command. """

        # Read data from input file
        data = self.__read_data(self.args.input)

        if data:
            if self.args.format == 'summary':
                print(data)
            elif self.args.format == 'info':
                data.info()
            elif self.args.format == 'example':
                df = data.to_dataframe()
                print(df.head())
        else:
            raise ValueError('No data found in file.')

class CliInterface:
    """ Definition of the CLI interface """

    @staticmethod
    def parse(argparser: argparse.ArgumentParser):
        subparsers = argparser.add_subparsers(dest='command', help='Verfügbare Befehle')

        # Sub parser for "convert" command
        # -------------------------------------------------------------------------------
        mapping_help = 'Map CNV column names to standard parameter names in the ' \
            'format name=value. Allowed parameter names are: ' + \
            ', \n'.join(f"{k}" for k, v in ctdparams.allowed_parameters().items())
        format_help = 'Choose the output format. Allowed formats are: ' + \
            ', '.join(['netcdf','csv'])
        convert_parser = subparsers.add_parser('convert', help='Convert a CNV file to netCDF or CSV')
        convert_parser.add_argument('-i', '--input', type=str, required=True, help='Path of CNV input file')
        convert_parser.add_argument('-o', '--output', type=str, required=True, help='Path of output file')
        convert_parser.add_argument('-f', '--format', type=str, choices=['netcdf', 'csv'], help=format_help)
        convert_parser.add_argument('-m', '--mapping', nargs='+', help=mapping_help)

        # Sub parser for "show" command
        # -------------------------------------------------------------------------------
        show_parser = subparsers.add_parser('show', help='Show contents of a netCDF, CSV, or CNV file.')
        show_parser.add_argument('-i', '--input', type=str, required=True, help='Path of CNV input file')
        show_parser.add_argument('--format', type=str, choices=['summary', 'info', 'example'], default='summary', help='What to show.')

        # Sub parser for "plot-ts" command
        # -------------------------------------------------------------------------------
        plot_ts_parser = subparsers.add_parser('plot-ts', help='Plot a T-S diagram from a netCDF file')
        plot_ts_parser.add_argument('-i', '--input', type=str, required=True, help='Path of netCDF input file')
        plot_ts_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_ts_parser.add_argument('--title', default='T-S Diagram', type=str, help='Title of the plot.')
        plot_ts_parser.add_argument('--dot-size', default=70, type=int, help='Dot size for scatter plot (1-200)')
        plot_ts_parser.add_argument('--colormap', default='jet', type=str, help='Name of the colormap for the plot. Must be a valid Matplotlib colormap.')
        plot_ts_parser.add_argument('--no-lines-between-dots', default=False, action='store_true', help='Disable the connecting lines between dots.')
        plot_ts_parser.add_argument('--no-colormap', action='store_true', default=False, help='Disable the colormap in the plot')
        plot_ts_parser.add_argument('--no-isolines', default=False, action='store_true', help='Disable the density isolines in the plot')
        plot_ts_parser.add_argument('--no-grid', default=False, action='store_true', help='Disable the grid.')

        # Sub parser for "plot-profile" command
        # -------------------------------------------------------------------------------
        plot_profile_parser = subparsers.add_parser('plot-profile', help='Plot a vertical CTD profile from a netCDF file')
        plot_profile_parser.add_argument('-i', '--input', type=str, required=True, help='Path of netCDF input file')
        plot_profile_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_profile_parser.add_argument('--title', default='Salinity and Temperature Profiles', type=str, help='Title of the plot.')
        plot_profile_parser.add_argument('--dot-size', default=3, type=int, help='Dot size for scatter plot (1-200)')
        plot_profile_parser.add_argument('--no-lines-between-dots', default=False, action='store_true', help='Disable the connecting lines between dots.')
        plot_profile_parser.add_argument('--no-grid', default=False, action='store_true', help='Disable the grid.')

        # Sub parser for "plot-series" command
        # -------------------------------------------------------------------------------
        plot_series_parser = subparsers.add_parser('plot-series', help='Plot a time series for a single parameter from a netCDF file')
        plot_series_parser.add_argument('-i', '--input', type=str, required=True, help='Path of netCDF input file')
        plot_series_parser.add_argument('-o', '--output', type=str, help='Path of output file if plot shall be written')
        plot_series_parser.add_argument('-p', '--parameter', type=str, required=True, help='Standard name of a parameter, e.g. "temperature" or "salinity".')

        return argparser.parse_args()

def main():
    argparser = argparse.ArgumentParser(description='CTD Tools', formatter_class=argparse.RawTextHelpFormatter)
    args = CliInterface.parse(argparser)
    controller = CommandController(argparser, args)
    controller.execute()

if __name__ == "__main__":
    main()
