"""
Command factory for creating command instances.
"""

from ...core import DependencyManager, DataIOManager
from ...core.exceptions import CTDToolsError
from .base import BaseCommand
from .data_commands import ConvertCommand, ShowCommand, SubsetCommand, CalcCommand
from .plot_commands import PlotTSCommand, PlotProfileCommand, PlotSeriesCommand
from .info_commands import FormatsCommand


class CommandFactory:
    """Factory for creating command instances."""

    def create_command(self, command_name: str, dependency_manager: DependencyManager, 
                      io_manager: DataIOManager) -> BaseCommand:
        """
        Create a command instance based on command name.
        
        Parameters:
        -----------
        command_name : str
            Name of the command to create
        dependency_manager : DependencyManager
            Dependency manager instance
        io_manager : DataIOManager
            I/O manager instance
            
        Returns:
        --------
        BaseCommand
            Command instance
            
        Raises:
        -------
        CTDToolsError
            If command is unknown
        """
        # Data processing commands
        if command_name == 'convert':
            return ConvertCommand(dependency_manager, io_manager)
        elif command_name == 'show':
            return ShowCommand(dependency_manager, io_manager)
        elif command_name == 'subset':
            return SubsetCommand(dependency_manager, io_manager)
        elif command_name == 'calc':
            return CalcCommand(dependency_manager, io_manager)

        # Plotting commands
        elif command_name == 'plot-ts':
            return PlotTSCommand(dependency_manager, io_manager)
        elif command_name == 'plot-profile':
            return PlotProfileCommand(dependency_manager, io_manager)
        elif command_name == 'plot-series':
            return PlotSeriesCommand(dependency_manager, io_manager)

        # Info commands
        elif command_name == 'formats':
            return FormatsCommand(dependency_manager, io_manager)

        else:
            raise CTDToolsError(f"Unknown command: {command_name}")
