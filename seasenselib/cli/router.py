"""
CLI router.

This module handles command routing and execution.
"""

import sys
import logging
from typing import List
from ..core.exceptions import SeaSenseLibError
from .._version import PACKAGE_NAME, get_version
from .parser import ArgumentParser
from .commands import CommandFactory

logger = logging.getLogger(__name__)

class CLIRouter:
    """Main CLI router.
    
    This class is responsible for routing commands and executing them
    while managing I/O operations.

    Attributes:
    ----------
    io_manager : DataIOManager
        Handles data input/output operations.
    argument_parser : ArgumentParser
        Parses command line arguments.
    command_factory : CommandFactory
        Creates command instances based on parsed arguments.

    Methods:
    -------
    route_and_execute(args: List[str]) -> int:
        Routes the command based on arguments and executes it.
        Returns an exit code (0 for success, non-zero for error).

    """

    def __init__(self):
        self._io_manager = None
        self.argument_parser = ArgumentParser()
        self.command_factory = CommandFactory()

    def _get_io_manager(self):
        if self._io_manager is None:
            from ..core import DataIOManager
            self._io_manager = DataIOManager()
        return self._io_manager

    def route_and_execute(self, args: List[str]) -> int:
        """Route command and execute with lazy loading.

        This method parses the command line arguments to determine which
        command to execute. It uses the ArgumentParser to quickly identify
        the command name, then creates the appropriate command instance
        using the CommandFactory. It also handles any exceptions that may
        occur during command execution, including user cancellations and
        specific errors.
        
        Parameters:
        -----------
        args : List[str]
            Command line arguments
            
        Returns:
        --------
        int
            Exit code (0 for success, non-zero for error)

        Raises:
        -------
        KeyboardInterrupt:
            Catches user cancellation and exits gracefully.
        SeaSenseLibError:
            Catches specific SeaSenseLib errors and prints an error message.
        Exception:
            Catches unexpected errors and prints an error message. 
        """
        try:
            if args and args[0] in ('-v', '--version'):
                print(f"{PACKAGE_NAME} {get_version()}")
                return 0

            # Quick parse to get command name
            command_name = self.argument_parser.parse_command_quickly(args)

            if not command_name:
                # No command specified or help requested
                parser = self.argument_parser.create_full_parser(lightweight=True)
                parser.print_help()
                return 0

            # Special handling for plot command with plotter-specific help
            if command_name == 'plot':
                return self._handle_plot_command(args)

            help_requested = '-h' in args or '--help' in args

            try:
                parser = self.argument_parser.create_command_parser(
                    command_name, lightweight=help_requested
                )
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1

            if help_requested:
                parser.print_help()
                return 0

            parsed_args = parser.parse_args(args[1:])

            # Configure logging if requested
            self._configure_logging(parsed_args)

            # Create command instance
            if command_name in {'list', 'formats'}:
                io_manager = None
            else:
                io_manager = self._get_io_manager()
            command = self.command_factory.create_command(command_name, io_manager)

            # Execute command
            result = command.execute(parsed_args)
            
            # Print error message if command failed
            if not result.success and result.message:
                print(result.message, file=sys.stderr)
            
            return 0 if result.success else 1

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.", file=sys.stderr)
            return 1
        except SeaSenseLibError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1

    def _handle_plot_command(self, args: List[str]) -> int:
        """Handle plot command with dynamic parser based on plotter key.
        
        Parameters:
        -----------
        args : List[str]
            Command line arguments (including 'plot')
            
        Returns:
        --------
        int
            Exit code (0 for success, non-zero for error)
        """
        from ..core.autodiscovery import PlotterDiscovery
        
        # Check if help is requested and extract plotter key
        help_requested = '-h' in args or '--help' in args
        
        # Extract plotter key (second argument after 'plot')
        plotter_key = None
        if len(args) >= 2 and not args[1].startswith('-'):
            plotter_key = args[1]
        
        # If help is requested with a specific plotter key, show plotter-specific help
        if help_requested and plotter_key:
            # Validate that the plotter exists
            discovery = PlotterDiscovery()
            plotter_class = discovery.get_class_by_key(plotter_key)
            
            if not plotter_class:
                available = discovery.get_format_info()
                keys = [p['key'] for p in available]
                print(f"Error: Unknown plotter '{plotter_key}'.", file=sys.stderr)
                print(f"Available plotters: {', '.join(keys)}", file=sys.stderr)
                print("Use 'seasenselib list plotters' for more details.", file=sys.stderr)
                return 1
            
            # Create and show plotter-specific parser
            parser = self.argument_parser.create_plot_parser_for_plotter(plotter_key)
            parser.print_help()
            return 0
        
        # If help is requested without plotter key OR no plotter key provided, show available plotters
        if (help_requested and not plotter_key) or (not plotter_key):
            discovery = PlotterDiscovery()
            plotters = discovery.get_format_info()
            
            print("usage: seasenselib plot <plotter-key> [options]")
            print()
            print("Create plots using available plotters.")
            print()
            print("Available plotter keys:")
            for plotter in sorted(plotters, key=lambda x: x['key']):
                plugin_marker = " [PLUGIN]" if plotter.get('is_plugin', False) else ""
                print(f"  {plotter['key']:<20} {plotter['name']}{plugin_marker}")
            print()
            print("Use 'seasenselib plot <plotter-key> -h' for plotter-specific options.")
            print("Use 'seasenselib list plotters' for more details.")
            print()
            print("Examples:")
            print("  seasenselib plot ts-diagram -i data.cnv -o output.png")
            print("  seasenselib plot time-series -i data.cnv -p temperature")
            print("  seasenselib plot time-series-multi -i data.cnv -p temp salinity --dual-axis")
            return 0
        
        # Normal execution - parse with plotter-specific parser
        parser = self.argument_parser.create_plot_parser_for_plotter(plotter_key)
        # Remove 'plot' and plotter_key from args for parsing
        remaining_args = [arg for i, arg in enumerate(args) if not (i == 0 or (i == 1 and arg == plotter_key))]
        parsed_args = parser.parse_args(remaining_args)
        self._configure_logging(parsed_args)
        # Add back the plotter key
        parsed_args.plotter = plotter_key
        # Add default values for optional args that might not be in this specific parser
        if not hasattr(parsed_args, 'list_plotters'):
            parsed_args.list_plotters = False
        
        # Create and execute command
        command = self.command_factory.create_command('plot', self._get_io_manager())
        result = command.execute(parsed_args)
        
        # Print error message if command failed
        if not result.success and result.message:
            print(result.message, file=sys.stderr)
        
        return 0 if result.success else 1

    @staticmethod
    def _configure_logging(parsed_args) -> None:
        """Configure logging based on CLI flags."""
        verbose = getattr(parsed_args, 'verbose', False)
        level_name = getattr(parsed_args, 'verbose_level', None)
        log_target = getattr(parsed_args, 'verbose_log', None)
        package_logger = logging.getLogger("seasenselib")

        for handler in list(package_logger.handlers):
            package_logger.removeHandler(handler)
            handler.close()
        package_logger.propagate = False

        if not verbose and not log_target:
            # Suppress all package logging unless --verbose/--verbose-log is used.
            package_logger.setLevel(logging.ERROR)
            return

        if level_name:
            level = getattr(logging, level_name.upper(), logging.INFO)
        else:
            level = logging.INFO
        package_logger.setLevel(level)

        log_path = None
        if log_target:
            if isinstance(log_target, str):
                log_path = log_target
            else:
                output = getattr(parsed_args, 'output', None)
                if output:
                    log_path = f"{output}.log"
                else:
                    log_path = "seasenselib.log"
            try:
                from pathlib import Path
                Path(log_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                logger.debug("Failed to create log directory for '%s'", log_path, exc_info=True)

        handlers = []
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        if verbose:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(level)
            stream_handler.setFormatter(formatter)
            handlers.append(stream_handler)

        if log_path:
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

        for handler in handlers:
            package_logger.addHandler(handler)
