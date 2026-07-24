"""
Command-line argument parsing with lazy loading capabilities.
"""

import argparse
from typing import List, Optional

from .._version import PACKAGE_NAME, get_version


class _HideFormatsHelpFormatter(argparse.RawTextHelpFormatter):
    """Custom formatter that hides legacy commands from help output."""
    
    # Commands to hide from help
    HIDDEN_COMMANDS = {'formats'}
    
    def _format_action(self, action):
        """Override to filter out hidden commands from subcommand choices."""
        # Get the original formatted action
        result = super()._format_action(action)
        
        # If this is the subparsers action, clean up hidden commands
        if hasattr(action, 'choices') and action.choices:
            # Check if any hidden commands are present
            has_hidden = any(cmd in action.choices for cmd in self.HIDDEN_COMMANDS)
            
            if has_hidden:
                # Remove hidden commands from the metavar/choices display in usage line
                for cmd in self.HIDDEN_COMMANDS:
                    result = result.replace(f',{cmd}}}', '}')
                    result = result.replace(f'{{{cmd},', '{')
                    result = result.replace(f',{cmd},', ',')
                
                # Remove any line that contains ==SUPPRESS== (hidden command help lines)
                lines = result.split('\n')
                filtered_lines = []
                for line in lines:
                    if '==SUPPRESS==' in line:
                        continue
                    filtered_lines.append(line)
                result = '\n'.join(filtered_lines)
        
        return result
    
    def _format_usage(self, usage, actions, groups, prefix):
        """Override to remove hidden commands from usage line."""
        result = super()._format_usage(usage, actions, groups, prefix)
        # Remove hidden commands from the usage line
        for cmd in self.HIDDEN_COMMANDS:
            result = result.replace(f',{cmd}}}', '}')
            result = result.replace(f'{{{cmd},', '{')
            result = result.replace(f',{cmd},', ',')
        return result


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
        # Lazy load format lists when needed
        self._input_formats = None
        self._output_formats = None
        self._default_profiles = ['default', 'minimal', 'full']
        self._default_stages = [
            "mapping",
            "unit_handling",
            "transformation",
            "derivation",
            "metadata_extraction",
            "metadata_enrichment",
            "validation",
            "finalization",
        ]

    @property
    def INPUT_FORMATS(self):
        """Lazy load input formats."""
        if self._input_formats is None:
            from ..core.autodiscovery import get_input_formats
            self._input_formats = get_input_formats()
        return self._input_formats

    @property
    def OUTPUT_FORMATS(self):
        """Lazy load output formats."""
        if self._output_formats is None:
            from ..core.autodiscovery import get_output_formats
            self._output_formats = get_output_formats()
        return self._output_formats

    def _get_available_stages(self, lightweight: bool = False):
        """Get list of available stage names."""
        if lightweight:
            return list(self._default_stages)
        from ..pipeline.registry import StageRegistry
        try:
            registry = StageRegistry.get_instance()
            return registry.list_stages()
        except Exception:
            # If discovery fails, fall back to the registry defaults.
            return StageRegistry.default_stage_names()

    def _get_available_profiles(self, lightweight: bool = False):
        """Get list of available pipeline profile names."""
        if lightweight:
            return list(self._default_profiles)
        try:
            from importlib import resources
            profiles = resources.files('seasenselib.config.pipeline')
            names = []
            for entry in profiles.iterdir():
                if entry.name.endswith('.json'):
                    names.append(entry.name[:-5])
            return sorted(names)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load pipeline profiles from package resources."
            ) from exc

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

    def create_plot_parser_for_plotter(self, plotter_key: str) -> argparse.ArgumentParser:
        """Create a specialized parser for a specific plotter.
        
        Parameters:
        -----------
        plotter_key : str
            The key of the plotter (e.g., 'time-series', 'ts-diagram', etc.)
            
        Returns:
        --------
        argparse.ArgumentParser
            A parser with only the arguments relevant to the specified plotter
        """
        parser = argparse.ArgumentParser(
            prog=f'seasenselib plot {plotter_key}',
            description=f'Create plots using the {plotter_key} plotter',
            formatter_class=_HideFormatsHelpFormatter
        )
        
        # Common arguments for all plotters
        parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        parser.add_argument('-f', '--input-format', type=str,
                    default=None, choices=self.INPUT_FORMATS,
                    help='Format of input file')
        parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header/metadata input file (for Nortek ASCII or Nortek CSV String Data.csv)')
        parser.add_argument('-o', '--output', type=str,
                    help='Path of output file if plot shall be written')
        parser.add_argument('-t', '--title', type=str,
                    help='Title of the plot')
        parser.add_argument('-m', '--mapping', nargs='+',
                    help='Map source variables to canonical parameter names (canonical=source).')
        parser.add_argument('--processing-protocol', nargs='?', const=True, default=None,
                    help='Write a processing protocol (JSON) next to the plot or input (optionally specify path)')
        self._add_reader_config_args(parser)
        self._add_stage_control_args(parser)
        
        # Try to let the plotter class declare its own CLI args (plugins supported)
        try:
            # Lazy import discovery to avoid heavy imports when not needed
            from ..core.autodiscovery import PlotterDiscovery
            discovery = PlotterDiscovery()
            plotter_class = discovery.get_class_by_key(plotter_key)
            if plotter_class and hasattr(plotter_class, 'add_cli_arguments'):
                # Allow the plotter to add its arguments to the parser
                try:
                    plotter_class.add_cli_arguments(parser)
                except Exception:
                    # If the plotter's hook misbehaves, fall back to generic args
                    parser.add_argument('-p', '--parameter', type=str, nargs='*',
                                        help='Parameter(s) to plot (plotter-specific)')
            else:
                # Unknown or plugin without hook: provide a generic parameter option
                parser.add_argument('-p', '--parameter', type=str, nargs='*',
                                    help='Parameter(s) to plot (plotter-specific)')
        except Exception:
            # If discovery fails for any reason, provide the generic argument
            parser.add_argument('-p', '--parameter', type=str, nargs='*',
                                help='Parameter(s) to plot (plotter-specific)')

        # Logging options
        self._add_logging_args(parser)
        
        return parser

    def create_full_parser(self, lightweight: bool = False) -> argparse.ArgumentParser:
        """Create the full argument parser with all subcommands."""
        parser = argparse.ArgumentParser(
            description='SeaSenseLib - Oceanographic sensor data processing',
            formatter_class=_HideFormatsHelpFormatter
        )
        parser.add_argument('-v', '--version', action='version',
                    version=f'{PACKAGE_NAME} {get_version()}',
                    help='Show the SeaSenseLib version and exit')

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Add all subcommands
        self._add_convert_parser(subparsers, lightweight=lightweight)
        self._add_show_parser(subparsers, lightweight=lightweight)
        self._add_list_parser(subparsers, lightweight=lightweight)
        self._add_plot_parser(subparsers, lightweight=lightweight)
        self._add_subset_parser(subparsers, lightweight=lightweight)
        self._add_calc_parser(subparsers, lightweight=lightweight)
        
        # Add hidden aliases for backward compatibility
        self._add_formats_alias(subparsers)

        return parser

    def create_command_parser(self, command_name: str, lightweight: bool = False) -> argparse.ArgumentParser:
        """Create a parser for a specific command only."""
        if command_name == 'convert':
            return self._add_convert_parser(None, lightweight=lightweight)
        if command_name == 'show':
            return self._add_show_parser(None, lightweight=lightweight)
        if command_name == 'list':
            return self._add_list_parser(None, lightweight=lightweight)
        if command_name == 'plot':
            return self._add_plot_parser(None, lightweight=lightweight)
        if command_name == 'subset':
            return self._add_subset_parser(None, lightweight=lightweight)
        if command_name == 'calc':
            return self._add_calc_parser(None, lightweight=lightweight)
        if command_name == 'formats':
            # legacy alias
            return self._add_list_parser(None, lightweight=lightweight)

        raise ValueError(f"Unknown command: {command_name}")

    def _add_reader_config_args(self, parser):
        """Add reader configuration arguments (for CNV and other formats).
        
        Parameters
        ----------
        parser : argparse.ArgumentParser
            Parser to add arguments to
        """
        parser.add_argument('--no-sanitize', action='store_true', default=False,
                    help=argparse.SUPPRESS)
        parser.add_argument('--reader-arg', action='append', default=[],
                    metavar='NAME=VALUE', dest='reader_args',
                    help=(
                        'Pass a reader-specific option. Can be repeated; '
                        'names are validated for the selected reader. '
                        'Use "seasenselib list reader-args --filter FORMAT" to discover names.'
                    ))
        parser.add_argument('--metadata-file', type=str,
                    help='Path to a metadata JSON file with sections "global" and "variables"')
        parser.add_argument('--metadata', type=str,
                    help='Inline metadata JSON (same structure as --metadata-file). '
                         'Variables should use canonical names.')

    def _add_writer_config_args(self, parser):
        """Add writer configuration arguments."""
        parser.add_argument(
            '--sanitize-netcdf-names',
            action='store_true',
            default=False,
            help=(
                "Replace '/' with '_' in NetCDF dimension, coordinate, and "
                "variable names before writing."
            ),
        )

    def _add_logging_args(self, parser):
        """Add logging configuration arguments."""
        parser.add_argument('--verbose', action='store_true', default=False,
                    help='Enable verbose logging (info level)')
        parser.add_argument('--verbose-level', type=str,
                    choices=['debug', 'info', 'warning', 'error', 'critical'],
                    help='Set verbosity level explicitly')
        parser.add_argument('--verbose-log', nargs='?', const=True, default=None,
                    dest='verbose_log',
                    help='Write verbose output to a file (optionally specify path)')

    def _add_stage_control_args(self, parser, lightweight: bool = False):
        """Add processing stage control arguments for data processing pipeline.
        
        Parameters
        ----------
        parser : argparse.ArgumentParser
            Parser to add arguments to
        """
        available_stages = self._get_available_stages(lightweight=lightweight)
        steps_list = ', '.join(available_stages)
        profiles_list = ', '.join(self._get_available_profiles(lightweight=lightweight))
        
        parser.add_argument('--raw-only', action='store_true', default=False,
                    help='Skip all processing and return raw data from file')
        parser.add_argument('--pipeline-apply-stages', type=str, metavar='STAGE[,STAGE...]',
                    dest='pipeline_apply_stages',
                    help=f'Apply only specified pipeline stages (comma-separated). Available: {steps_list}')
        parser.add_argument('--pipeline-skip-stages', type=str, metavar='STAGE[,STAGE...]',
                    dest='pipeline_skip_stages',
                    help=f'Skip specified pipeline stages (comma-separated). Available: {steps_list}')
        parser.add_argument('--pipeline-profile', dest='pipeline_profile',
                    help=f'Use a built-in pipeline profile. Available: {profiles_list}')
        parser.add_argument('--pipeline-file', dest='pipeline_file',
                    help='Path to a pipeline configuration file (.json/.yaml/.toml)')
        parser.add_argument('--pipeline-apply-handlers', type=str,
                    dest='pipeline_apply_handlers',
                    help='Apply only specified handlers (comma-separated, format: stage:handler)')
        parser.add_argument('--pipeline-skip-handlers', type=str,
                    dest='pipeline_skip_handlers',
                    help='Skip specified handlers (comma-separated, format: stage:handler)')
        parser.add_argument('--default-latitude', type=float,
                    dest='default_latitude',
                    help=(
                        'Fallback latitude in degrees north for derivations '
                        'when input data has no latitude. Used by depth, and by '
                        'TEOS-10 salinity/temperature together with longitude. '
                        'Omit to avoid guessing.'
                    ))
        parser.add_argument('--default-longitude', type=float,
                    dest='default_longitude',
                    help=(
                        'Fallback longitude in degrees east for derivations '
                        'when input data has no longitude. Used by TEOS-10 '
                        'salinity/temperature together with latitude. '
                        'Omit to avoid guessing.'
                    ))

    def _add_convert_parser(self, subparsers, lightweight: bool = False):
        """Add convert command parser."""
        if lightweight:
            mapping_help = 'Map source variables to canonical parameter names (canonical=source).'
        else:
            # We'll import parameters only when needed
            try:
                # pylint: disable=C0415
                import seasenselib.parameters as params
                mapping_help = ('Map source variables to canonical parameter names in the '
                               'format canonical=source. Allowed parameter names are: ' +
                               ', \n'.join(f"{k}" for k, v in params.allowed_parameters().items()))
            except ImportError:
                mapping_help = 'Map source variables to canonical parameter names'

        if lightweight:
            format_help = 'Choose the output format (use "seasenselib list writers" to see options).'
            input_choices = None
            output_choices = None
        else:
            format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(self.OUTPUT_FORMATS)
            input_choices = self.INPUT_FORMATS
            output_choices = self.OUTPUT_FORMATS

        if subparsers is None:
            convert_parser = argparse.ArgumentParser(
                prog='seasenselib convert',
                description='Convert a file to a specific format.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            convert_parser = subparsers.add_parser('convert',
                        help='Convert a file to a specific format.')
        convert_parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        convert_parser.add_argument('-f', '--input-format',
                    type=str, default=None, choices=input_choices,
                    help='Format of input file')
        convert_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header/metadata input file (for Nortek ASCII or Nortek CSV String Data.csv)')
        convert_parser.add_argument('-o', '--output', type=str, required=True,
                    help='Path of output file')
        convert_parser.add_argument('-F', '--output-format', type=str, choices=output_choices, 
                    help=format_help)
        convert_parser.add_argument('-m', '--mapping', nargs='+',
                    help=mapping_help)
        convert_parser.add_argument('--processing-protocol', nargs='?', const=True, default=None,
                    help='Write a processing protocol (JSON) next to the output (optionally specify path)')
        self._add_reader_config_args(convert_parser)
        self._add_writer_config_args(convert_parser)
        self._add_stage_control_args(convert_parser, lightweight=lightweight)
        self._add_logging_args(convert_parser)
        return convert_parser

    def _add_show_parser(self, subparsers, lightweight: bool = False):
        """Add show command parser."""
        if lightweight:
            mapping_help = ('Map source variables to canonical parameter names '
                            '(format: canonical=source)')
            input_choices = None
        else:
            # We'll import parameters only when needed
            try:
                # pylint: disable=C0415
                import seasenselib.parameters as params
                mapping_help = ('Map source variables to canonical parameter names in the '
                               'format canonical=source (e.g., temperature=tv290C). Allowed parameter names are: ' +
                               ', \n'.join(f"{k}" for k, v in params.allowed_parameters().items()))
            except ImportError:
                mapping_help = 'Map source variables to canonical parameter names (format: canonical=source)'
            input_choices = self.INPUT_FORMATS

        if subparsers is None:
            show_parser = argparse.ArgumentParser(
                prog='seasenselib show',
                description='Show contents of a file.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            show_parser = subparsers.add_parser('show',
                        help='Show contents of a file.')
        show_parser.add_argument('-i', '--input', type=str, required=True,
                    help='Path of input file')
        show_parser.add_argument('-f', '--input-format', type=str,
                    default=None, choices=input_choices,
                    help='Format of input file')
        show_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header/metadata input file (for Nortek ASCII or Nortek CSV String Data.csv)')
        show_parser.add_argument('-s', '--schema', type=str,
                    choices=['summary', 'info', 'example'], default='summary',
                    help='What to show.')
        show_parser.add_argument('-m', '--mapping', nargs='+',
                    help=mapping_help)
        show_parser.add_argument('--processing-protocol', nargs='?', const=True, default=None,
                    help='Write a processing protocol (JSON) next to the input (optionally specify path)')
        self._add_reader_config_args(show_parser)
        self._add_stage_control_args(show_parser, lightweight=lightweight)
        self._add_logging_args(show_parser)
        return show_parser

    def _add_list_parser(self, subparsers, lightweight: bool = False):
        """Add list command parser."""
        if subparsers is None:
            list_parser = argparse.ArgumentParser(
                prog='seasenselib list',
                description='List available readers, writers, plotters, parameters, or pipeline resources.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            list_parser = subparsers.add_parser('list',
                        help='List available readers, writers, plotters, parameters, or pipeline resources.')
        list_parser.add_argument('resource_type', type=str, nargs='?', default='all',
                    choices=[
                        'all',
                        'readers',
                        'writers',
                        'plotters',
                        'parameters',
                        'reader-args',
                        'pipeline-stages',
                        'pipeline-handlers',
                        'pipeline-profiles',
                    ],
                    help='Type of resources to list (default: all)')
        list_parser.add_argument('--output', '-o', type=str,
                    choices=['table', 'json', 'yaml', 'csv'], default='table',
                    help='Output format (default: table)')
        list_parser.add_argument('--filter', '-f', type=str,
                    help='Filter by name or extension (case-insensitive)')
        list_parser.add_argument('--sort', '-s', type=str,
                    choices=[
                        'name',
                        'key',
                        'extension',
                        'type',
                        'stage',
                        'class',
                        'reader',
                        'argument',
                    ],
                    default='name',
                    help='Sort by field (default: name)')
        list_parser.add_argument('--reverse', '-r', action='store_true',
                    help='Reverse sort order')
        list_parser.add_argument('--no-header', action='store_true',
                    help='Omit header row (useful for scripts)')
        list_parser.add_argument('--list-details', action='store_true',
                    help='Show additional information like class names')
        self._add_logging_args(list_parser)
        return list_parser

    def _add_plot_parser(self, subparsers, lightweight: bool = False):
        """Add unified plot command parser (simplified for main help)."""
        if subparsers is None:
            plot_parser = argparse.ArgumentParser(
                prog='seasenselib plot',
                description='Create plots using available plotters.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            plot_parser = subparsers.add_parser('plot',
                        help='Create plots using available plotters.')
        plot_parser.add_argument('plotter', type=str, nargs='?',
                    help='Plotter key (use --list-plotters to see available plotters)')
        plot_parser.add_argument('--list-plotters', action='store_true',
                    help='List available plotters and exit')
        # Add a dummy -i argument to prevent "required" error when just checking help
        plot_parser.add_argument('-i', '--input', type=str,
                    help='Path of input file (use "plot <plotter-key> -h" for plotter-specific help)')
        self._add_logging_args(plot_parser)

    def _add_formats_alias(self, subparsers):
        """Add formats command as a hidden alias for 'list readers' (backward compatibility)."""
        # Create a hidden parser that acts like 'list readers'
        formats_parser = subparsers.add_parser('formats',
                    help=argparse.SUPPRESS)  # Hidden from help
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
        formats_parser.add_argument('--list-details', action='store_true',
                    help='Show additional information like class names')

    def _add_subset_parser(self, subparsers, lightweight: bool = False):
        """Add subset command parser."""
        if lightweight:
            format_help = 'Choose the output format (use "seasenselib list writers" to see options).'
            input_choices = None
            output_choices = None
        else:
            format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(self.OUTPUT_FORMATS)
            input_choices = self.INPUT_FORMATS
            output_choices = self.OUTPUT_FORMATS

        if subparsers is None:
            subset_parser = argparse.ArgumentParser(
                prog='seasenselib subset',
                description='Extract a subset of a file.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            subset_parser = subparsers.add_parser('subset', 
                        help='Extract a subset of a file.')
        subset_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        subset_parser.add_argument('-f', '--input-format', type=str, 
                    default=None, choices=input_choices,
                    help='Format of input file')
        subset_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header/metadata input file (for Nortek ASCII or Nortek CSV String Data.csv)')
        subset_parser.add_argument('-o', '--output', type=str,
                    help='Path of output file')
        subset_parser.add_argument('-F', '--output-format', type=str, choices=output_choices, 
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
        self._add_reader_config_args(subset_parser)
        self._add_writer_config_args(subset_parser)
        self._add_logging_args(subset_parser)
        return subset_parser

    def _add_calc_parser(self, subparsers, lightweight: bool = False):
        """Add calc command parser."""
        if lightweight:
            format_help = 'Choose the output format (use "seasenselib list writers" to see options).'
            input_choices = None
            output_choices = None
        else:
            format_help = 'Choose the output format. Allowed formats are: ' + ', '.join(self.OUTPUT_FORMATS)
            input_choices = self.INPUT_FORMATS
            output_choices = self.OUTPUT_FORMATS
        method_choices = [
            'min', 'max', 'mean', 'arithmetic_mean', 'median', 'std',
            'standard_deviation', 'var', 'variance', 'sum'
        ]

        if subparsers is None:
            calc_parser = argparse.ArgumentParser(
                prog='seasenselib calc',
                description='Run an aggregate function on parameters of a dataset.',
                formatter_class=_HideFormatsHelpFormatter
            )
        else:
            calc_parser = subparsers.add_parser('calc',
                        help='Run an aggregate function on parameters of a dataset.')
        calc_parser.add_argument('-i', '--input', type=str, required=True, 
                    help='Path of input file')
        calc_parser.add_argument('-f', '--input-format', type=str, default=None,
                    choices=input_choices, help='Format of input file')
        calc_parser.add_argument('-H', '--header-input', type=str, default=None,
                    help='Path of header/metadata input file (for Nortek ASCII or Nortek CSV String Data.csv)')
        calc_parser.add_argument('-o', '--output', type=str, 
                    help='Path of output file')
        calc_parser.add_argument('-F', '--output-format', type=str, choices=output_choices,
                    help=format_help)
        calc_parser.add_argument('-M', '--method', type=str, choices=method_choices,
                    help='Mathematical method operated on the values.')
        calc_parser.add_argument('-p', '--parameter', type=str, required=True,
                    help='Standard name of a parameter, e.g. "temperature" or "salinity".')
        calc_parser.add_argument('-r', '--resample', default=False, action='store_true',
                    help='Resample the time series.')
        calc_parser.add_argument('-T', '--time-interval', type=str,
                    help='Time interval for resampling. Examples: 1M (one month)')
        self._add_reader_config_args(calc_parser)
        self._add_logging_args(calc_parser)
        return calc_parser
