"""
Module for abstract base class for plotting sensor data from xarray Datasets.

This module defines the `AbstractPlotter` class, which serves as a base class for
all plotter implementations in the SeaSenseLib package. Concrete plotter classes should
inherit from this class and implement the `plot` method to handle the specifics of
creating different types of visualizations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import warnings
import xarray as xr
import seasenselib.parameters as params


class AbstractPlotter(ABC):
    """Abstract base class for plotting sensor data from xarray Datasets.
    
    This class provides a common interface for all plotter implementations.
    All concrete plotter classes should inherit from this class and implement
    the plot method.
    
    This class supports the context manager protocol for automatic figure cleanup:
    
    >>> with SomePlotter(dataset) as plotter:
    ...     plotter.plot()
    >>> # matplotlib figures automatically closed
    
    Attributes:
    -----------
    data : xr.Dataset (read-only)
        The xarray Dataset containing the sensor data to be plotted.
    
    Methods:
    --------
    __init__(data: xr.Dataset):
        Initializes the plotter with the provided xarray Dataset.
    __enter__() -> AbstractPlotter:
        Context manager entry point.
    __exit__(exc_type, exc_val, exc_tb) -> None:
        Context manager exit - closes matplotlib figures.
    data: xr.Dataset (read-only)
        The xarray Dataset containing the sensor data.
    plot(**kwargs):
        Creates the plot (to be implemented by subclasses).
    _get_dataset_without_nan() -> xr.Dataset:
        Returns dataset with NaN values removed from time dimension.
    _validate_required_variables(required_vars: list):
        Validates that required variables exist in the dataset.

    Raises:
    -------
    NotImplementedError:
        If the subclass does not implement the `plot` method.
    TypeError:
        If the provided data is not an xarray Dataset.
    ValueError:
        If required variables are missing from the dataset.
    """

    def __init__(self, data: xr.Dataset | None = None):
        """Initialize the plotter with the provided xarray Dataset.
        
        Parameters:
        -----------
        data : xr.Dataset
            The xarray Dataset containing the sensor data to be plotted.
        """

        # Validate that data is an xarray Dataset or None
        if data is not None and not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Set the data attribute
        self._data = data
        self._initialized = True  # Flag to control setter behavior

    @property
    def data(self) -> xr.Dataset | None:
        """Get the xarray Dataset containing the sensor data (read-only).

        Returns:
        --------
        xr.Dataset | None
            The xarray Dataset containing the sensor data.
        """
        return self._data

    @data.setter
    def data(self, value: xr.Dataset):
        """Set the xarray Dataset with validation (deprecated).
        
        .. deprecated:: 1.5
            Setting data after construction is deprecated and will be
            removed in version 2.0. Create a new plotter instance instead.
        
        Parameters:
        -----------
        value : xr.Dataset
            The xarray Dataset containing the sensor data.
            
        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """
        if not isinstance(value, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Warn if trying to set after initialization
        if hasattr(self, '_initialized') and self._initialized:
            warnings.warn(
                "Setting data after construction is deprecated and will be "
                "removed in version 2.0. Create a new plotter instance instead.",
                DeprecationWarning,
                stacklevel=2
            )

        self._data = value

    def __enter__(self) -> 'AbstractPlotter':
        """Context manager entry point.
        
        Returns:
        --------
        AbstractPlotter
            Returns self for use in with statement.
            
        Examples:
        ---------
        >>> with SomePlotter(dataset) as plotter:
        ...     plotter.plot()
        >>> # figures automatically closed
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes matplotlib figures and releases resources.
        
        Parameters:
        -----------
        exc_type : type
            Exception type if an exception was raised.
        exc_val : BaseException
            Exception value if an exception was raised.
        exc_tb : TracebackType
            Traceback if an exception was raised.
        """
        plt = self._get_plt()
        plt.close('all')  # Close all matplotlib figures
        self._data = None

    def __repr__(self) -> str:
        """String representation of the plotter.
        
        Returns:
        --------
        str
            Human-readable string showing class name and key.
        """
        return f"{self.__class__.__name__}(key='{self.key()}')"

    @abstractmethod
    def plot(self, *args, **kwargs):
        """Create the plot.
        
        This method must be implemented by all subclasses to define
        how the specific type of plot should be created.
        
        Parameters:
        -----------
        *args : tuple
            Positional arguments specific to the plot type.
        **kwargs : dict
            Keyword arguments specific to the plot type.
            
        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this method.
        """
        pass

    @staticmethod
    @abstractmethod
    def name() -> str:
        """Get the name for this plotter.

        This property must be implemented by all subclasses.

        Returns:
        --------
        str
            The name (e.g., 'Time Series', 'T-S Diagram', 'Vertical Profile').

        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Writer classes must define a format name")

    @staticmethod
    @abstractmethod
    def key() -> str:
        """Get the unique key for this writer.

        This property must be implemented by all subclasses.
        
        Returns:
        --------
        str
            The key value (e.g., 'time-series', 'ts-diagram', 'depth-profile').
        
        Raises:
        -------
        NotImplementedError:
            If the subclass does not implement this property.
        """
        raise NotImplementedError("Writer classes must define a key")

    @classmethod
    def add_cli_arguments(cls, parser):
        """Optional hook for plotters to add their CLI arguments.

        Plugins can override this method to register argparse options
        specific to the plotter. The parser passed in will already contain
        the common options (input, output, title, etc.). Implementations
        should only add arguments and not parse them.
        """
        # Default: no extra arguments
        return

    def _get_dataset_without_nan(self) -> xr.Dataset:
        """Returns dataset with NaN values removed from time dimension.
        
        Returns:
        --------
        xr.Dataset
            The dataset with NaN values dropped along the time dimension.
        """
        return self.data.dropna(dim=params.TIME)

    def _validate_required_variables(self, required_vars: list):
        """Validates that required variables exist in the dataset.
        
        Parameters:
        -----------
        required_vars : list
            List of variable names that must exist in the dataset.
            
        Raises:
        -------
        ValueError:
            If any required variable is missing from the dataset.
        """

        missing_vars = []
        for var in required_vars:
            if var not in self.data:
                missing_vars.append(var)

        if missing_vars:
            missing_str = ', '.join(missing_vars)
            raise ValueError(f"Required variable(s) missing from dataset: {missing_str}")

    def _validate_required_variables_any(self, required_groups: list):
        """Validates that at least one variable from each group exists.

        Parameters
        -----------
        required_groups : list of list
            Each inner list is a group of variable names; at least one
            variable from each group must be present in the dataset.

        Raises
        -------
        ValueError:
            If for any group none of its variables are present.
        """

        missing_groups = []
        for group in required_groups:
            if not any(var in self.data for var in group):
                missing_groups.append(' or '.join(group))

        if missing_groups:
            missing_str = '; '.join(missing_groups)
            raise ValueError(
                f"Required variable(s) missing from dataset. Need: {missing_str}"
            )

    def _save_or_show_plot(self, output_file: str | None = None):
        """Helper method to either save plot to file or display it.
        
        Parameters:
        -----------
        output_file : str, optional
            Path to save the plot. If None, the plot is displayed.
        """
        plt = self._get_plt()
        if output_file:
            plt.savefig(output_file)
        else:
            plt.show()

    @staticmethod
    def _get_plt():
        """Lazy import for matplotlib.pyplot to avoid heavy import at module load."""
        import matplotlib.pyplot as plt
        return plt
