"""
Base classes for command handling.
"""

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from ...core import DependencyManager, DataIOManager


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    message: str = ""
    data: Any = None
    exit_code: int = 0


class BaseCommand(ABC):
    """Abstract base class for all commands."""

    def __init__(self, dependency_manager: DependencyManager, io_manager: DataIOManager):
        self.deps = dependency_manager
        self.io = io_manager

    @abstractmethod
    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute the command with given arguments."""
        pass

    def _parse_parameters(self, parameter_args):
        """Parse parameter arguments supporting both comma-separated and space-separated formats."""
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
