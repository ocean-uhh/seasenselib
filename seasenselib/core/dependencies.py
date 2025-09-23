"""
Lazy dependency management for SeaSenseLib.

This module provides a centralized way to manage imports of heavy dependencies,
loading them only when needed to improve CLI startup performance.
"""

import importlib
from typing import Dict, Any, Optional
from .exceptions import DependencyError


class DependencyManager:
    """
    Manages lazy loading of heavy dependencies.
    
    This class provides methods to load various groups of dependencies
    such as data processing, plotting, and numerical processing. It uses
    lazy loading techniques to defer the import of modules until they are
    actually needed, which helps improve the startup performance of the CLI.
    
    Attributes:
    ----------
    _loaded_modules : Dict[str, Any]
        Cache for already loaded modules to avoid redundant imports.
    _dependency_groups : Dict[str, Dict[str, Any]]
        Cache for groups of dependencies, allowing lazy loading of related modules.
    
    Methods:
    -------
    get_data_dependencies() -> Dict[str, Any]:
        Loads and returns data processing dependencies (pandas, xarray, readers, writers).
    get_plot_dependencies() -> Dict[str, Any]:
        Loads and returns plotting dependencies (matplotlib, plotters).
    get_processing_dependencies() -> Dict[str, Any]:
        Loads and returns processing dependencies (numpy, processors).
    get_parameters_module() -> Any:
        Loads and returns the parameters module.
    has_dependency_group(group_name: str) -> bool:
        Checks if a specific dependency group has been loaded.
    clear_cache():
        Clears the cached loaded modules and dependency groups.
    """

    def __init__(self):
        self._loaded_modules: Dict[str, Any] = {}
        self._dependency_groups: Dict[str, Dict[str, Any]] = {}

    def _safe_import(self, module_name: str, feature_name: Optional[str] = None) -> Any:
        """Safely import a module with informative error messages."""
        try:
            return importlib.import_module(module_name)
        except ImportError as e:
            feature = feature_name or module_name
            raise DependencyError(
                f"Optional dependency '{module_name}' not found. "
                f"Install it to use {feature} functionality: "
                f"pip install {module_name.split('.')[0]}"
            ) from e

    def get_data_dependencies(self) -> Dict[str, Any]:
        """Load data processing dependencies (pandas, xarray, readers, writers)."""
        if 'data' not in self._dependency_groups:
            deps = {}
            # Create lazy loaders for heavy dependencies
            deps['pd'] = self._create_lazy_loader('pandas', 'data processing')
            deps['xr'] = self._create_lazy_loader('xarray', 'data processing')

            # For readers, we'll provide a lazy loader that loads individual classes
            deps['readers'] = self._create_readers_loader()
            deps['writers'] = self._create_lazy_loader('seasenselib.writers', 'data writing')

            self._dependency_groups['data'] = deps

        return self._dependency_groups['data']

    def _create_lazy_loader(self, module_name: str, feature_name: str):
        """Create a lazy loader for a single module."""

        class LazyModule:
            """Lazy loader for a module that loads it only when accessed."""

            def __init__(self, module_name, feature_name, dep_manager):
                self.module_name = module_name
                self.feature_name = feature_name
                self.dep_manager = dep_manager
                self._module = None

            def _ensure_loaded(self):
                if self._module is None:
                    # pylint: disable=W0212
                    self._module = self.dep_manager. \
                        _safe_import(self.module_name, self.feature_name)
                return self._module

            def __getattr__(self, name):
                return getattr(self._ensure_loaded(), name)

            def __call__(self, *args, **kwargs):
                return self._ensure_loaded()(*args, **kwargs)

        return LazyModule(module_name, feature_name, self)

    def _create_readers_loader(self):
        """Create a lazy loader for readers that loads individual reader classes on demand."""

        class ReadersLoader:
            """Lazy loader for readers that loads individual reader classes on demand."""

            def __init__(self, dep_manager):
                self.dep_manager = dep_manager
                self._readers_module = None
                self._loaded_classes = {}

                # Get reader classes from the centralized registry
                # pylint: disable=C0415
                from ..readers.registry import get_all_reader_classes
                self._all_readers = ['AbstractReader'] + get_all_reader_classes()

            def _get_readers_module(self):
                """Get the readers module (only when absolutely necessary)."""
                if self._readers_module is None:
                    # pylint: disable=W0212
                    self._readers_module = self.dep_manager. \
                        _safe_import('seasenselib.readers', 'data reading')
                return self._readers_module

            def __getattr__(self, name):
                """Lazy load individual reader classes."""
                if name == '__all__':
                    return self._all_readers

                # Load individual reader class only when accessed
                if name not in self._loaded_classes:
                    readers_module = self._get_readers_module()
                    self._loaded_classes[name] = getattr(readers_module, name)

                # Return the loaded class
                return self._loaded_classes[name]

        return ReadersLoader(self)

    def get_plot_dependencies(self) -> Dict[str, Any]:
        """Load plotting dependencies (matplotlib, plotters)."""

        if 'plot' not in self._dependency_groups:
            deps = {}

            # Configure matplotlib backend first
            matplotlib = self._safe_import('matplotlib', 'plotting')
            deps['matplotlib'] = matplotlib
            deps['plt'] = self._safe_import('matplotlib.pyplot', 'plotting')

            # Import plotters module
            deps['plotters'] = self._safe_import('seasenselib.plotters', 'plotting')

            self._dependency_groups['plot'] = deps

        return self._dependency_groups['plot']

    def get_processing_dependencies(self) -> Dict[str, Any]:
        """Load processing dependencies (numpy, processors)."""
        if 'processing' not in self._dependency_groups:
            deps = {}
            deps['np'] = self._safe_import('numpy', 'numerical processing')

            # Import processors module
            deps['processors'] = self._safe_import('seasenselib.processors', 'processing')

            self._dependency_groups['processing'] = deps

        return self._dependency_groups['processing']

    def get_parameters_module(self) -> Any:
        """Load parameters module."""
        if 'parameters' not in self._loaded_modules:
            try:
                # pylint: disable=C0415
                import seasenselib.parameters as params
                self._loaded_modules['parameters'] = params
            except ImportError as e:
                raise DependencyError(f"Failed to import parameters module: {e}") from e

        return self._loaded_modules['parameters']

    def has_dependency_group(self, group_name: str) -> bool:
        """Check if a dependency group has been loaded."""
        return group_name in self._dependency_groups

    def clear_cache(self):
        """Clear the dependency cache (useful for testing)."""
        self._loaded_modules.clear()
        self._dependency_groups.clear()
