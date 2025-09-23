"""
CLI router.

This module handles command routing with lazy dependency loading.
"""

import sys
from typing import List
from ..core import DependencyManager, DataIOManager
from ..core.exceptions import SeaSenseLibError
from .parser import ArgumentParser
from .commands import CommandFactory


class CLIRouter:
    """Main CLI router with lazy loading capabilities.
    
    This class is responsible for routing commands and executing them
    while managing dependencies and I/O operations. It uses lazy loading
    to improve startup performance by deferring heavy imports until they
    are actually needed.

    Attributes:
    ----------
    dependency_manager : DependencyManager
        Manages lazy loading of dependencies.
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
        self.dependency_manager = DependencyManager()
        self.io_manager = DataIOManager(self.dependency_manager)
        self.argument_parser = ArgumentParser()
        self.command_factory = CommandFactory()

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
            # Quick parse to get command name
            command_name = self.argument_parser.parse_command_quickly(args)

            if not command_name:
                # No command specified or help requested
                parser = self.argument_parser.create_full_parser()
                parser.print_help()
                return 0

            # Create command instance
            command = self.command_factory.create_command(
                command_name, self.dependency_manager, self.io_manager
            )

            # Parse full arguments for this specific command
            parser = self.argument_parser.create_full_parser()
            parsed_args = parser.parse_args(args)

            # Execute command
            result = command.execute(parsed_args)
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
