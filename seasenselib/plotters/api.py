"""
Plotting API - Modern interface for oceanographic data visualization.

This module provides a user-friendly API for creating domain-specific plots
of oceanographic sensor data.
"""

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import xarray as xr

# Lazy imports for plotters
_plotters_loaded = False
_plotter_classes = {}

def _load_plotters():
    """Lazy loading of plotter classes."""
    global _plotters_loaded, _plotter_classes

    if not _plotters_loaded:
        from ..plotters import (
            ProfilePlotter, 
            TimeSeriesPlotter, 
            TimeSeriesPlotterMulti,
            TsDiagramPlotter
        )

        _plotter_classes = {
            'profile': ProfilePlotter,
            'time_series': TimeSeriesPlotter,
            'time_series_multi': TimeSeriesPlotterMulti,
            'ts_diagram': TsDiagramPlotter
        }
        _plotters_loaded = True


def profile(dataset: 'xr.Dataset', 
           parameters: Optional[List[str]] = None,
           title: Optional[str] = None,
           output_file: Optional[str] = None,
           show: bool = True,
           **kwargs) -> None:
    """
    Create a vertical profile plot for CTD data.
    
    Parameters
    ----------
    dataset : xarray.Dataset
        The dataset containing CTD profile data
    parameters : List[str], optional
        List of parameters to plot. If None, defaults to ['temperature', 'salinity']
    title : str, optional
        Plot title. If None, auto-generated.
    output_file : str, optional
        Path to save the plot. If None, plot is displayed only.
    show : bool, default True
        Whether to display the plot
    **kwargs
        Additional arguments passed to the plotter
        
    Examples
    --------
    >>> import seasenselib as ssl
    >>> data = ssl.read('ctd_data.cnv')
    >>> ssl.plot.profile(data, parameters=['temperature', 'salinity'])
    """
    _load_plotters()

    plotter = _plotter_classes['profile'](dataset)

    if parameters is None:
        parameters = ['temperature', 'salinity']

    plotter.plot(
        parameters=parameters,
        title=title,
        output_file=output_file,
        show=show,
        **kwargs
    )


def time_series(dataset: 'xr.Dataset',
               parameters: Optional[List[str]] = None,
               title: Optional[str] = None,
               output_file: Optional[str] = None,
               show: bool = True,
               **kwargs) -> None:
    """
    Create time series plots for moored instrument data.
    
    Parameters
    ----------
    dataset : xarray.Dataset
        The dataset containing time series data
    parameters : List[str], optional
        List of parameters to plot. If None, plots all available parameters.
    title : str, optional
        Plot title. If None, auto-generated.
    output_file : str, optional
        Path to save the plot. If None, plot is displayed only.
    show : bool, default True
        Whether to display the plot
    **kwargs
        Additional arguments passed to the plotter
        
    Examples
    --------
    >>> import seasenselib as ssl
    >>> data = ssl.read('mooring_data.csv')
    >>> ssl.plot.time_series(data, parameters=['temperature'])
    """
    _load_plotters()

    if parameters is None or len(parameters) == 1:
        # Single parameter plot
        plotter = _plotter_classes['time_series'](dataset)
        param = parameters[0] if parameters else list(dataset.data_vars.keys())[0]
        plotter.plot(
            parameter_names=param,
            title=title,
            output_file=output_file,
            show=show,
            **kwargs
        )
    else:
        # Multi-parameter plot
        plotter = _plotter_classes['time_series_multi'](dataset)
        plotter.plot(
            parameter_names=parameters,
            title=title,
            output_file=output_file,
            show=show,
            **kwargs
        )


def ts_diagram(dataset: 'xr.Dataset',
              title: Optional[str] = None,
              output_file: Optional[str] = None,
              show: bool = True,
              **kwargs) -> None:
    """
    Create a Temperature-Salinity (T-S) diagram with density isolines.
    
    Parameters
    ----------
    dataset : xarray.Dataset
        The dataset containing temperature and salinity data
    title : str, optional
        Plot title. If None, auto-generated.
    output_file : str, optional
        Path to save the plot. If None, plot is displayed only.
    show : bool, default True
        Whether to display the plot
    **kwargs
        Additional arguments passed to the plotter
        
    Examples
    --------
    ```python
    import seasenselib as ssl
    ds = ssl.read('ctd_profile.cnv')
    ssl.plot.ts_diagram(ds, title="Station 001 T-S Diagram")
    ssl.plot.time_series(ds, parameters=['temperature', 'salinity'], dual_axis=True, normalize=True)
    ```
    """
    _load_plotters()

    plotter = _plotter_classes['ts_diagram'](dataset)
    plotter.plot(
        title=title,
        output_file=output_file,
        show=show,
        **kwargs
    )


# Export the public API
__all__ = [
    'profile',
    'time_series', 
    'ts_diagram'
]
